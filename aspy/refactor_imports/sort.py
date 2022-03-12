from __future__ import annotations

import collections
from typing import Any
from typing import Sequence

from aspy.refactor_imports.classify import classify_import
from aspy.refactor_imports.classify import ImportType
from aspy.refactor_imports.import_obj import AbstractImportObj
from aspy.refactor_imports.import_obj import FromImport
from aspy.refactor_imports.import_obj import ImportImport


# For `import_before_from`
CLS_TO_INDEX = {ImportImport: '0', FromImport: '1'}


def sort(
        imports: Sequence[AbstractImportObj],
        **kwargs: Any,
) -> tuple[tuple[AbstractImportObj, ...], ...]:
    """Sort import objects into groups.

    :param list imports: FromImport / ImportImport objects

    For example:

        from os import path
        from aspy import refactor_imports
        import sys
        import pyramid

    becomes:

        import sys
        from os import path

        import pyramid

        from aspy import refactor_imports
    """
    # Partition the imports
    imports_partitioned: dict[str, list[AbstractImportObj]]
    imports_partitioned = collections.defaultdict(list)
    for import_obj in imports:
        tp = classify_import(import_obj.import_statement.module, **kwargs)
        if tp == ImportType.FUTURE and isinstance(import_obj, ImportImport):
            tp = ImportType.BUILTIN

        imports_partitioned[tp].append(import_obj)

    # sort each of the segments

    def sort_within(obj: AbstractImportObj) -> tuple[str, ...]:
        return (CLS_TO_INDEX[type(obj)],) + obj.sort_key

    for segment_key, val in imports_partitioned.items():
        imports_partitioned[segment_key] = sorted(val, key=sort_within)

    return tuple(
        tuple(imports_partitioned[key])
        for key in ImportType.__all__ if key in imports_partitioned
    )
