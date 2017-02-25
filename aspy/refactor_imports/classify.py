from __future__ import unicode_literals

import imp
import os.path


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


def _find_module_closes_file(module_name):
    """Fixes a python3 warning about not explicitly closing the module file"""
    file_obj, pathname, description = imp.find_module(module_name)
    if file_obj:
        file_obj.close()
    return pathname, description


def _get_module_info(module_name, application_directories):
    """Attempt to get module info from the first module name.

    1.) Attempt `imp.find_module`, this will fail if it is not importable
        Since we're likely to be running in our own environment where
        the thing we're statically analyzing isn't importable this is
        really only likely to succeed for system packages

    2.) Attempt to find it as a file from any of the application directories
        - Try `module_name` (maybe a package directory?)
        - Try `module_name + '.py'` (maybe a python file?)
        - Give up and assume it's importable as just `module_name`
        - TODO: is it worth it to try for C extensions here? I think not
            since C extensions should probably won't exist at a top level
        - TODO: are there any other special cases to worry about?

    :param text module_name: the first segment of a module name, such as 'aspy'
    """
    try:
        return (True,) + _find_module_closes_file(module_name)
    except ImportError:
        # In the general case we probably can't import the modules because
        # our environment will be isolated from theirs.
        pass

    for local_path in application_directories:
        pkg_path = os.path.join(local_path, module_name)
        mod_path = os.path.join(local_path, module_name + '.py')
        if (
                os.path.exists(pkg_path) and
                os.path.isdir(pkg_path) and
                os.listdir(pkg_path)
        ):
            module_path = pkg_path
            break
        elif os.path.exists(mod_path):
            module_path = mod_path
            break
    else:
        # We did not find a local file that looked like the module
        module_path = module_name + '.notlocal'

    return False, module_path, ('', '', imp.PY_SOURCE)


PACKAGES_PATH = '-packages' + os.sep


def classify_import(module_name, application_directories=('.',)):
    """Classifies an import by its package.

    Returns a value in ImportType.__all__

    :param text module_name: The dotted notation of a module
    :param tuple application_directories: tuple of paths which are considered
        application roots.
    """
    # Only really care about the first part of the path
    base_module_name = module_name.split('.')[0]
    found, module_path, module_info = _get_module_info(
        base_module_name, application_directories,
    )
    # Relative imports: `from .foo import bar`
    if base_module_name == '__future__':
        return ImportType.FUTURE
    elif base_module_name == '':
        return ImportType.APPLICATION
    # If imp tells us it is builtin, it is builtin
    elif module_info[2] == imp.C_BUILTIN:
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
