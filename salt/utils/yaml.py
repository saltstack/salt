# -*- coding: utf-8 -*-
'''
Convenience module that provides our custom loader and dumper in a single module
'''
from __future__ import absolute_import, print_function, unicode_literals

# pylint: disable=wildcard-import,unused-wildcard-import,unused-import
from yaml import YAMLError, parser, scanner
from salt.utils.yamldumper import *
from salt.utils.yamlloader import *
