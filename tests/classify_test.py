import os
import os.path
import pytest
import sys

from aspy.refactor_imports.classify import classify_import
from aspy.refactor_imports.classify import ImportType


# pylint: disable=redefined-outer-name,unused-argument


@pytest.mark.parametrize(
    ('module', 'expected'),
    (
        ('os', ImportType.BUILTIN),
        ('random', ImportType.BUILTIN),
        ('sys', ImportType.BUILTIN),
        ('pyramid', ImportType.THIRD_PARTY),
        ('aspy.refactor_imports', ImportType.APPLICATION),
        ('.main_test', ImportType.APPLICATION),
    ),
)
def test_classify_import(module, expected):
    ret = classify_import(module)
    assert ret is expected


@pytest.yield_fixture
def in_tmpdir(tmpdir):
    old_path = os.getcwd()
    os.chdir(tmpdir.strpath)
    try:
        yield tmpdir.strpath
    finally:
        os.chdir(old_path)


def test_in_tmpdir(in_tmpdir):
    assert os.getcwd() == in_tmpdir


@pytest.yield_fixture
def no_empty_path():
    # Some of our tests check things based on their pwd where things aren't
    # necessarily importable.  Let's make them not actually importable.
    empty_in_path = '' in sys.path
    if empty_in_path:  # pragma: no cover (depends on running conditions)
        # We're going to assume it is at the beginning
        sys.path.remove('')
        yield
        sys.path.insert(0, '')
    else:  # pragma: no cover (depend on running conditions)
        # noop
        yield


def test_symlink_path_different(in_tmpdir, no_empty_path):
    # symlink a file, these are likely to not be application files
    open('dest_file.py', 'w').close()
    os.symlink('dest_file.py', 'src_file.py')
    ret = classify_import('src_file')
    assert ret is ImportType.THIRD_PARTY


def test_file_existing_is_application_level(in_tmpdir, no_empty_path):
    open('my_file.py', 'w').close()
    ret = classify_import('my_file')
    assert ret is ImportType.APPLICATION


def test_package_existing_is_application_level(in_tmpdir, no_empty_path):
    os.mkdir('my_package')
    open(os.path.join('my_package', '__init__.py'), 'w').close()
    ret = classify_import('my_package')
    assert ret is ImportType.APPLICATION
