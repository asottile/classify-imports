from __future__ import annotations

import ast
from typing import NamedTuple
from typing import TypeVar
from typing import Union

from cached_property import cached_property

T = TypeVar('T')


def tuple_lower(t: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(s.lower() for s in t)


def _from_str(s: str, tp: type[T]) -> T:
    obj = ast.parse(s).body[0]
    if not isinstance(obj, tp):
        raise AssertionError(f'Expected ast of type {tp!r} but got {obj!r}')
    return obj


def _from_import_module(ast_obj: ast.ImportFrom) -> str:
    level_s = '.' * ast_obj.level  # local imports
    module_s = ast_obj.module or ''  # from . import bar makes module `None`
    return f'{level_s}{module_s}'


class ImportImportSortKey(NamedTuple):
    module: str
    asname: str

    @classmethod
    def from_python_ast(cls, ast_obj: ast.Import) -> ImportImportSortKey:
        return cls(ast_obj.names[0].name, ast_obj.names[0].asname or '')


class FromImportSortKey(NamedTuple):
    module: str
    symbol: str
    asname: str

    @classmethod
    def from_python_ast(cls, ast_obj: ast.ImportFrom) -> FromImportSortKey:
        return cls(
            _from_import_module(ast_obj),
            ast_obj.names[0].name,
            ast_obj.names[0].asname or '',
        )


def _ast_alias_to_s(ast_alias: ast.alias) -> str:
    if ast_alias.asname:
        return f'{ast_alias.name} as {ast_alias.asname}'
    else:
        return ast_alias.name


def _format_import_import(ast_aliases: list[ast.alias]) -> str:
    return 'import {}\n'.format(
        ', '.join(
            sorted(_ast_alias_to_s(ast_alias) for ast_alias in ast_aliases),
        ),
    )


class ImportImport:
    def __init__(self, ast_obj: ast.Import) -> None:
        self.ast_obj = ast_obj
        self.import_statement = ImportImportSortKey.from_python_ast(ast_obj)

    @classmethod
    def from_str(cls, s: str) -> ImportImport:
        return cls(_from_str(s, ast.Import))

    @property
    def is_explicit_relative(self) -> bool:
        return self.import_statement.module.startswith('.')

    @property
    def has_multiple_imports(self) -> bool:
        return len(self.ast_obj.names) > 1

    @cached_property
    def sort_key(self) -> tuple[str, ...]:
        return tuple_lower(self.import_statement) + self.import_statement

    def __lt__(self, other: ImportImport) -> bool:
        return self.sort_key < other.sort_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return self.import_statement == other.import_statement

    def __hash__(self) -> int:
        return hash(repr(self))

    def split_imports(self) -> list[ImportImport]:
        return [
            type(self).from_str(_format_import_import([ast_alias]))
            for ast_alias in self.ast_obj.names
        ]

    def to_text(self) -> str:
        return _format_import_import(self.ast_obj.names)

    def __repr__(self) -> str:
        return f'{type(self).__name__}.from_str({self.to_text()!r})'


def _format_from_import(module: str, ast_aliases: list[ast.alias]) -> str:
    return 'from {} import {}\n'.format(
        module,
        ', '.join(
            sorted(_ast_alias_to_s(ast_alias) for ast_alias in ast_aliases),
        ),
    )


class FromImport:
    def __init__(self, ast_obj: ast.ImportFrom) -> None:
        self.ast_obj = ast_obj
        self.import_statement = FromImportSortKey.from_python_ast(ast_obj)

    @classmethod
    def from_str(cls, s: str) -> FromImport:
        return cls(_from_str(s, ast.ImportFrom))

    @property
    def is_explicit_relative(self) -> bool:
        return self.import_statement.module.startswith('.')

    @property
    def has_multiple_imports(self) -> bool:
        return len(self.ast_obj.names) > 1

    def split_imports(self) -> list[FromImport]:
        return [
            type(self).from_str(
                _format_from_import(
                    _from_import_module(self.ast_obj), [ast_alias],
                ),
            )
            for ast_alias in self.ast_obj.names
        ]

    @cached_property
    def sort_key(self) -> tuple[str, ...]:
        return tuple_lower(self.import_statement) + self.import_statement

    def __lt__(self, other: ImportImport) -> bool:
        return self.sort_key < other.sort_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return self.import_statement == other.import_statement

    def __hash__(self) -> int:
        return hash(repr(self))

    def to_text(self) -> str:
        return _format_from_import(
            _from_import_module(self.ast_obj), self.ast_obj.names,
        )

    def __repr__(self) -> str:
        return f'{type(self).__name__}.from_str({self.to_text()!r})'


AbstractImportObj = Union['ImportImport', 'FromImport']


ast_type_to_import_type = {
    ast.Import: ImportImport, ast.ImportFrom: FromImport,
}


def import_obj_from_str(s: str) -> AbstractImportObj:
    """Returns an import object (either ImportImport or FromImport) from text.
    """
    ast_obj = ast.parse(s).body[0]
    return ast_type_to_import_type[type(ast_obj)](ast_obj)
