from __future__ import annotations

import contextlib
import os.path
import subprocess
import sys
import zipfile
from unittest import mock

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
        ('__main__', ImportType.APPLICATION),
    ),
)
def test_classify_import(module, expected):
    ret = classify_import(module)
    assert ret is expected


def test_spec_is_none():
    """for __main__ in a subprocess, spec is None and raises an error"""
    prog = '''\
import __main__
from aspy.refactor_imports.classify import classify_import, ImportType
assert __main__.__spec__ is None, __main__.__spec__
tp = classify_import('__main__')
assert tp == ImportType.APPLICATION, tp
'''
    subprocess.check_call((sys.executable, '-c', prog))

    # simulate this situation for coverage
    with mock.patch.object(sys.modules['__main__'], '__spec__', None):
        assert classify_import('__main__') == ImportType.APPLICATION


def test_true_namespace_package(tmpdir):
    site_packages = tmpdir.join('site-packages')
    site_packages.join('a').ensure_dir()
    sys_path = [site_packages.strpath] + sys.path
    with mock.patch.object(sys, 'path', sys_path):
        # while this is a py3+ feature, aspy.refactor_imports happens to get
        # this correct anyway!
        assert classify_import('a') == ImportType.THIRD_PARTY


@pytest.mark.xfail(  # pragma: win32 no cover
    sys.platform == 'win32',
    reason='Expected fail for no symlink support',
)
def test_symlink_path_different(in_tmpdir, no_empty_path):
    # symlink a file, these are likely to not be application files
    in_tmpdir.join('dest_file.py').ensure()
    in_tmpdir.join('src_file.py').mksymlinkto('dest-file.py')
    ret = classify_import('src_file')
    assert ret is ImportType.THIRD_PARTY


@contextlib.contextmanager
def in_sys_path(pth):
    paths = [os.path.abspath(p) for p in pth.split(os.pathsep)]

    path_before = sys.path[:]
    sys.path[:] = paths + path_before
    try:
        yield
    finally:
        sys.path[:] = path_before


@contextlib.contextmanager
def in_sys_path_and_pythonpath(pth):
    with in_sys_path(pth), mock.patch.dict(os.environ, {'PYTHONPATH': pth}):
        yield


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


def test_classify_pythonpath_zipimport(in_tmpdir):
    path_zip = in_tmpdir.join('ppth').ensure_dir().join('fzip.zip')
    with zipfile.ZipFile(str(path_zip), 'w') as fzip:
        fzip.writestr('fzip.py', '')
    with in_sys_path_and_pythonpath('ppth/fzip.zip'):
        assert classify_import('fzip') is ImportType.THIRD_PARTY


def test_classify_embedded_builtin(in_tmpdir):
    path_zip = in_tmpdir.join('ppth').ensure_dir().join('fzip.zip')
    with zipfile.ZipFile(str(path_zip), 'w') as fzip:
        fzip.writestr('fzip.py', '')
    with in_sys_path('ppth/fzip.zip'):
        assert classify_import('fzip') is ImportType.BUILTIN


def test_file_existing_is_application_level(in_tmpdir, no_empty_path):
    in_tmpdir.join('my_file.py').ensure()
    ret = classify_import('my_file')
    assert ret is ImportType.APPLICATION


def test_package_existing_is_application_level(in_tmpdir, no_empty_path):
    in_tmpdir.join('my_package').ensure_dir().join('__init__.py').ensure()
    ret = classify_import('my_package')
    assert ret is ImportType.APPLICATION


def test_empty_directory_is_not_package(in_tmpdir, no_empty_path):
    in_tmpdir.join('my_package').ensure_dir()
    ret = classify_import('my_package')
    assert ret is ImportType.THIRD_PARTY


def test_application_directories(in_tmpdir, no_empty_path):
    # Similar to @bukzor's testing setup
    in_tmpdir.join('tests/testing').ensure_dir().join('__init__.py').ensure()
    # Should be classified 3rd party without argument
    ret = classify_import('testing')
    assert ret is ImportType.THIRD_PARTY
    # Should be application with extra directories
    ret = classify_import('testing', application_directories=('.', 'tests'))
    assert ret is ImportType.APPLICATION


def test_application_directory_case(in_tmpdir, no_empty_path):
    srcdir = in_tmpdir.join('SRC').ensure_dir()
    if in_tmpdir.join('src').exists():
        raise pytest.skip('requires case sensitive filesystem')

    srcdir.join('my_package').ensure_dir().join('__init__.py').ensure()
    with in_sys_path('src'):
        ret = classify_import('my_package', application_directories=('SRC',))
    assert ret is ImportType.APPLICATION


def test_unclassifiable_application_modules():
    # Should be classified 3rd party without argument
    ret = classify_import('c_module')
    assert ret is ImportType.THIRD_PARTY
    # Should be classified application with the override
    ret = classify_import(
        'c_module', unclassifiable_application_modules=('c_module',),
    )
    assert ret is ImportType.APPLICATION


def test_unclassifiable_application_modules_ignores_future():
    # Trying to force __future__ to be APPLICATION shouldn't have any effect
    ret = classify_import(
        '__future__', unclassifiable_application_modules=('__future__',),
    )
    assert ret is ImportType.FUTURE
