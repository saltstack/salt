'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen
in here
'''

# Import python libs
import sys

# Import salt libs
import salt.log
import salt.crypt
from salt.exceptions import SaltReqTimeoutError
from salt._compat import pickle

# Import zeromq
import zmq

log = salt.log.logging.getLogger(__name__)

try:
    # Attempt to import msgpack
    import msgpack
    # There is a serialization issue on ARM and potentially other platforms
    # for some msgpack bindings, check for it
    if msgpack.loads(msgpack.dumps([1,2,3])) is None:
        raise ImportError
except ImportError:
    # Fall back to msgpack_pure
    try:
        import msgpack_pure as msgpack
    except ImportError:
        # TODO: Come up with a sane way to get a configured logfile
        #       and write to the logfile when this error is hit also
        log_format = '[%(levelname)-8s] %(message)s'
        salt.log.setup_console_logger(log_format=log_format)
        log.fatal('Unable to import msgpack or msgpack_pure python modules')
        sys.exit(1)


def package(payload):
    '''
    This method for now just wraps msgpack.dumps, but it is here so that
    we can make the serialization a custom option in the future with ease.
    '''
    return msgpack.dumps(payload)


def unpackage(package_):
    '''
    Unpackages a payload
    '''
    return msgpack.loads(package_, use_list=True)


def format_payload(enc, **kwargs):
    '''
    Pass in the required arguments for a payload, the enc type and the cmd,
    then a list of keyword args to generate the body of the load dict.
    '''
    payload = {'enc': enc}
    load = {}
    for key in kwargs:
        load[key] = kwargs[key]
    payload['load'] = load
    return package(payload)


class Serial(object):
    '''
    Create a serialization object, this object manages all message
    serialization in Salt
    '''
    def __init__(self, opts):
        if isinstance(opts, dict):
            self.serial = opts.get('serial', 'msgpack')
        elif isinstance(opts, str):
            self.serial = opts
        else:
            self.serial = 'msgpack'

    def loads(self, msg):
        '''
        Run the correct loads serialization format
        '''
        if self.serial == 'msgpack':
            return msgpack.loads(msg, use_list=True)
        elif self.serial == 'pickle':
            try:
                return pickle.loads(msg)
            except Exception:
                return msgpack.loads(msg, use_list=True)

    def load(self, fn_):
        '''
        Run the correct serialization to load a file
        '''
        data = fn_.read()
        fn_.close()
        return self.loads(data)

    def dumps(self, msg):
        '''
        Run the correct dumps serialization format
        '''
        if self.serial == 'pickle':
            return pickle.dumps(msg)
        else:
            return msgpack.dumps(msg)

    def dump(self, msg, fn_):
        '''
        Serialize the correct data into the named file object
        '''
        fn_.write(self.dumps(msg))
        fn_.close()


class SREQ(object):
    '''
    Create a generic interface to wrap salt zeromq req calls. 
    '''
    def __init__(self, master, serial='msgpack', linger=0):
        self.master = master
        self.serial = Serial(serial)
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.linger = linger
        self.socket.connect(master)

    def send(self, enc, load, tries=1, timeout=60):
        '''
        Takes two arguments, the encryption type and the base payload
        '''
        payload = {'enc': enc}
        payload['load'] = load
        package = self.serial.dumps(payload)
        self.socket.send(package)
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        tried = 0
        while True:
            if not poller.poll(timeout*1000) and tried >= tries:
                raise SaltReqTimeoutError('Waited {0} seconds'.format(timeout))
            else:
                break
            tried += 1
        ret = self.serial.loads(self.socket.recv())
        poller.unregister(self.socket)
        return ret

    def send_auto(self, payload):
        '''
        Detect the encryption type based on the payload
        '''
        enc = payload.get('enc', 'clear')
        load = payload.get('load', {})
        return self.send(enc, load)
