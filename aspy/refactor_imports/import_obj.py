# pylint: disable=bad-continuation,protected-access
from __future__ import unicode_literals

import ast
import collections

from cached_property import cached_property


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
    def sort_key(self):
        return namedtuple_lower(self.import_statement) + self.import_statement

    def __lt__(self, other):
        return self.sort_key < other.sort_key

    def __eq__(self, other):
        return self.sort_key == other.sort_key

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.to_text())

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

    def __repr__(self):
        return '{0}.from_str({1!r})'.format(type(self).__name__, self.to_text())


def _from_import_module(ast_import):
    return '{0}{1}'.format(
        # Handle local imports
        '.' * ast_import.level,
        # from . import bar makes module `None`
        ast_import.module or '',
    )


class ImportImportSortKey(collections.namedtuple(
    'ImportImportSortKey', ['module', 'asname'],
)):
    __slots__ = ()

    @classmethod
    def from_python_ast(cls, ast_import):
        return cls(ast_import.names[0].name, ast_import.names[0].asname or '')


class FromImportSortKey(collections.namedtuple(
    'FromImportSortKey', ['module', 'symbol', 'asname'],
)):
    __slots__ = ()

    @classmethod
    def from_python_ast(cls, ast_import):
        return cls(
            _from_import_module(ast_import),
            ast_import.names[0].name,
            ast_import.names[0].asname or '',
        )


def _ast_alias_to_s(ast_alias):
    if ast_alias.asname:
        return '{0} as {1}'.format(ast_alias.name, ast_alias.asname)
    else:
        return ast_alias.name


def _format_import_import(ast_aliases):
    return 'import {0}\n'.format(
        ', '.join(
            sorted(_ast_alias_to_s(ast_alias) for ast_alias in ast_aliases)
        ),
    )


class ImportImport(AbstractImportObj):
    _expected_ast_type = ast.Import
    _sort_key_type = ImportImportSortKey

    def split_imports(self):
        return [
            type(self).from_str(_format_import_import([ast_alias]))
            for ast_alias in self.ast_obj.names
        ]

    def to_text(self):
        return _format_import_import(self.ast_obj.names)


def _format_from_import(module, ast_aliases):
    return 'from {0} import {1}\n'.format(
        module,
        ', '.join(
            sorted(_ast_alias_to_s(ast_alias) for ast_alias in ast_aliases)
        ),
    )


class FromImport(AbstractImportObj):
    _expected_ast_type = ast.ImportFrom
    _sort_key_type = FromImportSortKey

    def split_imports(self):
        return [
            type(self).from_str(_format_from_import(
                self.ast_obj.module, [ast_alias],
            ))
            for ast_alias in self.ast_obj.names
        ]

    def to_text(self):
        return _format_from_import(
            _from_import_module(self.ast_obj), self.ast_obj.names,
        )


ast_type_to_import_type = dict(
    (t._expected_ast_type, t) for t in (ImportImport, FromImport)
)


def import_obj_from_str(s):
    """Returns an import object (either ImportImport or FromImport) from text.
    """
    ast_obj = ast.parse(s).body[0]
    return ast_type_to_import_type[type(ast_obj)](ast_obj)
