'''
A few checks to make sure the environment is sane
'''
# Original Author: Jeff Schroeder <jeffschroeder@computer.org>

import os
import sys
import logging
import salt.log
log = logging.getLogger(__name__)

__all__ = ('zmq_version', 'check_root', 'run')

def zmq_version():
    '''ZeroMQ python bindings >= 2.1.9 are required'''
    import zmq
    ver = zmq.__version__
    ver_int = int(ver.replace('.', ''))
    if not ver_int >= 219:
        log.critical("ZeroMQ python bindings >= 2.1.9 are required")
        return False
    return True

def check_root():
    '''
    Most of the salt scripts need to run as root, this function will simply
    verify that root is the user before the application discovers it.
    '''
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            return True
    msg = 'Sorry, the salt must run as root.  http://xkcd.com/838'
    if os.getuid():
        log.critical(msg)
        return False
    return True

def run():
    for func in __all__:
        if func == "run": continue
        if not globals().get(func)():
            sys.exit(1)
