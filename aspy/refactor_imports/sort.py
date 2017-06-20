from __future__ import absolute_import
from __future__ import unicode_literals

import collections

from aspy.refactor_imports.classify import classify_import
from aspy.refactor_imports.classify import ImportType
from aspy.refactor_imports.import_obj import FromImport
from aspy.refactor_imports.import_obj import ImportImport


# For `import_before_from`
CLS_TO_INDEX = {
    ImportImport: 0,
    FromImport: 1,
}


def sort(imports, separate=True, import_before_from=True,
         separate_relative=False, **classify_kwargs):
    """Sort import objects into groups.

    :param list imports: FromImport / ImportImport objects
    :param bool separate: Whether to classify and return separate segments
        of imports based on classification.
    :param bool import_before_from: Whether to sort `import ...` imports before
        `from ...` imports.
    :param bool split_relative:
        Whether to split `from .xx import xx` imports from other local imports
        with an new line.

    For example:
        from os import path
        from aspy import refactor_imports
        import sys
        import pyramid

    separate = True, import_before_from = True

        import sys
        from os import path

        import pyramid

        from aspy import refactor_imports

    separate = True, import_before_from = False

        from os import path
        import sys

        import pyramid

        from aspy import refactor_imports

    separate = False, import_before_from = True

        import pyramid
        import sys
        from aspy import refactor_imports
        from os import path

    separate = False, import_before_from = False

        from aspy import refactor_imports
        from os import path
        import pyramid
        import sys

    Split relative example:

        from os import path
        from aspy import refactor_imports
        from .sort import sort
        import sys
        import pyramid

    sperate = True, import_before_from = True, separate_relative = False

        import sys
        from os import path

        import pyramid

        from .sort import sort
        from aspy import refactor_imports

    sperate = True, import_before_from = True, separate_relative = True

        import sys
        from os import path

        import pyramid

        from aspy import refactor_imports

        from .sort import sort
    """
    classify_kwargs["separate_relative"] = separate_relative

    if separate:
        def classify_func(obj):
            return classify_import(
                obj.import_statement.module, **classify_kwargs
            )
        types = ImportType.__all__
    else:
        # A little cheaty, this allows future imports to sort before others
        def classify_func(obj):
            return classify_import(
                obj.import_statement.module, **classify_kwargs
            ) == ImportType.FUTURE
        types = [True, False]

    if import_before_from:
        def sort_within(obj):
            return (CLS_TO_INDEX[type(obj)],) + obj.sort_key
    else:
        def sort_within(obj):
            return tuple(obj.sort_key)

    # Partition the imports
    imports_partitioned = collections.defaultdict(list)
    for import_obj in imports:
        imports_partitioned[classify_func(import_obj)].append(import_obj)

    # sort each of the segments
    for segment_key, val in imports_partitioned.items():
        imports_partitioned[segment_key] = sorted(val, key=sort_within)

    return tuple(
        tuple(imports_partitioned[key])
        for key in types if key in imports_partitioned
    )
