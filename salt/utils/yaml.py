"""
Convenience module that provides our custom loader and dumper in a single module
"""

# pylint: disable=wildcard-import,unused-wildcard-import,unused-import

from yaml import YAMLError, parser, scanner

from salt.utils.yamldumper import *
from salt.utils.yamlloader import *

# pylint: enable=wildcard-import,unused-wildcard-import,unused-import
