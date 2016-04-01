# -*- coding: utf-8 -*-
'''
Simple script to dump the contents of msgpack files to the terminal
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import sys
import pprint

# Import third party libs
import msgpack


def dump(path):
    '''
    Read in a path and dump the contents to the screen
    '''
    if not os.path.isfile(path):
        print('Not a file')
        return
    with open(path, 'rb') as fp_:
        data = msgpack.loads(fp_.read())
        pprint.pprint(data)


if __name__ == '__main__':
    dump(sys.argv[1])
