[![Build Status](https://travis-ci.org/asottile/aspy.refactor_imports.svg?branch=master)](https://travis-ci.org/asottile/aspy.refactor_imports)
[![Coverage Status](https://img.shields.io/coveralls/asottile/aspy.refactor_imports.svg?branch=master)](https://coveralls.io/r/asottile/aspy.refactor_imports)

aspy.refactor_imports
==========

Utilities for refactoring imports in python-like syntax.


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

### aspy.refactor_imports.classify

#### Classify a module

```python
>>> from aspy.refactor_imports.classify import classify_import
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

    BUILTIN = 'BUILTIN'
    THIRD_PARTY = 'THIRD_PARTY'
    APPLICATION = 'APPLICATION'

    __all__ = [BUILTIN, THIRD_PARTY, APPLICATION]
```
