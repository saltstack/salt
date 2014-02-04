#!/usr/bin/env python
'''
The setup script table
'''

import os
# Use setuptools only if the user opts-in by setting the USE_SETUPTOOLS env var
# This ensures consistent behavior but allows for advanced usage with
# virtualenv, buildout, and others.
USE_SETUPTOOLS = False
if 'USE_SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        USE_SETUPTOOLS = True
    except:
        USE_SETUPTOOLS = False


if USE_SETUPTOOLS is False:
    from distutils.core import setup

NAME = 'table'
DESC = ('An multi backend crypto abstraction system')
VERSION = '0.1.0'

kwargs = {}

kwargs.update(
    name=NAME,
    version=VERSION,
    description=DESC,
    author='Thomas S Hatch',
    author_email='thatch45@gmail.com',
    url='http://red45.org',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        ],
    packages=[
        'table',
        'table.public',
        'table.secret'],
)

if USE_SETUPTOOLS:
    kwargs.update(
        install_requires=open('requirements.txt').readlines(),
    )

setup(**kwargs)
