# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
import logging
import os

import jnpr.junos
import jnpr.junos.utils
import jnpr.junos.cfg
HAS_JUNOS = True


def proxyconn(user=None, host=None, passwd=None):
    jdev = jnpr.junos.Device(user=user, host=host, password=passwd)
    jdev.open()
    jdev.bind(cu=jnpr.junos.utils.Config)
    return jdev

def proxytype():
    return 'junos'

def id(opts):
    return opts['proxyconn'].facts['hostname']
