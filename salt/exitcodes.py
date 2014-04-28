# -*- coding: utf-8 -*-
'''
Classification of Salt exit codes.  These are intended to augment
universal exit codes (found in Python's `os` module with the `EX_`
prefix or in `sysexits.h`).
'''

# Too many situations use "exit 1" - try not to use it when something
# else is more appropriate.
EX_GENERIC = 1

EX_DEPLOY_THIN = 3
EX_PYTHON_OLD = 4
EX_CHECKSUM = 5
