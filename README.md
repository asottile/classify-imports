[![Build Status](https://travis-ci.org/asottile/aspy.refactor_imports.svg?branch=master)](https://travis-ci.org/asottile/aspy.refactor_imports)
[![Coverage Status](https://img.shields.io/coveralls/asottile/aspy.refactor_imports.svg?branch=master)](https://coveralls.io/r/asottile/aspy.refactor_imports)
[![Build status](https://ci.appveyor.com/api/projects/status/1x3de58cbkjxoxey?svg=true)](https://ci.appveyor.com/project/asottile/aspy-refactor-imports)

aspy.refactor_imports
==========

Utilities for refactoring imports in python-like syntax.


## Installation

`pip install aspy.refactor_imports`


## Examples

### aspy.refactor_imports.import_obj

#### Constructing an import object

```python
>>> from aspy.refactor_imports.import_obj import FromImport
>>> from aspy.refactor_imports.import_obj import ImportImport
>>> FromImport.from_str('from foo import bar').to_text()
u'from foo import bar\n'
>>> ImportImport.from_str('import bar as baz').to_text()
u'import bar as baz\n'
```

#### Splitting an import object

```python
>>> from aspy.refactor_imports.import_obj import ImportImport
>>> obj = ImportImport.from_str('import foo, bar, baz')
>>> [i.to_text() for i in obj.split_imports()]
[u'import foo\n', u'import bar\n', u'import baz\n']
```

#### Sorting import objects

```python
>>> import pprint
>>> from aspy.refactor_imports.import_obj import FromImport
>>> objs = sorted([
    FromImport.from_str('from a import foo'),
    FromImport.from_str('from a.b import baz'),
    FromImport.from_str('from a import bar'),
    FromImport.from_str('from a import bar as buz'),
    FromImport.from_str('from a import bar as baz'),
])
>>> pprint.pprint([i.to_text() for i in objs])
[u'from a import bar\n',
 u'from a import bar as baz\n',
 u'from a import bar as buz\n',
 u'from a import foo\n',
 u'from a.b import baz\n']
```

```python
# Or to partition into blocks (even with mixed imports)
>>> import buck.pprint as pprint
>>> from aspy.refactor_imports.import_obj import FromImport
>>> from aspy.refactor_imports.import_obj import ImportImport
>>> from aspy.refactor_imports.sort import sort
>>> partitioned = sort(
    [
        FromImport.from_str('from aspy import refactor_imports'),
        ImportImport.from_str('import sys'),
        FromImport.from_str('from pyramid.view import view_config'),
        ImportImport.from_str('import cached_property'),
    ],
    separate=True,
    import_before_from=True,
))
>>> pprint.pprint(partitioned)
(
    (ImportImport.from_str(u'import sys\n'),),
    (
        ImportImport.from_str(u'import cached_property\n'),
        FromImport.from_str(u'from pyramid.view import view_config\n'),
    ),
    (FromImport.from_str(u'from aspy import refactor_imports\n'),),
)

```

### aspy.refactor_imports.classify

#### Classify a module

```python
>>> from aspy.refactor_imports.classify import classify_import
>>> classify_import('__future__')
u'FUTURE'
>>> classify_import('aspy')
u'APPLICATION'
>>> classify_import('pyramid')
u'THIRD_PARTY'
>>> classify_import('os')
u'BUILTIN'
>>> classify_import('os.path')
u'BUILTIN'
```

#### Also as convenient constants

```python
## From aspy.refactor_imports.classify


class ImportType(object):
    __slots__ = ()

    FUTURE = 'FUTURE'
    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = [FUTURE, BUILTIN, THIRD_PARTY, APPLICATION]
```
