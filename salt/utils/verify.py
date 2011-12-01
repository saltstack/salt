'''
A few checks to make sure the environment is sane
'''
# Original Author: Jeff Schroeder <jeffschroeder@computer.org>

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

def check_root():
    '''
    Most of the salt scripts need to run as root, this function will simply
    verify that root is the user before the application discovers it.
    '''
    if os.getuid():
        print ('Sorry, the salt must run as root, it needs to operate '
               'in a privileged environment to do what it does.\n'
               'http://xkcd.com/838/')
        sys.exit(1)

def run():
    for func in __all__:
        if func == "run": continue
        if not locals().get(func)():
            sys.exit(1)
