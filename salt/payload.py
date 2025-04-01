"""
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen
in here
"""

import collections.abc
import datetime
import gc
import logging

import salt.transport.frame
import salt.utils.immutabletypes as immutabletypes
import salt.utils.msgpack
import salt.utils.stringutils
from salt.defaults import _Constant
from salt.exceptions import SaltDeserializationError, SaltReqTimeoutError
from salt.utils.data import CaseInsensitiveDict

try:
    import zmq
except ImportError:
    # No need for zeromq in local mode
    pass

log = logging.getLogger(__name__)


def package(payload):
    """
    This method for now just wraps msgpack.dumps, but it is here so that
    we can make the serialization a custom option in the future with ease.
    """
    return salt.utils.msgpack.dumps(payload)


def unpackage(package_):
    """
    Unpackages a payload
    """
    return salt.utils.msgpack.loads(package_, use_list=True)


def format_payload(enc, **kwargs):
    """
    Pass in the required arguments for a payload, the enc type and the cmd,
    then a list of keyword args to generate the body of the load dict.
    """
    payload = {"enc": enc}
    load = {}
    for key in kwargs:
        load[key] = kwargs[key]
    payload["load"] = load
    return package(payload)


def loads(msg, encoding=None, raw=False):
    """
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
    """
    try:

        def ext_type_decoder(code, data):
            if code == 78:
                data = salt.utils.stringutils.to_unicode(data)
                return datetime.datetime.strptime(data, "%Y%m%dT%H:%M:%S.%f")
            if code == 79:
                name, value = salt.utils.msgpack.loads(data, raw=False)
                return _Constant(name, value)
            return data

        gc.disable()  # performance optimization for msgpack
        loads_kwargs = {"use_list": True, "ext_hook": ext_type_decoder}
        if encoding is None:
            loads_kwargs["raw"] = True
        else:
            loads_kwargs["raw"] = False
        try:
            ret = salt.utils.msgpack.unpackb(msg, **loads_kwargs)
        except UnicodeDecodeError:
            # msg contains binary data
            loads_kwargs.pop("raw", None)
            ret = salt.utils.msgpack.loads(msg, **loads_kwargs)
        if encoding is None and not raw:
            ret = salt.transport.frame.decode_embedded_strs(ret)
    except Exception as exc:  # pylint: disable=broad-except
        log.critical(
            "Could not deserialize msgpack message. This often happens "
            "when trying to read a file not in binary mode. "
            "To see message payload, enable debug logging and retry. "
            "Exception: %s",
            exc,
        )
        log.debug("Msgpack deserialization failure on message: %s", msg)
        exc_msg = "Could not deserialize msgpack message. See log for more info."
        raise SaltDeserializationError(exc_msg) from exc
    finally:
        gc.enable()
    return ret


def dumps(msg, use_bin_type=False):
    """
    Run the correct dumps serialization format

    :param use_bin_type: Useful for Python 3 support. Tells msgpack to
                         differentiate between 'str' and 'bytes' types
                         by encoding them differently.
                         Since this changes the wire protocol, this
                         option should not be used outside of IPC.
    """

    def ext_type_encoder(obj):
        if isinstance(obj, int):
            # msgpack can't handle the very long Python longs for jids
            # Convert any very long longs to strings
            return str(obj)
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            # msgpack doesn't support datetime.datetime and datetime.date datatypes.
            # So here we have converted these types to custom datatype
            # This is msgpack Extended types numbered 78
            return salt.utils.msgpack.ExtType(
                78,
                salt.utils.stringutils.to_bytes(obj.strftime("%Y%m%dT%H:%M:%S.%f")),
            )
        elif isinstance(obj, _Constant):
            # Special case our constants.
            return salt.utils.msgpack.ExtType(
                79,
                salt.utils.msgpack.dumps((obj.name, obj.value), use_bin_type=True),
            )
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
        elif isinstance(obj, collections.abc.MutableMapping):
            return dict(obj)
        # Nothing known exceptions found. Let msgpack raise its own.
        return obj

    try:
        return salt.utils.msgpack.packb(
            msg, default=ext_type_encoder, use_bin_type=use_bin_type
        )
    except (OverflowError, salt.utils.msgpack.exceptions.PackValueError):
        # msgpack<=0.4.6 don't call ext encoder on very long integers raising the error instead.
        # Convert any very long longs to strings and call dumps again.
        def verylong_encoder(obj, context):
            # Make sure we catch recursion here.
            objid = id(obj)
            # This instance list needs to correspond to the types recursed
            # in the below if/elif chain. Also update
            # tests/unit/test_payload.py
            if objid in context and isinstance(obj, (dict, list, tuple)):
                return "<Recursion on {} with id={}>".format(
                    type(obj).__name__, id(obj)
                )
            context.add(objid)

            # The isinstance checks in this if/elif chain need to be
            # kept in sync with the above recursion check.
            if isinstance(obj, dict):
                for key, value in obj.copy().items():
                    obj[key] = verylong_encoder(value, context)
                return dict(obj)
            elif isinstance(obj, (list, tuple)):
                obj = list(obj)
                for idx, entry in enumerate(obj):
                    obj[idx] = verylong_encoder(entry, context)
                return obj
            # A value of an Integer object is limited from -(2^63) upto (2^64)-1 by MessagePack
            # spec. Here we care only of JIDs that are positive integers.
            if isinstance(obj, int) and obj >= pow(2, 64):
                return str(obj)
            else:
                return obj

        msg = verylong_encoder(msg, set())
        return salt.utils.msgpack.packb(
            msg, default=ext_type_encoder, use_bin_type=use_bin_type
        )


def load(fn_):
    """
    Run the correct serialization to load a file
    """
    data = fn_.read()
    fn_.close()
    if data:
        return loads(data, encoding="utf-8")


def dump(msg, fn_):
    """
    Serialize the correct data into the named file object
    """
    # When using Python 3, write files in such a way
    # that the 'bytes' and 'str' types are distinguishable
    # by using "use_bin_type=True".
    fn_.write(dumps(msg, use_bin_type=True))
    fn_.close()


class SREQ:
    """
    Create a generic interface to wrap salt zeromq req calls.
    """

    def __init__(self, master, id_="", serial="msgpack", linger=0, opts=None):
        self.master = master
        self.id_ = id_
        self.linger = linger
        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.opts = opts

    @property
    def socket(self):
        """
        Lazily create the socket.
        """
        if not hasattr(self, "_socket"):
            # create a new one
            self._socket = self.context.socket(zmq.REQ)
            if hasattr(zmq, "RECONNECT_IVL_MAX"):
                self._socket.setsockopt(zmq.RECONNECT_IVL_MAX, 5000)

            self._set_tcp_keepalive()
            if self.master.startswith("tcp://["):
                # Hint PF type if bracket enclosed IPv6 address
                if hasattr(zmq, "IPV6"):
                    self._socket.setsockopt(zmq.IPV6, 1)
                elif hasattr(zmq, "IPV4ONLY"):
                    self._socket.setsockopt(zmq.IPV4ONLY, 0)
            self._socket.linger = self.linger
            if self.id_:
                self._socket.setsockopt(zmq.IDENTITY, self.id_)
            self._socket.connect(self.master)
        return self._socket

    def _set_tcp_keepalive(self):
        if hasattr(zmq, "TCP_KEEPALIVE") and self.opts:
            if "tcp_keepalive" in self.opts:
                self._socket.setsockopt(zmq.TCP_KEEPALIVE, self.opts["tcp_keepalive"])
            if "tcp_keepalive_idle" in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE_IDLE, self.opts["tcp_keepalive_idle"]
                )
            if "tcp_keepalive_cnt" in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE_CNT, self.opts["tcp_keepalive_cnt"]
                )
            if "tcp_keepalive_intvl" in self.opts:
                self._socket.setsockopt(
                    zmq.TCP_KEEPALIVE_INTVL, self.opts["tcp_keepalive_intvl"]
                )

    def clear_socket(self):
        """
        delete socket if you have it
        """
        if hasattr(self, "_socket"):
            if isinstance(self.poller.sockets, dict):
                sockets = list(self.poller.sockets.keys())
                for socket in sockets:
                    log.trace("Unregistering socket: %s", socket)
                    self.poller.unregister(socket)
            else:
                for socket in self.poller.sockets:
                    log.trace("Unregistering socket: %s", socket)
                    self.poller.unregister(socket[0])
            del self._socket

    def send(self, enc, load, tries=1, timeout=60):
        """
        Takes two arguments, the encryption type and the base payload
        """
        payload = {"enc": enc}
        payload["load"] = load
        pkg = dumps(payload)
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
                    "SaltReqTimeoutError: after %s seconds. (Try %s of %s)",
                    timeout,
                    tried,
                    tries,
                )
            if tried >= tries:
                self.clear_socket()
                raise SaltReqTimeoutError(
                    "SaltReqTimeoutError: after {} seconds, ran {} tries".format(
                        timeout * tried, tried
                    )
                )
        return loads(self.socket.recv())

    def send_auto(self, payload, tries=1, timeout=60):
        """
        Detect the encryption type based on the payload
        """
        enc = payload.get("enc", "clear")
        load = payload.get("load", {})
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
