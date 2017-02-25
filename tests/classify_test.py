import contextlib
import os.path
import sys

import mock
import pytest

from aspy.refactor_imports.classify import classify_import
from aspy.refactor_imports.classify import ImportType


@pytest.mark.parametrize(
    ('module', 'expected'),
    (
        ('__future__', ImportType.FUTURE),
        ('os', ImportType.BUILTIN),
        ('random', ImportType.BUILTIN),
        ('sys', ImportType.BUILTIN),
        ('cached_property', ImportType.THIRD_PARTY),
        ('pyramid', ImportType.THIRD_PARTY),
        ('aspy.refactor_imports', ImportType.APPLICATION),
        ('.main_test', ImportType.APPLICATION),
    ),
)
def test_classify_import(module, expected):
    ret = classify_import(module)
    assert ret is expected


@pytest.mark.xfail(
    os.name == 'nt',
    reason='Expected fail for no symlink support',
)
def test_symlink_path_different(in_tmpdir, no_empty_path):  # pragma: no cover
    # symlink a file, these are likely to not be application files
    open('dest_file.py', 'w').close()
    os.symlink('dest_file.py', 'src_file.py')
    ret = classify_import('src_file')
    assert ret is ImportType.THIRD_PARTY


@contextlib.contextmanager
def in_sys_path_and_pythonpath(pth):
    paths = [os.path.abspath(p) for p in pth.split(os.pathsep)]

    path_before = sys.path[:]
    sys.path[:] = paths + path_before
    try:
        with mock.patch.dict(os.environ, {'PYTHONPATH': pth}):
            yield
    finally:
        sys.path[:] = path_before


def test_classify_pythonpath_third_party(in_tmpdir):
    in_tmpdir.join('ppth').ensure_dir().join('f.py').ensure()
    with in_sys_path_and_pythonpath('ppth'):
        assert classify_import('f') is ImportType.THIRD_PARTY


def test_classify_pythonpath_dot_app(in_tmpdir):
    in_tmpdir.join('f.py').ensure()
    with in_sys_path_and_pythonpath('.'):
        assert classify_import('f') is ImportType.APPLICATION


def test_classify_pythonpath_multiple(in_tmpdir):
    in_tmpdir.join('ppth').ensure_dir().join('f.py').ensure()
    with in_sys_path_and_pythonpath(os.pathsep.join(('ppth', 'foo'))):
        assert classify_import('f') is ImportType.THIRD_PARTY


def test_file_existing_is_application_level(in_tmpdir, no_empty_path):
    open('my_file.py', 'w').close()
    ret = classify_import('my_file')
    assert ret is ImportType.APPLICATION


def test_package_existing_is_application_level(in_tmpdir, no_empty_path):
    os.mkdir('my_package')
    open(os.path.join('my_package', '__init__.py'), 'w').close()
    ret = classify_import('my_package')
    assert ret is ImportType.APPLICATION


def test_empty_directory_is_not_package(in_tmpdir, no_empty_path):
    os.mkdir('my_package')
    ret = classify_import('my_package')
    assert ret is ImportType.THIRD_PARTY


def test_application_directories(in_tmpdir, no_empty_path):
    # Similar to @bukzor's testing setup
    os.makedirs('tests/testing')
    open('tests/testing/__init__.py', 'w').close()
    # Should be classified 3rd party without argument
    ret = classify_import('testing')
    assert ret is ImportType.THIRD_PARTY
    # Should be application with extra directories
    ret = classify_import('testing', application_directories=('.', 'tests'))
    assert ret is ImportType.APPLICATION
