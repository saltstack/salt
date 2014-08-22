#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
The setup script for sodium_grabber
'''

# pylint: disable=C0111,E1101,E1103,F0401,W0611

from distutils.core import setup, Extension
from os import path

HERE = path.dirname(__file__)

SETUP_KWARGS = {}
sodium_grabber = Extension('sodium_grabber',
    sources = [path.join(HERE, 'sodium_grabber.c')],
    libraries = ['sodium'],
)
SETUP_KWARGS['ext_modules'] = [sodium_grabber]
SETUP_KWARGS['name'] = "sodium_grabber"

if __name__ == '__main__':
    setup(**SETUP_KWARGS)
