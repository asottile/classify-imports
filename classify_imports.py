from __future__ import annotations

import ast
import collections
import functools
import operator
import os.path
import stat
import sys
from importlib.util import find_spec
from typing import Any
from typing import Callable
from typing import Generator
from typing import Generic
from typing import Iterable
from typing import NamedTuple
from typing import TypeVar

from distutils import sysconfig

T = TypeVar('T')


class cached_property(Generic[T]):
    def __init__(self, func: Callable[[Any], T]) -> None:
        self._func = func

    def __get__(self, instance: object, owner: type[Any]) -> T:
        ret = instance.__dict__[self._func.__name__] = self._func(instance)
        return ret


class Classified:
    FUTURE = 'FUTURE'
    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    order = (FUTURE, BUILTIN, THIRD_PARTY, APPLICATION)


_STATIC_CLASSIFICATIONS = {
    '__future__': Classified.FUTURE,
    '__main__': Classified.APPLICATION,
    # force distutils to be "third party" after being gobbled by setuptools
    'distutils': Classified.THIRD_PARTY,
    # relative imports: `from .foo import bar`
    '': Classified.APPLICATION,
}


class Settings(NamedTuple):
    application_directories: tuple[str, ...] = ('.',)
    unclassifiable_application_modules: frozenset[str] = frozenset()


def _path_key(path: str) -> tuple[str, tuple[int, int]]:
    path = path or '.'  # '' in sys.path is the current directory
    # os.path.samestat uses (st_ino, st_dev) to determine equality
    st = os.stat(path)
    return path, (st.st_ino, st.st_dev)


def _find_local(path: tuple[str, ...], base: str) -> bool:
    for p in path:
        p_dir = os.path.join(p, base)
        try:
            stat_dir = os.lstat(p_dir)
        except OSError:
            pass
        else:
            if stat.S_ISDIR(stat_dir.st_mode) and os.listdir(p_dir):
                return True
        try:
            stat_file = os.lstat(os.path.join(p, f'{base}.py'))
        except OSError:
            pass
        else:
            return stat.S_ISREG(stat_file.st_mode)
    else:
        return False


@functools.lru_cache(maxsize=None)
def _get_app(app_dirs: tuple[str, ...]) -> tuple[str, ...]:
    app_dirs_ret = []
    filtered_stats = set()
    for p in app_dirs:
        try:
            p, key = _path_key(p)
        except OSError:
            continue
        else:
            if key not in filtered_stats:
                app_dirs_ret.append(p)
                filtered_stats.add(key)

    return tuple(app_dirs_ret)


_STDLIB_PATH = sysconfig.get_python_lib(standard_lib=True)
if sys.version_info >= (3, 10):  # pragma: >=3.10 cover
    _BUILTIN_MODS = frozenset(sys.stdlib_module_names)
else:  # pragma: <3.10 cover
    _BUILTIN_MODS = frozenset(sys.builtin_module_names)


@functools.lru_cache(maxsize=None)
def classify_base(base: str, settings: Settings = Settings()) -> str:
    try:
        return _STATIC_CLASSIFICATIONS[base]
    except KeyError:
        pass

    if base in settings.unclassifiable_application_modules:
        return Classified.APPLICATION
    elif base in _BUILTIN_MODS:
        return Classified.BUILTIN

    app = _get_app(settings.application_directories)

    if _find_local(app, base):
        return Classified.APPLICATION
    elif find_spec(base) is not None:  # pragma: <3.10 cover
        spec = find_spec(base)
        if spec and spec.origin and spec.origin.startswith(_STDLIB_PATH) \
                and not spec.origin.rstrip('/\\').endswith('-packages'):
            return Classified.BUILTIN
    return Classified.THIRD_PARTY


def _ast_alias_to_s(node: ast.alias) -> str:
    if node.asname:
        return f'{node.name} as {node.asname}'
    else:
        return node.name


class ImportKey(NamedTuple):
    module: str
    asname: str


class Import:
    def __init__(self, node: ast.Import) -> None:
        self.node = node
        self.is_multiple = len(node.names) > 1

    @property
    def module(self) -> str:
        return self.node.names[0].name

    @property
    def module_base(self) -> str:
        return self.module.partition('.')[0]

    @cached_property
    def key(self) -> ImportKey:
        alias = self.node.names[0]
        return ImportKey(alias.name, alias.asname or '')

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Import) and self.key == other.key

    @property
    def sort_key(self) -> tuple[str, str, str, str, str]:
        name, asname = self.key
        return ('0', name.lower(), asname.lower(), name, asname)

    def split(self) -> Generator[Import, None, None]:
        if not self.is_multiple:
            yield self
        else:
            for name in self.node.names:
                yield type(self)(ast.Import(names=[name]))

    def __str__(self) -> str:
        assert not self.is_multiple
        return f'import {_ast_alias_to_s(self.node.names[0])}\n'

    def __repr__(self) -> str:
        return f'import_obj_from_str({str(self)!r})'


class ImportFromKey(NamedTuple):
    module: str
    symbol: str
    asname: str


class ImportFrom:
    def __init__(self, node: ast.ImportFrom) -> None:
        self.node = node
        self.is_multiple = len(node.names) > 1

    @property
    def module(self) -> str:
        level = '.' * self.node.level  # local imports
        mod = self.node.module or ''  # from . import bar makes module `None`
        return f'{level}{mod}'

    @property
    def module_base(self) -> str:
        return self.module.partition('.')[0]

    @cached_property
    def key(self) -> ImportFromKey:
        alias = self.node.names[0]
        return ImportFromKey(self.module, alias.name, alias.asname or '')

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ImportFrom) and self.key == other.key

    @property
    def sort_key(self) -> tuple[str, str, str, str, str, str, str]:
        mod, name, asname = self.key
        return (
            '1',
            mod.lower(), name.lower(), asname.lower(),
            mod, name, asname,
        )

    def split(self) -> Generator[ImportFrom, None, None]:
        if not self.is_multiple:
            yield self
        else:
            for name in self.node.names:
                node = ast.ImportFrom(
                    module=self.node.module,
                    names=[name],
                    level=self.node.level,
                )
                yield type(self)(node)

    def __str__(self) -> str:
        assert not self.is_multiple
        return (
            f'from {self.module} '
            f'import {_ast_alias_to_s(self.node.names[0])}\n'
        )

    def __repr__(self) -> str:
        return f'import_obj_from_str({str(self)!r})'


_import_type = {ast.Import: Import, ast.ImportFrom: ImportFrom}


@functools.lru_cache(maxsize=None)
def import_obj_from_str(s: str) -> Import | ImportFrom:
    node = ast.parse(s, mode='single').body[0]
    return _import_type[type(node)](node)


def sort(
        imports: Iterable[Import | ImportFrom],
        settings: Settings = Settings(),
) -> tuple[tuple[Import | ImportFrom, ...], ...]:
    # Partition the imports
    imports_partitioned = collections.defaultdict(list)
    for obj in imports:
        tp = classify_base(obj.module_base, settings=settings)
        if tp is Classified.FUTURE and isinstance(obj, Import):
            tp = Classified.BUILTIN

        imports_partitioned[tp].append(obj)

    # sort each of the segments
    sortkey = operator.attrgetter('sort_key')
    for val in imports_partitioned.values():
        val.sort(key=sortkey)

    return tuple(
        tuple(imports_partitioned[key])
        for key in Classified.order if key in imports_partitioned
    )
