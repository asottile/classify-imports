from setuptools import setup


setup(
    name='aspy.refactor_imports',
    description="Utilities for refactoring imports in python-like syntax.",
    url='https://github.com/asottile/aspy.refactor_imports',
    version='0.3.3',

    author='Anthony Sottile',
    author_email='asottile@umich.edu',

    platforms='all',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],

    packages=['aspy', 'aspy.refactor_imports'],
    namespace_packages=['aspy'],
    install_requires=[
        'cached_property',
    ],
)
