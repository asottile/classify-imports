from __future__ import annotations

import importlib.util
import os.path
import sys
import zipimport
from typing import Container


class ImportType:
    __slots__ = ()

    FUTURE = 'FUTURE'
    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = (FUTURE, BUILTIN, THIRD_PARTY, APPLICATION)


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

    try:
        spec = importlib.util.find_spec(module_name)
    except ValueError:  # spec is None
        spec = None
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


def classify_import(
        module_name: str,
        application_directories: tuple[str, ...] = ('.',),
        unclassifiable_application_modules: Container[str] = (),
) -> str:
    """Classifies an import by its package.

    Returns a value in ImportType.__all__

    :param text module_name: The dotted notation of a module
    :param tuple application_directories: tuple of paths which are considered
        application roots.
    :param tuple unclassifiable_application_modules: tuple of module names
        that are considered application modules.  this setting is intended
        to be used for things like C modules which may not always appear on
        the filesystem.
    """
    # Only really care about the first part of the path
    base, _, _ = module_name.partition('.')
    found, module_path, is_builtin = _get_module_info(
        base, application_directories,
    )
    if base == '__future__':
        return ImportType.FUTURE
    elif base == '__main__':
        return ImportType.APPLICATION
    # force distutils to be "third party" after being gobbled by setuptools
    elif base == 'distutils':
        return ImportType.THIRD_PARTY
    elif base in unclassifiable_application_modules:
        return ImportType.APPLICATION
    # relative imports: `from .foo import bar`
    elif base == '':
        return ImportType.APPLICATION
    # if the import system tells us it is builtin, it is builtin
    elif is_builtin:
        return ImportType.BUILTIN
    # if the module path exists in the project directories
    elif _module_path_is_local_and_is_not_symlinked(
            module_path, application_directories,
    ):
        return ImportType.APPLICATION
    # Otherwise we assume it is a system module or a third party module
    elif (
            found and
            PACKAGES_PATH not in module_path and
            not _due_to_pythonpath(module_path)
    ):
        return ImportType.BUILTIN
    else:
        return ImportType.THIRD_PARTY
