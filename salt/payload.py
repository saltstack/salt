# -*- coding: utf-8 -*-
'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen
in here
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
# import sys  # Use if sys is commented out below
import logging
import gc
import datetime

# Import salt libs
import salt.log
import salt.transport.frame
import salt.utils.immutabletypes as immutabletypes
import salt.utils.stringutils
from salt.exceptions import SaltReqTimeoutError, SaltDeserializationError
from salt.utils.data import CaseInsensitiveDict

# Import third party libs
from salt.ext import six
try:
    import zmq
except ImportError:
    # No need for zeromq in local mode
    pass

log = logging.getLogger(__name__)

HAS_MSGPACK = False
try:
    # Attempt to import msgpack
    import msgpack
    # There is a serialization issue on ARM and potentially other platforms
    # for some msgpack bindings, check for it
    if msgpack.version >= (0, 4, 0):
        if msgpack.loads(msgpack.dumps([1, 2, 3], use_bin_type=False), use_list=True) is None:
            raise ImportError
    else:
        if msgpack.loads(msgpack.dumps([1, 2, 3]), use_list=True) is None:
            raise ImportError
    HAS_MSGPACK = True
except ImportError:
    # Fall back to msgpack_pure
    try:
        import msgpack_pure as msgpack  # pylint: disable=import-error
        HAS_MSGPACK = True
    except ImportError:
        # TODO: Come up with a sane way to get a configured logfile
        #       and write to the logfile when this error is hit also
        LOG_FORMAT = '[%(levelname)-8s] %(message)s'
        salt.log.setup_console_logger(log_format=LOG_FORMAT)
        log.fatal('Unable to import msgpack or msgpack_pure python modules')
        # Don't exit if msgpack is not available, this is to make local mode
        # work without msgpack
        #sys.exit(salt.defaults.exitcodes.EX_GENERIC)


if HAS_MSGPACK and not hasattr(msgpack, 'exceptions'):
    class PackValueError(Exception):
        '''
        older versions of msgpack do not have PackValueError
        '''

    class exceptions(object):
        '''
        older versions of msgpack do not have an exceptions module
        '''
        PackValueError = PackValueError()

    msgpack.exceptions = exceptions()


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
        elif isinstance(opts, six.string_types):
            self.serial = opts
        else:
            self.serial = 'msgpack'

    def loads(self, msg, encoding=None, raw=False):
        '''
        Run the correct loads serialization format

        :param encoding: Useful for Python 3 support. If the msgpack data
                         was encoded using "use_bin_type=True", this will
                         differentiate between the 'bytes' type and the
                         'str' type by decoding contents with 'str' type
                         to what the encoding was set as. Recommended
                         encoding is 'utf-8' when using Python 3.
                         If the msgpack data was not encoded using
                         "use_bin_type=True", it will try to decode
                         all 'bytes' and 'str' data (the distinction has
                         been lost in this case) to what the encoding is
                         set as. In this case, it will fail if any of
                         the contents cannot be converted.
        '''
        try:
            def ext_type_decoder(code, data):
                if code == 78:
                    data = salt.utils.stringutils.to_unicode(data)
                    return datetime.datetime.strptime(data, '%Y%m%dT%H:%M:%S.%f')
                return data

            gc.disable()  # performance optimization for msgpack
            loads_kwargs = {'use_list': True,
                            'ext_hook': ext_type_decoder}
            if msgpack.version >= (0, 4, 0):
                # msgpack only supports 'encoding' starting in 0.4.0.
                # Due to this, if we don't need it, don't pass it at all so
                # that under Python 2 we can still work with older versions
                # of msgpack.
                if msgpack.version >= (0, 5, 2):
                    if encoding is None:
                        loads_kwargs['raw'] = True
                    else:
                        loads_kwargs['raw'] = False
                else:
                    loads_kwargs['encoding'] = encoding
                try:
                    ret = msgpack.loads(msg, **loads_kwargs)
                except UnicodeDecodeError:
                    # msg contains binary data
                    loads_kwargs.pop('raw', None)
                    loads_kwargs.pop('encoding', None)
                    ret = msgpack.loads(msg, **loads_kwargs)
            else:
                ret = msgpack.loads(msg, **loads_kwargs)
            if six.PY3 and encoding is None and not raw:
                ret = salt.transport.frame.decode_embedded_strs(ret)
        except Exception as exc:
            log.critical(
                'Could not deserialize msgpack message. This often happens '
                'when trying to read a file not in binary mode. '
                'To see message payload, enable debug logging and retry. '
                'Exception: %s', exc
            )
            log.debug('Msgpack deserialization failure on message: %s', msg)
            gc.collect()
            raise six.raise_from(
                SaltDeserializationError(
                    'Could not deserialize msgpack message.'
                    ' See log for more info.'
                ),
                exc,
            )
        finally:
            gc.enable()
        return ret

    def load(self, fn_):
        '''
        Run the correct serialization to load a file
        '''
        data = fn_.read()
        fn_.close()
        if data:
            if six.PY3:
                return self.loads(data, encoding='utf-8')
            else:
                return self.loads(data)

    def dumps(self, msg, use_bin_type=False):
        '''
        Run the correct dumps serialization format

        :param use_bin_type: Useful for Python 3 support. Tells msgpack to
                             differentiate between 'str' and 'bytes' types
                             by encoding them differently.
                             Since this changes the wire protocol, this
                             option should not be used outside of IPC.
        '''
        def ext_type_encoder(obj):
            if isinstance(obj, six.integer_types):
                # msgpack can't handle the very long Python longs for jids
                # Convert any very long longs to strings
                return six.text_type(obj)
            elif isinstance(obj, (datetime.datetime, datetime.date)):
                # msgpack doesn't support datetime.datetime and datetime.date datatypes.
                # So here we have converted these types to custom datatype
                # This is msgpack Extended types numbered 78
                return msgpack.ExtType(78, salt.utils.stringutils.to_bytes(
                    obj.strftime('%Y%m%dT%H:%M:%S.%f')))
            # The same for immutable types
            elif isinstance(obj, immutabletypes.ImmutableDict):
                return dict(obj)
            elif isinstance(obj, immutabletypes.ImmutableList):
                return list(obj)
            elif isinstance(obj, (set, immutabletypes.ImmutableSet)):
                # msgpack can't handle set so translate it to tuple
                return tuple(obj)
            elif isinstance(obj, CaseInsensitiveDict):
                return dict(obj)
            # Nothing known exceptions found. Let msgpack raise it's own.
            return obj

        try:
            if msgpack.version >= (0, 4, 0):
                # msgpack only supports 'use_bin_type' starting in 0.4.0.
                # Due to this, if we don't need it, don't pass it at all so
                # that under Python 2 we can still work with older versions
                # of msgpack.
                return msgpack.dumps(msg, default=ext_type_encoder, use_bin_type=use_bin_type)
            else:
                return msgpack.dumps(msg, default=ext_type_encoder)
        except (OverflowError, msgpack.exceptions.PackValueError):
            # msgpack<=0.4.6 don't call ext encoder on very long integers raising the error instead.
            # Convert any very long longs to strings and call dumps again.
            def verylong_encoder(obj):
                if isinstance(obj, dict):
                    for key, value in six.iteritems(obj.copy()):
                        obj[key] = verylong_encoder(value)
                    return dict(obj)
                elif isinstance(obj, (list, tuple)):
                    obj = list(obj)
                    for idx, entry in enumerate(obj):
                        obj[idx] = verylong_encoder(entry)
                    return obj
                # A value of an Integer object is limited from -(2^63) upto (2^64)-1 by MessagePack
                # spec. Here we care only of JIDs that are positive integers.
                if isinstance(obj, six.integer_types) and obj >= pow(2, 64):
                    return six.text_type(obj)
                else:
                    return obj

            msg = verylong_encoder(msg)
            if msgpack.version >= (0, 4, 0):
                return msgpack.dumps(msg, default=ext_type_encoder, use_bin_type=use_bin_type)
            else:
                return msgpack.dumps(msg, default=ext_type_encoder)

    def dump(self, msg, fn_):
        '''
        Serialize the correct data into the named file object
        '''
        if six.PY2:
            fn_.write(self.dumps(msg))
        else:
            # When using Python 3, write files in such a way
            # that the 'bytes' and 'str' types are distinguishable
            # by using "use_bin_type=True".
            fn_.write(self.dumps(msg, use_bin_type=True))
        fn_.close()


class SREQ(object):
    '''
    Create a generic interface to wrap salt zeromq req calls.
    '''
    def __init__(self, master, id_='', serial='msgpack', linger=0, opts=None):
        self.master = master
        self.id_ = id_
        self.serial = Serial(serial)
        self.linger = linger
        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.opts = opts

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

            self._set_tcp_keepalive()
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

    def _set_tcp_keepalive(self):
        if hasattr(zmq, 'TCP_KEEPALIVE') and self.opts:
            if 'tcp_keepalive' in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE, self.opts['tcp_keepalive']
                )
            if 'tcp_keepalive_idle' in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE_IDLE, self.opts['tcp_keepalive_idle']
                )
            if 'tcp_keepalive_cnt' in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE_CNT, self.opts['tcp_keepalive_cnt']
                )
            if 'tcp_keepalive_intvl' in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE_INTVL, self.opts['tcp_keepalive_intvl']
                )

    def clear_socket(self):
        '''
        delete socket if you have it
        '''
        if hasattr(self, '_socket'):
            if isinstance(self.poller.sockets, dict):
                sockets = list(self.poller.sockets.keys())
                for socket in sockets:
                    log.trace('Unregistering socket: %s', socket)
                    self.poller.unregister(socket)
            else:
                for socket in self.poller.sockets:
                    log.trace('Unregistering socket: %s', socket)
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
                log.info(
                    'SaltReqTimeoutError: after %s seconds. (Try %s of %s)',
                    timeout, tried, tries
                )
            if tried >= tries:
                self.clear_socket()
                raise SaltReqTimeoutError(
                    'SaltReqTimeoutError: after {0} seconds, ran {1} '
                    'tries'.format(timeout * tried, tried)
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

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()
    # pylint: enable=W1701
