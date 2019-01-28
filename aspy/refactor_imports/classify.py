from __future__ import unicode_literals

import os.path
import sys


class ImportType(object):
    __slots__ = ()

    FUTURE = 'FUTURE'
    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = (FUTURE, BUILTIN, THIRD_PARTY, APPLICATION)


def _pythonpath_dirs():
    if 'PYTHONPATH' not in os.environ:
        return set()

    splitpath = os.environ['PYTHONPATH'].split(os.pathsep)
    return {os.path.realpath(p) for p in splitpath} - {os.path.realpath('.')}


def _due_to_pythonpath(module_path):
    mod_dir, _ = os.path.split(os.path.realpath(module_path))
    return mod_dir in _pythonpath_dirs()


def _module_path_is_local_and_is_not_symlinked(
        module_path, application_directories,
):
    def _is_a_local_path(potential_path):
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


def _find_local(module_name, application_directories):
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


if sys.version_info < (3, 5):  # pragma: no cover (PY2)
    import imp

    def _get_module_info(module_name, application_dirs):
        """Attempt to get module info from the first module name.

        1.) Attempt `imp.find_module`, this will fail if it is not importable
            Since we're likely to be running in our own environment where
            the thing we're statically analyzing isn't importable this is
            really only likely to succeed for system packages

        2.) Attempt to find it as a file from any of the application dirs
            - Try `module_name` (maybe a package directory?)
            - Try `module_name + '.py'` (maybe a python file?)
            - Give up and assume it's importable as just `module_name`
            - TODO: is it worth it to try for C extensions here? I think not
                since C extensions should probably won't exist at a top level
            - TODO: are there any other special cases to worry about?

        :param text module_name: the first segment of a module name
        """
        if module_name in sys.builtin_module_names:
            return True, '(builtin)', True

        try:
            fileobj, filename, _ = imp.find_module(module_name)
        except ImportError:
            # In the general case we probably can't import the modules because
            # our environment will be isolated from theirs.
            pass
        else:
            if fileobj:
                fileobj.close()
            return True, filename, False

        return False, _find_local(module_name, application_dirs), False
else:  # pragma: no cover (PY3+)
    import importlib.util

    def _get_module_info(module_name, application_dirs):
        if module_name in sys.builtin_module_names:
            return True, '(builtin)', True

        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return False, _find_local(module_name, application_dirs), False
        elif spec.origin in {None, 'namespace'}:
            return True, next(iter(spec.submodule_search_locations)), False
        # special case pypy3 bug(?)
        elif not os.path.exists(spec.origin):
            return True, '(builtin)', True
        elif os.path.split(spec.origin)[1] == '__init__.py':
            return True, os.path.dirname(spec.origin), False
        else:
            return True, spec.origin, False


PACKAGES_PATH = '-packages' + os.sep


def classify_import(module_name, application_directories=('.',)):
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
