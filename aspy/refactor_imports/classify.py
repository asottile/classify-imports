import importlib.util
import os.path
import sys
import zipimport
from typing import Set
from typing import Tuple


class ImportType:
    __slots__ = ()

    FUTURE = 'FUTURE'
    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = (FUTURE, BUILTIN, THIRD_PARTY, APPLICATION)


def _pythonpath_dirs() -> Set[str]:
    if 'PYTHONPATH' not in os.environ:
        return set()

    splitpath = os.environ['PYTHONPATH'].split(os.pathsep)
    return {os.path.realpath(p) for p in splitpath} - {os.path.realpath('.')}


def _due_to_pythonpath(module_path: str) -> bool:
    mod_dir, _ = os.path.split(os.path.realpath(module_path))
    return mod_dir in _pythonpath_dirs()


def _module_path_is_local_and_is_not_symlinked(
        module_path: str, application_directories: Tuple[str, ...],
) -> bool:
    def _is_a_local_path(potential_path: str) -> bool:
        localpath = os.path.abspath(potential_path)
        abspath = os.path.abspath(module_path)
        realpath = os.path.realpath(module_path)
        return (
            abspath.startswith(localpath) and
            # It's possible (and surprisingly likely) that the consumer has a
            # virtualenv inside the project directory.  We'd like to still
            # consider things in the virtualenv as third party.
            os.sep not in abspath[len(localpath) + 1:] and
            abspath == realpath and
            os.path.exists(realpath)
        )

    return any(_is_a_local_path(path) for path in application_directories)


def _find_local(
        module_name: str,
        application_directories: Tuple[str, ...],
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
        application_dirs: Tuple[str, ...],
) -> Tuple[bool, str, bool]:
    if module_name in sys.builtin_module_names:
        return True, '(builtin)', True

    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False, _find_local(module_name, application_dirs), False
    # py36: None, py37+: 'namespace'
    elif spec.origin is None or spec.origin == 'namespace':
        assert spec.submodule_search_locations is not None
        return True, next(iter(spec.submodule_search_locations)), False
    elif isinstance(spec.loader, zipimport.zipimporter):
        return True, spec.origin, False
    # special case pypy3 bug(?)
    elif not os.path.exists(spec.origin):  # pragma: no cover
        return True, '(builtin)', True
    elif os.path.split(spec.origin)[1] == '__init__.py':
        return True, os.path.dirname(spec.origin), False
    else:
        return True, spec.origin, False


PACKAGES_PATH = '-packages' + os.sep


def classify_import(
        module_name: str,
        application_directories: Tuple[str, ...] = ('.',),
) -> str:
    """Classifies an import by its package.

    Returns a value in ImportType.__all__

    :param text module_name: The dotted notation of a module
    :param tuple application_directories: tuple of paths which are considered
        application roots.
    """
    # Only really care about the first part of the path
    base, _, _ = module_name.partition('.')
    found, module_path, is_builtin = _get_module_info(
        base, application_directories,
    )
    if base == '__future__':
        return ImportType.FUTURE
    # Relative imports: `from .foo import bar`
    elif base == '':
        return ImportType.APPLICATION
    # If imp tells us it is builtin, it is builtin
    elif is_builtin:
        return ImportType.BUILTIN
    # If the module path exists in the project directories
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
