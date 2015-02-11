# -*- coding: utf-8 -*-
'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen
in here
'''

# Import python libs
# import sys  # Use if sys is commented out below
import logging

# Import salt libs
import salt.log
import salt.crypt
from salt.exceptions import SaltReqTimeoutError

# Import third party libs
try:
    import zmq
except ImportError:
    # No need for zeromq in local mode
    pass

log = logging.getLogger(__name__)

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
        # Don't exit if msgpack is not available, this is to make local mode
        # work without msgpack
        #sys.exit(salt.exitcodes.EX_GENERIC)


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
        try:
            return msgpack.loads(msg, use_list=True)
        except Exception as exc:
            log.critical('Could not deserialize msgpack message: {0}'
                         'In an attempt to keep Salt running, returning an empty dict.'
                         'This often happens when trying to read a file not in binary mode.'
                         'Please open an issue and include the following error: {1}'.format(msg, exc))
            return {}

    def load(self, fn_):
        '''
        Run the correct serialization to load a file
        '''
        data = fn_.read()
        fn_.close()
        if data:
            return self.loads(data)

    def dumps(self, msg):
        '''
        Run the correct dumps serialization format
        '''
        try:
            return msgpack.dumps(msg)
        except TypeError:
            if msgpack.version >= (0, 2, 0):
                # Should support OrderedDict serialization, so, let's
                # raise the exception
                raise

            # msgpack is < 0.2.0, let's make its life easier
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
        except SystemError as exc:
            log.critical('Unable to serialize message! Consider upgrading msgpack. '
                         'Message which failed was {failed_message} '
                         'with exception {exception_message}').format(msg, exc)

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
        self.id_ = id_
        self.serial = Serial(serial)
        self.linger = linger
        self.context = zmq.Context()
        self.poller = zmq.Poller()

    @property
    def socket(self):
        '''
        Lazily create the socket.
        '''
        if not hasattr(self, '_socket'):
            # create a new one
            self._socket = self.context.socket(zmq.REQ)
            if hasattr(zmq, 'RECONNECT_IVL_MAX'):
                self._socket.setsockopt(
                    zmq.RECONNECT_IVL_MAX, 5000
                )

            if self.master.startswith('tcp://['):
                # Hint PF type if bracket enclosed IPv6 address
                if hasattr(zmq, 'IPV6'):
                    self._socket.setsockopt(zmq.IPV6, 1)
                elif hasattr(zmq, 'IPV4ONLY'):
                    self._socket.setsockopt(zmq.IPV4ONLY, 0)
            self._socket.linger = self.linger
            if self.id_:
                self._socket.setsockopt(zmq.IDENTITY, self.id_)
            self._socket.connect(self.master)
        return self._socket

    def clear_socket(self):
        '''
        delete socket if you have it
        '''
        if hasattr(self, '_socket'):
            if isinstance(self.poller.sockets, dict):
                sockets = list(self.poller.sockets.keys())
                for socket in sockets:
                    log.trace('Unregistering socket: {0}'.format(socket))
                    self.poller.unregister(socket)
            else:
                for socket in self.poller.sockets:
                    log.trace('Unregistering socket: {0}'.format(socket))
                    self.poller.unregister(socket[0])
            del self._socket

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
            if tries > 1:
                log.info('SaltReqTimeoutError: after {0} seconds. (Try {1} of {2})'.format(
                  timeout, tried, tries))
            if tried >= tries:
                self.clear_socket()
                raise SaltReqTimeoutError(
                    'SaltReqTimeoutError: after {0} seconds, ran {1} tries'.format(timeout * tried, tried)
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
        if isinstance(self.poller.sockets, dict):
            sockets = list(self.poller.sockets.keys())
            for socket in sockets:
                if socket.closed is False:
                    socket.setsockopt(zmq.LINGER, 1)
                    socket.close()
                self.poller.unregister(socket)
        else:
            for socket in self.poller.sockets:
                if socket[0].closed is False:
                    socket[0].setsockopt(zmq.LINGER, 1)
                    socket[0].close()
                self.poller.unregister(socket[0])
        if self.socket.closed is False:
            self.socket.setsockopt(zmq.LINGER, 1)
            self.socket.close()
        if self.context.closed is False:
            self.context.term()

    def __del__(self):
        self.destroy()
