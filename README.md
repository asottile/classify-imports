[![Build Status](https://asottile.visualstudio.com/asottile/_apis/build/status/asottile.classify-imports?branchName=main)](https://asottile.visualstudio.com/asottile/_build/latest?definitionId=74&branchName=main)
[![Azure DevOps coverage](https://img.shields.io/azure-devops/coverage/asottile/asottile/74/main.svg)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=74&branchName=main)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/asottile/classify-imports/main.svg)](https://results.pre-commit.ci/latest/github/asottile/classify-imports/main)

classify-imports
================

Utilities for refactoring imports in python-like syntax.

## installation

`pip install classify-imports`

## examples

### splitting an import object

```python
>>> from classify_imports import import_obj_from_str
>>> obj = import_obj_from_str('import foo, bar, baz')
>>> [str(i) for i in obj.split()]
['import foo\n', 'import bar\n', 'import baz\n']
```

### sorting import objects

```python
# Or to partition into blocks (even with mixed imports)
>>> import pprint
>>> from classify_imports import import_obj_from_str, sort
>>> partitioned = sort(
    [
        import_obj_from_str('from classify_imports import sort'),
        import_obj_from_str('import sys'),
        import_obj_from_str('from pyramid.view import view_config'),
        import_obj_from_str('import cached_property'),
    ],
)
>>> pprint.pprint(partitioned)
(
    (import_obj_from_str('import sys\n'),),
    (
        import_obj_from_str('import cached_property\n'),
        import_obj_from_str('from pyramid.view import view_config\n'),
    ),
    (import_obj_from_str('from classify_imports import sort\n'),),
)

```

### classify a module

```python
>>> from classify_imports import classify_base, import_obj_from_str
>>> classify_base('__future__')
<Classified.FUTURE: 0>
>>> classify_base('classify_imports')
<Classified.APPLICATION: 3>
>>> classify_base('pyramid')
<Classified.THIRD_PARTY: 2>
>>> classify_base('os')
<Classified.BUILTIN: 1>
>>> classify_base(import_obj_from_str('import os.path').module_base)
<Classified.BUILTIN: 1>
```
