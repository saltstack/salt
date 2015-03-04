# -*- coding: utf-8 -*-
'''
A simple test engine, not intended for real use but as an example
'''
# Import python libs
import time

# Import python libs
import logging

log = logging.getLogger(__name__)


def start():
    '''
    Do something from time to time
    '''
    while True:
        log.debug('.')
        time.sleep(5)
