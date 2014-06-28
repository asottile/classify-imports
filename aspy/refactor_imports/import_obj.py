from __future__ import unicode_literals

import ast
import collections
from cached_property import cached_property

# pylint: disable=bad-continuation,protected-access


def namedtuple_lower(t):
    """Lower cases a namedtuple"""
    return type(t)(*[s.lower() for s in t])


class AbstractImportObj(object):
    # The import object should expect a given AST object type
    _expected_ast_type = NotImplemented

    # The import object should have an import sort key type
    # This type should have a `from_ast_obj` factory method
    _sort_key_type = NotImplemented

    def __init__(self, ast_obj):
        self.ast_obj = ast_obj

    @classmethod
    def from_str(cls, s):
        """Construct an import object from a string."""
        ast_obj = ast.parse(s).body[0]
        if not isinstance(ast_obj, cls._expected_ast_type):
            raise AssertionError(
                'Expected ast of type {0!r} but got {1!r}'.format(
                    cls._expected_ast_type,
                    ast_obj
                )
            )
        return cls(ast_obj)

    @cached_property
    def import_statement(self):
        """Return a namedtuple representing this import."""
        return self._sort_key_type.from_python_ast(self.ast_obj)

    @cached_property
    def _sort_key(self):
        return namedtuple_lower(self.import_statement)

    def __lt__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return self._sort_key < other._sort_key

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return self._sort_key == other._sort_key

    @cached_property
    def has_multiple_imports(self):
        """Return whether the import represents multiple imports.

        For instance `import os, sys` does, but `import functools` does not
        """
        return len(self.ast_obj.names) > 1

    def split_imports(self):
        """Return an iterable of imports that result from taking each of the
        multiple imports and making a new import object for each of them.

        For instance:

        >>> ImportImport.from_str('import sys, os').split_imports()
        [ImportImport('import sys'), ImportImport('import os')]
        """
        raise NotImplementedError

    def to_text(self):
        """Return a string representation terminated by a newline."""
        raise NotImplementedError


def _check_only_one_name(ast_import):
    if len(ast_import.names) != 1:
        raise AssertionError(
            'Cannot construct import with multiple names: {0!r}'.format(
                ast_import,
            )
        )


class ImportImportSortKey(collections.namedtuple(
    'ImportImportSortKey', ['module', 'asname'],
)):
    __slots__ = ()

    @classmethod
    def from_python_ast(cls, ast_import):
        _check_only_one_name(ast_import)
        return cls(ast_import.names[0].name, ast_import.names[0].asname or '')


class FromImportSortKey(collections.namedtuple(
    'FromImportSortKey', ['module', 'symbol', 'asname'],
)):
    __slots__ = ()

    @classmethod
    def from_python_ast(cls, ast_import):
        _check_only_one_name(ast_import)
        return cls(
            ast_import.module,
            ast_import.names[0].name,
            ast_import.names[0].asname or '',
        )


def _ast_alias_to_s(ast_alias):
    if ast_alias.asname:
        return '{0} as {1}'.format(ast_alias.name, ast_alias.asname)
    else:
        return ast_alias.name


def _format_import_import(ast_alias):
    return 'import {0}\n'.format(_ast_alias_to_s(ast_alias))


class ImportImport(AbstractImportObj):
    _expected_ast_type = ast.Import
    _sort_key_type = ImportImportSortKey

    def split_imports(self):
        return [
            type(self).from_str(_format_import_import(ast_alias))
            for ast_alias in self.ast_obj.names
        ]

    def to_text(self):
        if self.has_multiple_imports:
            raise AssertionError('Cannot format multiple imports')
        return _format_import_import(self.ast_obj.names[0])


def _format_from_import(module, ast_alias):
    return 'from {0} import {1}\n'.format(module, _ast_alias_to_s(ast_alias))


class FromImport(AbstractImportObj):
    _expected_ast_type = ast.ImportFrom
    _sort_key_type = FromImportSortKey

    def split_imports(self):
        return [
            type(self).from_str(_format_from_import(
                self.ast_obj.module, ast_alias,
            ))
            for ast_alias in self.ast_obj.names
        ]

    def to_text(self):
        if self.has_multiple_imports:
            raise AssertionError('Cannot format multiple imports')
        return _format_from_import(
            self.ast_obj.module, self.ast_obj.names[0],
        )
