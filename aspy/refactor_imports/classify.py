from __future__ import unicode_literals

import imp
import os.path


class ImportType(object):
    __slots__ = ()

    FUTURE = 'FUTURE'
    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = [FUTURE, BUILTIN, THIRD_PARTY, APPLICATION]


def _module_path_is_local_and_is_not_symlinked(module_path):
    localpath = os.path.abspath('.')
    abspath = os.path.abspath(module_path)
    realpath = os.path.realpath(module_path)
    return (
        abspath.startswith(localpath) and
        # It's possible (and surprisingly likely) that the consumer has a
        # virtualenv inside the project directory.  We'd like to still consider
        # things in the virtualenv as third party.
        os.sep not in abspath[len(localpath) + 1:] and
        abspath == realpath and
        os.path.exists(realpath)
    )


def _get_module_info(module_name):
    """Attempt to get module info from the first module name.

    1.) Attempt `imp.find_module`, this will fail if it is not importable
        Since we're likely to be running in our own environment where
        the thing we're statically analyzing isn't importable this is
        really only likely to succeed for system packages

    2.) Attempt to find it as a file from `cwd`
        - Try `module_name` (maybe a package directory?)
        - Try `module_name + '.py'` (maybe a python file?)
        - Give up and assume it's importable as just `module_name`
        - TODO: is it worth it to try for C extensions here? I think not
            since C extensions should probably won't exist at a top level
        - TODO: are there any other special cases to worry about?

    :param text module_name: the first segment of a module name, such as 'aspy'
    """
    try:
        return (True,) + imp.find_module(module_name)[1:]
    except ImportError:
        # In the general case we probably can't import the modules because
        # our environment will be isolated from theirs.  However, our cwd
        # should be their project root
        pass

    if (
            os.path.exists(module_name) and
            os.path.isdir(module_name) and
            os.listdir(module_name)
    ):
        module_path = module_name
    elif os.path.exists(module_name + '.py'):
        module_path = module_name + '.py'
    else:
        # We did not find a local file that looked like the module
        module_path = module_name + '.notlocal'

    return False, module_path, ('', '', imp.PY_SOURCE)


PACKAGES_PATH = '-packages' + os.sep


def classify_import(module_name):
    """Classifies an import by its package.

    Returns a value in ImportType.__all__

    :param module_name: The dotted notation of a module
    :type module_name: text
    """
    # Only really care about the first part of the path
    base_module_name = module_name.split('.')[0]
    found, module_path, module_info = _get_module_info(base_module_name)
    # Relative imports: `from .foo import bar`
    if base_module_name == '__future__':
        return ImportType.FUTURE
    elif base_module_name == '':
        return ImportType.APPLICATION
    # If imp tells us it is builtin, it is builtin
    elif module_info[2] == imp.C_BUILTIN:
        return ImportType.BUILTIN
    # If the module path exists in our cwd
    elif _module_path_is_local_and_is_not_symlinked(module_path):
        return ImportType.APPLICATION
    # Otherwise we assume it is a system module or a third party module
    elif found and PACKAGES_PATH not in module_path:
        return ImportType.BUILTIN
    else:
        return ImportType.THIRD_PARTY
