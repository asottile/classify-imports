from __future__ import annotations

import ast
import collections
import functools
import operator
import os.path
import stat
import sys
from collections.abc import Generator
from collections.abc import Iterable
from typing import NamedTuple


if sys.version_info < (3, 14):  # pragma: <3.14 cover
    def import_replace(o: ast.Import, *, names: list[ast.alias]) -> ast.Import:
        return ast.Import(names=names)

    def import_from_replace(
            o: ast.ImportFrom,
            *,
            module: str | None = None,
            names: list[ast.alias] | None = None,
    ) -> ast.ImportFrom:
        return ast.ImportFrom(
            module=o.module if module is None else module,
            names=o.names if names is None else names,
            level=o.level,
        )
else:  # pragma: >=3.14 cover
    import_replace = ast.Import.__replace__
    import_from_replace = ast.ImportFrom.__replace__


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


@functools.cache
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


@functools.cache
def classify_base(base: str, settings: Settings = Settings()) -> str:
    try:
        return _STATIC_CLASSIFICATIONS[base]
    except KeyError:
        pass

    if base in sys.stdlib_module_names:
        return Classified.BUILTIN
    elif (
            base in settings.unclassifiable_application_modules or
            _find_local(_get_app(settings.application_directories), base)
    ):
        return Classified.APPLICATION
    else:
        return Classified.THIRD_PARTY


def _ast_alias_to_s(node: ast.alias) -> str:
    if node.asname:
        return f'{node.name} as {node.asname}'
    else:
        return node.name


class ImportKey(NamedTuple):
    module: str
    asname: str


class ImportKeyWithLazy(NamedTuple):
    module: str
    asname: str
    lazy: int


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

    @functools.cached_property
    def lazy(self) -> int:
        return getattr(self.node, 'is_lazy', 0)

    @functools.cached_property
    def key(self) -> ImportKey:  # pragma: no cover (deprecated)
        import warnings

        warnings.warn(
            'use key_with_lazy instead',
            DeprecationWarning,
            stacklevel=2,
        )

        alias = self.node.names[0]
        return ImportKey(alias.name, alias.asname or '')

    @functools.cached_property
    def key_with_lazy(self) -> ImportKeyWithLazy:
        alias = self.node.names[0]
        return ImportKeyWithLazy(alias.name, alias.asname or '', self.lazy)

    def __hash__(self) -> int:
        return hash(self.key_with_lazy)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Import) and
            self.key_with_lazy == other.key_with_lazy
        )

    @property
    def sort_key(self) -> tuple[str, ...]:
        name, asname, lazy = self.key_with_lazy
        return (
            str(lazy),
            '0',
            name.lower(), asname.lower(),
            name, asname,
        )

    def split(self) -> Generator[Import]:
        if not self.is_multiple:
            yield self
        else:
            for name in self.node.names:
                yield type(self)(import_replace(self.node, names=[name]))

    def __str__(self) -> str:
        lazy = 'lazy ' if self.lazy else ''
        assert not self.is_multiple
        return f'{lazy}import {_ast_alias_to_s(self.node.names[0])}\n'

    def __repr__(self) -> str:
        return f'import_obj_from_str({str(self)!r})'


class ImportFromKey(NamedTuple):
    module: str
    symbol: str
    asname: str


class ImportFromKeyWithLazy(NamedTuple):
    module: str
    symbol: str
    asname: str
    lazy: int


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

    @functools.cached_property
    def lazy(self) -> int:
        return getattr(self.node, 'is_lazy', 0)

    @functools.cached_property
    def key(self) -> ImportFromKey:  # pragma: no cover (deprecated)
        import warnings

        warnings.warn(
            'use key_with_lazy instead',
            DeprecationWarning,
            stacklevel=2,
        )

        alias = self.node.names[0]
        return ImportFromKey(self.module, alias.name, alias.asname or '')

    @functools.cached_property
    def key_with_lazy(self) -> ImportFromKeyWithLazy:
        alias = self.node.names[0]
        return ImportFromKeyWithLazy(
            self.module, alias.name, alias.asname or '', self.lazy,
        )

    def __hash__(self) -> int:
        return hash(self.key_with_lazy)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ImportFrom) and
            self.key_with_lazy == other.key_with_lazy
        )

    @property
    def sort_key(self) -> tuple[str, ...]:
        mod, name, asname, lazy = self.key_with_lazy
        return (
            str(lazy),
            '1',
            mod.lower(), name.lower(), asname.lower(),
            mod, name, asname,
        )

    def split(self) -> Generator[ImportFrom]:
        if not self.is_multiple:
            yield self
        else:
            for name in self.node.names:
                node = import_from_replace(self.node, names=[name])
                yield type(self)(node)

    def __str__(self) -> str:
        lazy = 'lazy ' if self.lazy else ''
        assert not self.is_multiple
        return (
            f'{lazy}from {self.module} '
            f'import {_ast_alias_to_s(self.node.names[0])}\n'
        )

    def __repr__(self) -> str:
        return f'import_obj_from_str({str(self)!r})'


_import_type = {ast.Import: Import, ast.ImportFrom: ImportFrom}


@functools.cache
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
