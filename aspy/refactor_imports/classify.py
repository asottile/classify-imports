from __future__ import unicode_literals

import imp
import os.path
import sys


# pylint: disable=bad-continuation


class ImportType(object):
    __slots__ = ()

    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = [BUILTIN, THIRD_PARTY, APPLICATION]


def _module_path_is_local_and_is_not_symlinked(module_path):
    abspath = os.path.abspath(module_path)
    realpath = os.path.realpath(module_path)
    return abspath == realpath and os.path.exists(realpath)


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

    :param module_name: the first segment of a module name, such as 'aspy'
    :type module_name: text
    """
    try:
        return imp.find_module(module_name)[1:]
    except ImportError:
        # In the general case we probably can't import the modules because
        # our environment will be isolated from theirs.  However, our cwd
        # should be their project root
        pass

    if os.path.exists(module_name):
        module_path = module_name
    elif os.path.exists(module_name + '.py'):
        module_path = module_name + '.py'
    else:
        module_path = module_name

    return (module_path, ('', '', imp.PY_SOURCE))


def classify_import(module_name):
    """Classifies an import by its package.

    Returns a value in ImportType.__all__

    :param module_name: The dotted notation of a module
    :type module_name: text
    """
    # Only really care about the first part of the path
    base_module_name = module_name.split('.')[0]
    module_path, module_info = _get_module_info(base_module_name)
    # Relative imports: `from .foo import bar`
    if base_module_name == '':
        return ImportType.APPLICATION
    elif module_info[2] == imp.C_BUILTIN:
        return ImportType.BUILTIN
    elif (
        module_path.startswith(sys.prefix) and
        '-packages/' not in module_path
    ):
        return ImportType.BUILTIN
    elif _module_path_is_local_and_is_not_symlinked(module_path):
        return ImportType.APPLICATION
    else:
        return ImportType.THIRD_PARTY
