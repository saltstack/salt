'''
A few checks to make sure the environment is sane
'''
# Original Author: Jeff Schroeder <jeffschroeder@computer.org>

import sys
import logging
log = logging.getLogger(__name__)

__all__ = ('zmq_version', 'run')

def zmq_version():
    '''ZeroMQ python bindings >= 2.1.9 are required'''
    import zmq
    ver = zmq.__version__
    ver_int = int(ver.replace('.', ''))
    if not ver_int >= 219:
        log.critical("ZeroMQ python bindings >= 2.1.9 are required")
        return False
    return True

def run():
    for func in __all__:
        if func == "run": continue
        if not globals().get(func)():
            sys.exit(1)
