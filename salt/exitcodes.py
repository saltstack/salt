# -*- coding: utf-8 -*-
'''
Classification of Salt exit codes.  These are intended to augment
universal exit codes (found in Python's `os` module with the `EX_`
prefix or in `sysexits.h`).
'''

# Too many situations use "exit 1" - try not to use it when something
# else is more appropriate.
EX_GENERIC = 1

# Salt SSH "Thin" deployment failures
EX_THIN_PYTHON_OLD = 10
EX_THIN_DEPLOY = 11
EX_THIN_CHECKSUM = 12
