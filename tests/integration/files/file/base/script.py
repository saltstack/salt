#!/usr/bin/env python
import sys

try:
    print ' '.join(sys.argv[1:])
except SyntaxError:
    print(' '.join(sys.argv[1:]))
