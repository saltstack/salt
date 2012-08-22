'''
A salt interface for running a Certificate Authority (CA)
which provides signed/unsigned SSL certificates

REQUIREMENT 1?:

Required python modules: PyOpenSSL

REQUIREMENT 2:

Add the following values in /etc/salt/minion for the 
CA module to function properly::

ca.cert_base_path: '/etc/pki/koji'


'''

import os
import sys
import time
import logging
import hashlib
import OpenSSL

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only load this module if the ca config options are set
    '''

    return 'ca'

