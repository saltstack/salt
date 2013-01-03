#!/usr/bin/env python
'''
This script is used to kick off a salt minion daemon
'''

from salt.scripts import salt_minion
from multiprocessing import freeze_support


if __name__ == '__main__':
    # This handles the bootstrapping code that is included with frozen
    # scripts. It is a no-op on unfrozen code.
    freeze_support()
    salt_minion()
