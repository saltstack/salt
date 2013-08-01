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

# Import third party libs
import zmq

log = salt.log.logging.getLogger(__name__)

try:
    # Attempt to import msgpack
    import msgpack
    # There is a serialization issue on ARM and potentially other platforms
    # for some msgpack bindings, check for it
    if msgpack.loads(msgpack.dumps([1, 2, 3]), use_list=True) is None:
        raise ImportError
except ImportError:
    # Fall back to msgpack_pure
    try:
        import msgpack_pure as msgpack
    except ImportError:
        # TODO: Come up with a sane way to get a configured logfile
        #       and write to the logfile when this error is hit also
        LOG_FORMAT = '[%(levelname)-8s] %(message)s'
        salt.log.setup_console_logger(log_format=LOG_FORMAT)
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
            try:
                return msgpack.dumps(msg)
            except TypeError:
                if msgpack.version >= (0, 2, 0):
                    # Should support OrderedDict serialization, so, let's
                    # raise the exception
                    raise

                # msgpack is < 0.2.0, let's make it's life easier
                # Since OrderedDict is identified as a dictionary, we can't
                # make use of msgpack custom types, we will need to convert by
                # hand.
                # This means iterating through all elements of a dictionary or
                # list/tuple
                def odict_encoder(obj):
                    if isinstance(obj, dict):
                        for key, value in obj.copy().iteritems():
                            obj[key] = odict_encoder(value)
                        return dict(obj)
                    elif isinstance(obj, (list, tuple)):
                        obj = list(obj)
                        for idx, entry in enumerate(obj):
                            obj[idx] = odict_encoder(entry)
                        return obj
                    return obj
                return msgpack.dumps(odict_encoder(msg))

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
    def __init__(self, master, id_='', serial='msgpack', linger=0):
        self.master = master
        self.serial = Serial(serial)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        if hasattr(zmq, 'RECONNECT_IVL_MAX'):
            self.socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, 5000
            )

        if master.startswith('tcp://[') and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.socket.setsockopt(zmq.IPV4ONLY, 0)
        self.socket.linger = linger
        if id_:
            self.socket.setsockopt(zmq.IDENTITY, id_)
        self.socket.connect(master)
        self.poller = zmq.Poller()

    def send(self, enc, load, tries=1, timeout=60):
        '''
        Takes two arguments, the encryption type and the base payload
        '''
        payload = {'enc': enc}
        payload['load'] = load
        pkg = self.serial.dumps(payload)
        self.socket.send(pkg)
        self.poller.register(self.socket, zmq.POLLIN)
        tried = 0
        while True:
            polled = self.poller.poll(timeout * 1000)
            tried += 1
            if polled:
                break
            elif tried >= tries:
                raise SaltReqTimeoutError(
                    'Waited {0} seconds'.format(
                        timeout * tried
                    )
                )
        return self.serial.loads(self.socket.recv())

    def send_auto(self, payload, tries=1, timeout=60):
        '''
        Detect the encryption type based on the payload
        '''
        enc = payload.get('enc', 'clear')
        load = payload.get('load', {})
        return self.send(enc, load, tries, timeout)

    def destroy(self):
        for socket in self.poller.sockets.keys():
            if socket.closed is False:
                socket.setsockopt(zmq.LINGER, 1)
                socket.close()
            self.poller.unregister(socket)
        if self.socket.closed is False:
            self.socket.setsockopt(zmq.LINGER, 1)
            self.socket.close()
        if self.context.closed is False:
            self.context.term()

    def __del__(self):
        self.destroy()
