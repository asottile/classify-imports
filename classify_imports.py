from __future__ import annotations

import ast
import collections
import enum
import functools
import importlib.util
import os.path
import sys
import zipimport
from typing import Generator
from typing import Iterable
from typing import NamedTuple

if sys.version_info >= (3, 8):  # pragma: >=3.8 cover
    from functools import cached_property
else:  # pragma: <3.8 cover
    cached_property = property

Classified = enum.Enum('Classified', 'FUTURE BUILTIN THIRD_PARTY APPLICATION')


def _pythonpath_dirs() -> set[str]:
    if 'PYTHONPATH' not in os.environ:
        return set()

    splitpath = os.environ['PYTHONPATH'].split(os.pathsep)
    return {os.path.realpath(p) for p in splitpath} - {os.path.realpath('.')}


def _due_to_pythonpath(module_path: str) -> bool:
    mod_dir, _ = os.path.split(os.path.realpath(module_path))
    return mod_dir in _pythonpath_dirs()


def _samedrive(path1: str, path2: str) -> bool:
    drive1, _ = os.path.splitdrive(path1)
    drive2, _ = os.path.splitdrive(path2)
    return drive1.upper() == drive2.upper()


def _normcase_equal(path1: str, path2: str) -> bool:
    return os.path.normcase(path1) == os.path.normcase(path2)


def _has_path_prefix(path: str, *, prefix: str) -> bool:
    # Both paths are assumed to be absolute.
    return (
        _samedrive(path, prefix) and
        _normcase_equal(prefix, os.path.commonpath((path, prefix)))
    )


def _module_path_is_local_and_is_not_symlinked(
        module_path: str, application_directories: tuple[str, ...],
) -> bool:
    def _is_a_local_path(potential_path: str) -> bool:
        localpath = os.path.abspath(potential_path)
        abspath = os.path.abspath(module_path)
        realpath = os.path.realpath(module_path)
        return (
            _has_path_prefix(abspath, prefix=localpath) and
            # It's possible (and surprisingly likely) that the consumer has a
            # virtualenv inside the project directory.  We'd like to still
            # consider things in the virtualenv as third party.
            os.sep not in abspath[len(localpath) + 1:] and
            _normcase_equal(abspath, realpath) and
            os.path.exists(realpath)
        )

    return any(_is_a_local_path(path) for path in application_directories)


def _find_local(
        module_name: str,
        application_directories: tuple[str, ...],
) -> str:
    for local_path in application_directories:
        pkg_path = os.path.join(local_path, module_name)
        mod_path = os.path.join(local_path, module_name + '.py')
        if os.path.isdir(pkg_path) and os.listdir(pkg_path):
            return pkg_path
        elif os.path.exists(mod_path):
            return mod_path
    else:
        # We did not find a local file that looked like the module
        return module_name + '.notlocal'


def _get_module_info(
        module_name: str,
        application_dirs: tuple[str, ...],
) -> tuple[bool, str, bool]:
    if module_name in sys.builtin_module_names:
        return True, '(builtin)', True

    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False, _find_local(module_name, application_dirs), False
    # namespace packages
    elif spec.origin is None:
        assert spec.submodule_search_locations is not None
        return True, next(iter(spec.submodule_search_locations)), False
    elif isinstance(spec.loader, zipimport.zipimporter):
        return True, spec.origin, False
    elif os.path.split(spec.origin)[1] == '__init__.py':
        return True, os.path.dirname(spec.origin), False
    else:
        return True, spec.origin, False


PACKAGES_PATH = '-packages' + os.sep


class Settings(NamedTuple):
    application_directories: tuple[str, ...] = ('.',)
    unclassifiable_application_modules: frozenset[str] = frozenset()


@functools.lru_cache(maxsize=None)
def classify_base(
        base: str,
        settings: Settings = Settings(),
) -> Classified:
    if base == '__future__':
        return Classified.FUTURE
    elif base == '__main__':
        return Classified.APPLICATION
    # force distutils to be "third party" after being gobbled by setuptools
    elif base == 'distutils':
        return Classified.THIRD_PARTY
    elif base in settings.unclassifiable_application_modules:
        return Classified.APPLICATION
    # relative imports: `from .foo import bar`
    elif base == '':
        return Classified.APPLICATION

    found, module_path, is_builtin = _get_module_info(
        base, settings.application_directories,
    )

    # if the import system tells us it is builtin, it is builtin
    if is_builtin:
        return Classified.BUILTIN
    # if the module path exists in the project directories
    elif _module_path_is_local_and_is_not_symlinked(
            module_path, settings.application_directories,
    ):
        return Classified.APPLICATION
    # Otherwise we assume it is a system module or a third party module
    elif (
            found and
            PACKAGES_PATH not in module_path and
            not _due_to_pythonpath(module_path)
    ):
        return Classified.BUILTIN
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


class Import:
    def __init__(self, node: ast.Import) -> None:
        self.node = node

    @property
    def is_multiple(self) -> bool:
        return len(self.node.names) > 1

    @property
    def module(self) -> str:
        return self.node.names[0].name

    @property
    def module_base(self) -> str:
        return self.module.split('.')[0]

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

    @property
    def is_multiple(self) -> bool:
        return len(self.node.names) > 1

    @property
    def module(self) -> str:
        level = '.' * self.node.level  # local imports
        mod = self.node.module or ''  # from . import bar makes module `None`
        return f'{level}{mod}'

    @property
    def module_base(self) -> str:
        return self.module.split('.')[0]

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
    node = ast.parse(s).body[0]
    return _import_type[type(node)](node)


def sort(
        imports: Iterable[Import | ImportFrom],
        settings: Settings = Settings(),
) -> tuple[tuple[Import | ImportFrom, ...], ...]:
    # Partition the imports
    imports_partitioned: dict[Classified, list[Import | ImportFrom]]
    imports_partitioned = collections.defaultdict(list)
    for obj in imports:
        tp = classify_base(obj.module_base, settings=settings)
        if tp is Classified.FUTURE and isinstance(obj, Import):
            tp = Classified.BUILTIN

        imports_partitioned[tp].append(obj)

    # sort each of the segments
    for val in imports_partitioned.values():
        val.sort(key=lambda obj: obj.sort_key)

    return tuple(
        tuple(imports_partitioned[key])
        for key in Classified if key in imports_partitioned
    )
