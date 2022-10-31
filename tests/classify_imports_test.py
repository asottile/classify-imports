from __future__ import annotations

import ast
import contextlib
import os.path
import subprocess
import sys
import zipfile
from unittest import mock

import pytest

from classify_imports import _get_app
from classify_imports import Classified
from classify_imports import classify_base
from classify_imports import import_obj_from_str
from classify_imports import ImportFromKey
from classify_imports import ImportKey
from classify_imports import Settings
from classify_imports import sort


@pytest.fixture(autouse=True)
def no_warnings(recwarn):
    yield
    assert len(recwarn) == 0


@pytest.fixture(autouse=True)
def no_empty_path():
    # Some of our tests check things based on their pwd where things aren't
    # necessarily importable.  Let's make them not actually importable.
    with contextlib.suppress(ValueError):
        sys.path.remove('')


@pytest.fixture(autouse=True)
def reset_caches():
    classify_base.cache_clear()
    _get_app.cache_clear()


@pytest.fixture
def in_tmpdir(tmpdir):
    with tmpdir.as_cwd():
        yield tmpdir


def test_get_app_removes_duplicate_app_dirs(tmpdir):
    d1 = tmpdir.join('d1').ensure_dir()
    app = _get_app((str(d1), str(d1)))
    assert app == (str(d1),)


def test_get_app_removes_non_existent_app_dirs(tmpdir):
    d1 = tmpdir.join('d1').ensure_dir()
    d2 = tmpdir.join('d2')
    app = _get_app((str(d1), str(d2)))
    assert app == (str(d1),)


@pytest.mark.parametrize(
    ('module', 'expected'),
    (
        ('__future__', Classified.FUTURE),
        ('os', Classified.BUILTIN),
        ('random', Classified.BUILTIN),
        ('sys', Classified.BUILTIN),
        ('cached_property', Classified.THIRD_PARTY),
        ('pyramid', Classified.THIRD_PARTY),
        ('classify_imports', Classified.APPLICATION),
        ('', Classified.APPLICATION),
        ('__main__', Classified.APPLICATION),
        ('tests', Classified.APPLICATION),
        pytest.param(
            'distutils', Classified.THIRD_PARTY,
            id='force setuptools-distutils detection',
        ),
    ),
)
def test_classify_base(module, expected):
    ret = classify_base(module)
    assert ret is expected


def test_spec_is_none():
    """for __main__ in a subprocess, spec is None and raises an error"""
    prog = '''\
import __main__
from classify_imports import classify_base, Classified
assert __main__.__spec__ is None, __main__.__spec__
tp = classify_base('__main__')
assert tp == Classified.APPLICATION, tp
'''
    subprocess.check_call((sys.executable, '-c', prog))

    # simulate this situation for coverage
    with mock.patch.object(sys.modules['__main__'], '__spec__', None):
        assert classify_base('__main__') == Classified.APPLICATION


def test_true_namespace_package(tmpdir):
    site_packages = tmpdir.join('site-packages')
    site_packages.join('a').ensure_dir()
    sys_path = [site_packages.strpath] + sys.path
    with mock.patch.object(sys, 'path', sys_path):
        # while this is a py3+ feature, classify_imports happens to get
        # this correct anyway!
        assert classify_base('a') == Classified.THIRD_PARTY


xfail_win32 = pytest.mark.xfail(sys.platform == 'win32', reason='symlinks')


@xfail_win32  # pragma: win32 no cover
def test_symlink_path_different(in_tmpdir):
    # symlink a file, these are likely to not be application files
    in_tmpdir.join('dest_file.py').ensure()
    in_tmpdir.join('src_file.py').mksymlinkto('dest-file.py')
    ret = classify_base('src_file')
    assert ret is Classified.THIRD_PARTY


@xfail_win32  # pragma: win32 no cover
def test_symlink_path_directory(in_tmpdir):
    # symlink a dir, these are likely to not be application files
    in_tmpdir.join('dest').ensure_dir()
    in_tmpdir.join('dest/t.py').ensure()
    in_tmpdir.join('srcmod').mksymlinkto('dest')
    ret = classify_base('srcmod')
    assert ret is Classified.THIRD_PARTY


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
        assert classify_base('f') is Classified.THIRD_PARTY


def test_classify_pythonpath_dot_app(in_tmpdir):
    in_tmpdir.join('f.py').ensure()
    with in_sys_path_and_pythonpath('.'):
        assert classify_base('f') is Classified.APPLICATION


def test_classify_pythonpath_multiple(in_tmpdir):
    in_tmpdir.join('ppth').ensure_dir().join('f.py').ensure()
    with in_sys_path_and_pythonpath(os.pathsep.join(('ppth', 'foo'))):
        assert classify_base('f') is Classified.THIRD_PARTY


def test_classify_pythonpath_zipimport(in_tmpdir):
    path_zip = in_tmpdir.join('ppth').ensure_dir().join('fzip.zip')
    with zipfile.ZipFile(str(path_zip), 'w') as fzip:
        fzip.writestr('fzip.py', '')
    with in_sys_path_and_pythonpath('ppth/fzip.zip'):
        assert classify_base('fzip') is Classified.THIRD_PARTY


def test_classify_embedded_builtin(in_tmpdir):
    path_zip = in_tmpdir.join('ppth').ensure_dir().join('fzip.zip')
    with zipfile.ZipFile(str(path_zip), 'w') as fzip:
        fzip.writestr('fzip.py', '')
    with in_sys_path('ppth/fzip.zip'):
        assert classify_base('fzip') is Classified.THIRD_PARTY


def test_file_existing_is_application_level(in_tmpdir):
    in_tmpdir.join('my_file.py').ensure()
    ret = classify_base('my_file')
    assert ret is Classified.APPLICATION


def test_package_existing_is_application_level(in_tmpdir):
    in_tmpdir.join('my_package').ensure_dir().join('__init__.py').ensure()
    ret = classify_base('my_package')
    assert ret is Classified.APPLICATION


def test_empty_directory_is_not_package(in_tmpdir):
    in_tmpdir.join('my_package').ensure_dir()
    ret = classify_base('my_package')
    assert ret is Classified.THIRD_PARTY


def test_application_directories(in_tmpdir):
    # Similar to @bukzor's testing setup
    in_tmpdir.join('tests/testing').ensure_dir().join('__init__.py').ensure()
    # Should be classified 3rd party without argument
    ret = classify_base('testing')
    assert ret is Classified.THIRD_PARTY
    # Should be application with extra directories
    ret = classify_base(
        'testing',
        settings=Settings(application_directories=('.', 'tests')),
    )
    assert ret is Classified.APPLICATION


def test_application_directory_case(in_tmpdir):
    srcdir = in_tmpdir.join('SRC').ensure_dir()
    srcdir.join('my_package').ensure_dir().join('__init__.py').ensure()
    with in_sys_path('src'):
        ret = classify_base(
            'my_package',
            settings=Settings(application_directories=('SRC',)),
        )
    assert ret is Classified.APPLICATION


def test_application_directories_empty(in_tmpdir):
    in_tmpdir.join('tests/testing').ensure_dir().join('__init__.py').ensure()
    # Should be classified 3rd party without argument
    ret = classify_base('testing')
    assert ret is Classified.THIRD_PARTY
    # Should be 3rd party if there are no application directories
    ret = classify_base(
        'testing',
        settings=Settings(application_directories=()),
    )
    assert ret is Classified.THIRD_PARTY


def test_unclassifiable_application_modules():
    # Should be classified 3rd party without argument
    ret = classify_base('c_module')
    assert ret is Classified.THIRD_PARTY
    # Should be classified application with the override
    ret = classify_base(
        'c_module',
        settings=Settings(
            unclassifiable_application_modules=frozenset(('c_module',)),
        ),
    )
    assert ret is Classified.APPLICATION


def test_unclassifiable_application_modules_builtin():
    # Should be classified builtin without argument
    ret = classify_base('os')
    assert ret is Classified.BUILTIN
    # Should be classified application with the override
    ret = classify_base(
        'os',
        settings=Settings(
            unclassifiable_application_modules=frozenset(('os',)),
        ),
    )
    assert ret is Classified.APPLICATION


def test_unclassifiable_application_modules_ignores_future():
    # Trying to force __future__ to be APPLICATION shouldn't have any effect
    ret = classify_base(
        '__future__',
        settings=Settings(
            unclassifiable_application_modules=frozenset(('__future__',)),
        ),
    )
    assert ret is Classified.FUTURE


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('from foo import bar', ImportFromKey('foo', 'bar', '')),
        ('from foo import bar as baz', ImportFromKey('foo', 'bar', 'baz')),
        ('from . import bar', ImportFromKey('.', 'bar', '')),
        ('from .foo import bar', ImportFromKey('.foo', 'bar', '')),
        ('from .. import bar', ImportFromKey('..', 'bar', '')),
        ('from ..foo import bar', ImportFromKey('..foo', 'bar', '')),
    ),
)
def test_from_import_key_from_python_ast(input_str, expected):
    assert import_obj_from_str(input_str).key == expected


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('import foo', ImportKey('foo', '')),
        ('import foo as bar', ImportKey('foo', 'bar')),
    ),
)
def test_import_import_sort_key_from_python_ast(input_str, expected):
    assert import_obj_from_str(input_str).key == expected


@pytest.fixture
def import_import():
    yield import_obj_from_str('import Foo as bar')


def test_import_import_node(import_import):
    assert type(import_import.node) == ast.Import


def test_import_import_key(import_import):
    assert import_import.key == ImportKey('Foo', 'bar')


def test_import_import_sort_key(import_import):
    assert import_import.sort_key == ('0', 'foo', 'bar', 'Foo', 'bar')


def test_import_import_equality_casing():
    assert (
        import_obj_from_str('import herp.DERP') !=
        import_obj_from_str('import herp.derp')
    )


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('import foo', False),
        ('import foo, bar', True),
    ),
)
def test_import_import_is_multiple(input_str, expected):
    assert import_obj_from_str(input_str).is_multiple is expected


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('import foo', [import_obj_from_str('import foo')]),
        (
            'import foo, bar',
            [
                import_obj_from_str('import foo'),
                import_obj_from_str('import bar'),
            ],
        ),
    ),
)
def test_import_import_split(input_str, expected):
    assert list(import_obj_from_str(input_str).split()) == expected


@pytest.mark.parametrize(
    'import_str',
    (
        'import foo\n',
        'import foo.bar\n',
        'import foo as bar\n',
    ),
)
def test_import_import_str(import_str):
    assert str(import_obj_from_str(import_str)) == import_str


def test_import_import_repr(import_import):
    expected = "import_obj_from_str('import Foo as bar\\n')"
    assert repr(import_import) == expected


@pytest.mark.parametrize(
    ('import_str', 'expected'),
    (
        ('import   foo', 'import foo\n'),
        ('import foo   as bar', 'import foo as bar\n'),
        ('import foo as    bar', 'import foo as bar\n'),
    ),
)
def test_import_import_str_normalizes_whitespace(import_str, expected):
    assert str(import_obj_from_str(import_str)) == expected


@pytest.fixture
def from_import():
    yield import_obj_from_str('from Foo import bar as baz')


def test_from_import_node(from_import):
    assert isinstance(from_import.node, ast.ImportFrom)


def test_from_import_key(from_import):
    ret = from_import.key
    assert ret == ImportFromKey('Foo', 'bar', 'baz')


def test_from_import_sort_key(from_import):
    ret = from_import.sort_key
    assert ret == ('1', 'foo', 'bar', 'baz', 'Foo', 'bar', 'baz')


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('from foo import bar', False),
        ('from foo import bar, baz', True),
    ),
)
def test_from_import_is_multiple(input_str, expected):
    assert import_obj_from_str(input_str).is_multiple is expected


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('from foo import bar', [import_obj_from_str('from foo import bar')]),
        (
            'from foo import bar, baz',
            [
                import_obj_from_str('from foo import bar'),
                import_obj_from_str('from foo import baz'),
            ],
        ),
        (
            'from .foo import bar, baz',
            [
                import_obj_from_str('from .foo import bar'),
                import_obj_from_str('from .foo import baz'),
            ],
        ),
    ),
)
def test_from_import_split(input_str, expected):
    assert list(import_obj_from_str(input_str).split()) == expected


@pytest.mark.parametrize(
    'import_str',
    (
        'from foo import bar\n',
        'from foo.bar import baz\n',
        'from foo.bar import baz as buz\n',
    ),
)
def test_from_import_str(import_str):
    assert str(import_obj_from_str(import_str)) == import_str


@pytest.mark.parametrize(
    ('import_str', 'expected'),
    (
        ('from   foo import bar', 'from foo import bar\n'),
        ('from foo    import bar', 'from foo import bar\n'),
        ('from foo import   bar', 'from foo import bar\n'),
        ('from foo import bar    as baz', 'from foo import bar as baz\n'),
        ('from foo import bar as    baz', 'from foo import bar as baz\n'),
    ),
)
def test_from_import_str_normalizes_whitespace(import_str, expected):
    assert str(import_obj_from_str(import_str)) == expected


def test_from_import_repr(from_import):
    expected = "import_obj_from_str('from Foo import bar as baz\\n')"
    assert repr(from_import) == expected


def test_from_import_hashable():
    my_set = set()
    my_set.add(import_obj_from_str('from foo import bar'))
    my_set.add(import_obj_from_str('from foo import bar'))
    assert len(my_set) == 1


def test_import_import_hashable():
    my_set = set()
    my_set.add(import_obj_from_str('import foo'))
    my_set.add(import_obj_from_str('import foo'))
    assert len(my_set) == 1


@pytest.mark.parametrize(
    'input_str',
    (
        'from . import bar\n',
        'from .foo import bar\n',
        'from .. import bar\n',
        'from ..foo import bar\n',
    ),
)
def test_local_imports(input_str):
    assert str(import_obj_from_str(input_str)) == input_str


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('from foo import bar', import_obj_from_str('from foo import bar')),
        (
            'from foo import bar, baz',
            import_obj_from_str('from foo import bar, baz'),
        ),
        ('import bar', import_obj_from_str('import bar')),
        ('import bar, baz', import_obj_from_str('import bar, baz')),
    ),
)
def test_import_obj_from_str(input_str, expected):
    assert import_obj_from_str(input_str) == expected


IMPORTS = (
    import_obj_from_str('from os import path'),
    import_obj_from_str('from classify_imports import classify_base'),
    import_obj_from_str('import sys'),
    import_obj_from_str('import pyramid'),
)


def test_separate_import_before_from():
    ret = sort(IMPORTS)
    assert ret == (
        (
            import_obj_from_str('import sys'),
            import_obj_from_str('from os import path'),
        ),
        (
            import_obj_from_str('import pyramid'),
        ),
        (
            import_obj_from_str('from classify_imports import classify_base'),
        ),
    )


def test_future_from_always_first():
    ret = sort(
        (
            import_obj_from_str('from __future__ import absolute_import'),
            import_obj_from_str('import __future__'),
        ),
    )
    assert ret == (
        (import_obj_from_str('from __future__ import absolute_import'),),
        (import_obj_from_str('import __future__'),),
    )


def test_passes_through_kwargs_to_classify(in_tmpdir):
    # Make a module
    in_tmpdir.join('my_module.py').ensure()

    imports = (
        import_obj_from_str('import my_module'),
        import_obj_from_str('import pyramid'),
    )
    # Without kwargs, my_module should get classified as application (in a
    # separate group).
    ret = sort(imports)
    assert ret == (
        (import_obj_from_str('import pyramid'),),
        (import_obj_from_str('import my_module'),),
    )
    # But when we put the application at a nonexistent directory
    # it'll be third party (and in the same group as pyramid)
    ret = sort(imports, Settings(application_directories=('dne',)))
    assert ret == (imports,)
