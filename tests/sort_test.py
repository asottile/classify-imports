from __future__ import absolute_import
from __future__ import unicode_literals

from aspy.refactor_imports.import_obj import FromImport
from aspy.refactor_imports.import_obj import ImportImport
from aspy.refactor_imports.sort import sort


IMPORTS = (
    FromImport.from_str('from os import path'),
    FromImport.from_str('from aspy import refactor_imports'),
    ImportImport.from_str('import sys'),
    ImportImport.from_str('import pyramid'),
)


def test_separate_import_before_from():
    ret = sort(IMPORTS, separate=True, import_before_from=True)
    assert ret == (
        (
            ImportImport.from_str('import sys'),
            FromImport.from_str('from os import path'),
        ),
        (
            ImportImport.from_str('import pyramid'),
        ),
        (
            FromImport.from_str('from aspy import refactor_imports'),
        ),
    )


def test_separate_not_import_before_from():
    ret = sort(IMPORTS, separate=True, import_before_from=False)
    assert ret == (
        (
            FromImport.from_str('from os import path'),
            ImportImport.from_str('import sys'),
        ),
        (
            ImportImport.from_str('import pyramid'),
        ),
        (
            FromImport.from_str('from aspy import refactor_imports'),
        ),
    )


def test_not_separate_import_before_from():
    ret = sort(IMPORTS, separate=False, import_before_from=True)
    assert ret == (
        (
            ImportImport.from_str('import pyramid'),
            ImportImport.from_str('import sys'),
            FromImport.from_str('from aspy import refactor_imports'),
            FromImport.from_str('from os import path'),
        ),
    )


def test_not_separate_not_import_before_from():
    ret = sort(IMPORTS, separate=False, import_before_from=False)
    assert ret == (
        (
            FromImport.from_str('from aspy import refactor_imports'),
            FromImport.from_str('from os import path'),
            ImportImport.from_str('import pyramid'),
            ImportImport.from_str('import sys'),
        ),
    )


def test_future_separate_block_non_separate():
    ret = sort(
        (
            FromImport.from_str('from __future__ import absolute_import'),
            ImportImport.from_str('import pyramid'),
        ),
        separate=False,
        import_before_from=True,
    )
    assert ret == (
        (FromImport.from_str('from __future__ import absolute_import'),),
        (ImportImport.from_str('import pyramid'),),
    )
