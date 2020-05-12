# -*- coding: utf-8 -*-
"""
Manage events

Events are all fired off via a zeromq 'pub' socket, and listened to with local
zeromq 'sub' sockets


All of the formatting is self contained in the event module, so we should be
able to modify the structure in the future since the same module used to read
events is the same module used to fire off events.

Old style event messages were comprised of two parts delimited at the 20 char
point. The first 20 characters are used for the zeromq subscriber to match
publications and 20 characters was chosen because it was at the time a few more
characters than the length of a jid (Job ID).  Any tags of length less than 20
characters were padded with "|" chars out to 20 characters.

Although not explicit, the data for an event comprised a python dict that was
serialized by msgpack.

New style event messages support event tags longer than 20 characters while
still being backwards compatible with old style tags.

The longer tags better enable name spaced event tags which tend to be longer.
Moreover, the constraint that the event data be a python dict is now an
explicit constraint and fire-event will now raise a ValueError if not. Tags
must be ascii safe strings, that is, have values less than 0x80

Since the msgpack dict (map) indicators have values greater than or equal to
0x80 it can be unambiguously determined if the start of data is at char 21
or not.

In the new style, when the tag is longer than 20 characters, an end of tag
string is appended to the tag given by the string constant TAGEND, that is, two
line feeds '\n\n'.  When the tag is less than 20 characters then the tag is
padded with pipes "|" out to 20 characters as before.  When the tag is exactly
20 characters no padded is done.

The get_event method intelligently figures out if the tag is longer than 20
characters.


The convention for namespacing is to use dot characters "." as the name space
delimiter. The name space "salt" is reserved by SaltStack for internal events.

For example:
Namespaced tag
    'salt.runner.manage.status.start'

"""

from __future__ import absolute_import, print_function, unicode_literals

import datetime
import fnmatch
import hashlib
import logging

# Import python libs
import os
import time
from collections.abc import MutableMapping
from multiprocessing.util import Finalize

# Import salt libs
import salt.config
import salt.defaults.exitcodes
import salt.ext.tornado.ioloop
import salt.ext.tornado.iostream
import salt.log.setup
import salt.payload
import salt.transport.client
import salt.transport.ipc
import salt.utils.asynchronous
import salt.utils.cache
import salt.utils.dicttrim
import salt.utils.files
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
import salt.utils.zeromq

# Import third party libs
from salt.ext import six
from salt.ext.six.moves import range

log = logging.getLogger(__name__)

# The SUB_EVENT set is for functions that require events fired based on
# component executions, like the state system
SUB_EVENT = ("state.highstate", "state.sls")

TAGEND = str("\n\n")  # long tag delimiter
TAGPARTER = str("/")  # name spaced tag delimiter
SALT = "salt"  # base prefix for all salt/ events
# dict map of namespaced base tag prefixes for salt events
TAGS = {
    "auth": "auth",  # prefix for all salt/auth events
    "job": "job",  # prefix for all salt/job events (minion jobs)
    "key": "key",  # prefix for all salt/key events
    "minion": "minion",  # prefix for all salt/minion events
    # (minion sourced events)
    "syndic": "syndic",  # prefix for all salt/syndic events
    # (syndic minion sourced events)
    "run": "run",  # prefix for all salt/run events (salt runners)
    "wheel": "wheel",  # prefix for all salt/wheel events
    "cloud": "cloud",  # prefix for all salt/cloud events
    "fileserver": "fileserver",  # prefix for all salt/fileserver events
    "queue": "queue",  # prefix for all salt/queue events
}


def get_event(
    node,
    sock_dir=None,
    transport="zeromq",
    opts=None,
    listen=True,
    io_loop=None,
    keep_loop=False,
    raise_errors=False,
):
    """
    Return an event object suitable for the named transport

    :param IOLoop io_loop: Pass in an io_loop if you want asynchronous
                           operation for obtaining events. Eg use of
                           set_event_handler() API. Otherwise, operation
                           will be synchronous.
    """
    sock_dir = sock_dir or opts["sock_dir"]
    # TODO: AIO core is separate from transport
    if node == "master":
        return MasterEvent(
            sock_dir,
            opts,
            listen=listen,
            io_loop=io_loop,
            keep_loop=keep_loop,
            raise_errors=raise_errors,
        )
    return SaltEvent(
        node,
        sock_dir,
        opts,
        listen=listen,
        io_loop=io_loop,
        keep_loop=keep_loop,
        raise_errors=raise_errors,
    )


def get_master_event(opts, sock_dir, listen=True, io_loop=None, raise_errors=False):
    """
    Return an event object suitable for the named transport
    """
    # TODO: AIO core is separate from transport
    if opts["transport"] in ("zeromq", "tcp", "detect"):
        return MasterEvent(
            sock_dir, opts, listen=listen, io_loop=io_loop, raise_errors=raise_errors
        )


def fire_args(opts, jid, tag_data, prefix=""):
    """
    Fire an event containing the arguments passed to an orchestration job
    """
    try:
        tag_suffix = [jid, "args"]
    except NameError:
        pass
    else:
        tag = tagify(tag_suffix, prefix)
        try:
            _event = get_master_event(opts, opts["sock_dir"], listen=False)
            _event.fire_event(tag_data, tag=tag)
        except Exception as exc:  # pylint: disable=broad-except
            # Don't let a problem here hold up the rest of the orchestration
            log.warning(
                "Failed to fire args event %s with data %s: %s", tag, tag_data, exc
            )


def tagify(suffix="", prefix="", base=SALT):
    """
    convenience function to build a namespaced event tag string
    from joining with the TABPART character the base, prefix and suffix

    If string prefix is a valid key in TAGS Then use the value of key prefix
    Else use prefix string

    If suffix is a list Then join all string elements of suffix individually
    Else use string suffix

    """
    parts = [base, TAGS.get(prefix, prefix)]
    if hasattr(suffix, "append"):  # list so extend parts
        parts.extend(suffix)
    else:  # string so append
        parts.append(suffix)

    for index, _ in enumerate(parts):
        try:
            parts[index] = salt.utils.stringutils.to_str(parts[index])
        except TypeError:
            parts[index] = str(parts[index])
    return TAGPARTER.join([part for part in parts if part])


class SaltEvent(object):
    """
    Warning! Use the get_event function or the code will not be
    RAET compatible
    The base class used to manage salt events
    """

    def __init__(
        self,
        node,
        sock_dir=None,
        opts=None,
        listen=True,
        io_loop=None,
        keep_loop=False,
        raise_errors=False,
    ):
        """
        :param IOLoop io_loop: Pass in an io_loop if you want asynchronous
                               operation for obtaining events. Eg use of
                               set_event_handler() API. Otherwise, operation
                               will be synchronous.
        :param Bool keep_loop: Pass a boolean to determine if we want to keep
                               the io loop or destroy it when the event handle
                               is destroyed. This is useful when using event
                               loops from within third party asynchronous code
        """
        self.serial = salt.payload.Serial({"serial": "msgpack"})
        self.keep_loop = keep_loop
        if io_loop is not None:
            self.io_loop = io_loop
            self._run_io_loop_sync = False
        else:
            self.io_loop = salt.ext.tornado.ioloop.IOLoop()
            self._run_io_loop_sync = True
        self.cpub = False
        self.cpush = False
        self.subscriber = None
        self.pusher = None
        self.raise_errors = raise_errors

        if opts is None:
            opts = {}
        if node == "master":
            self.opts = salt.config.DEFAULT_MASTER_OPTS.copy()
        else:
            self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.opts.update(opts)

        if sock_dir is None:
            sock_dir = self.opts["sock_dir"]
        else:
            self.opts["sock_dir"] = sock_dir

        if salt.utils.platform.is_windows() and "ipc_mode" not in opts:
            self.opts["ipc_mode"] = "tcp"
        self.puburi, self.pulluri = self.__load_uri(sock_dir, node)
        self.pending_tags = []
        self.pending_events = []
        self.__load_cache_regex()
        if listen and not self.cpub:
            # Only connect to the publisher at initialization time if
            # we know we want to listen. If we connect to the publisher
            # and don't read out events from the buffer on an on-going basis,
            # the buffer will grow resulting in big memory usage.
            self.connect_pub()

    @classmethod
    def __load_cache_regex(cls):
        """
        Initialize the regular expression cache and put it in the
        class namespace. The regex search strings will be prepend with '^'
        """
        # This is in the class namespace, to minimize cache memory
        # usage and maximize cache hits
        # The prepend='^' is to reduce differences in behavior between
        # the default 'startswith' and the optional 'regex' match_type
        cls.cache_regex = salt.utils.cache.CacheRegex(prepend="^")

    def __load_uri(self, sock_dir, node):
        """
        Return the string URI for the location of the pull and pub sockets to
        use for firing and listening to events
        """
        if node == "master":
            if self.opts["ipc_mode"] == "tcp":
                puburi = int(self.opts["tcp_master_pub_port"])
                pulluri = int(self.opts["tcp_master_pull_port"])
            else:
                puburi = os.path.join(sock_dir, "master_event_pub.ipc")
                pulluri = os.path.join(sock_dir, "master_event_pull.ipc")
        else:
            if self.opts["ipc_mode"] == "tcp":
                puburi = int(self.opts["tcp_pub_port"])
                pulluri = int(self.opts["tcp_pull_port"])
            else:
                hash_type = getattr(hashlib, self.opts["hash_type"])
                # Only use the first 10 chars to keep longer hashes from exceeding the
                # max socket path length.
                id_hash = hash_type(
                    salt.utils.stringutils.to_bytes(self.opts["id"])
                ).hexdigest()[:10]
                puburi = os.path.join(
                    sock_dir, "minion_event_{0}_pub.ipc".format(id_hash)
                )
                pulluri = os.path.join(
                    sock_dir, "minion_event_{0}_pull.ipc".format(id_hash)
                )
        log.debug("%s PUB socket URI: %s", self.__class__.__name__, puburi)
        log.debug("%s PULL socket URI: %s", self.__class__.__name__, pulluri)
        return puburi, pulluri

    def subscribe(self, tag=None, match_type=None):
        """
        Subscribe to events matching the passed tag.

        If you do not subscribe to a tag, events will be discarded by calls to
        get_event that request a different tag. In contexts where many different
        jobs are outstanding it is important to subscribe to prevent one call
        to get_event from discarding a response required by a subsequent call
        to get_event.
        """
        if tag is None:
            return
        match_func = self._get_match_func(match_type)
        self.pending_tags.append([tag, match_func])

    def unsubscribe(self, tag, match_type=None):
        """
        Un-subscribe to events matching the passed tag.
        """
        if tag is None:
            return
        match_func = self._get_match_func(match_type)

        self.pending_tags.remove([tag, match_func])

        old_events = self.pending_events
        self.pending_events = []
        for evt in old_events:
            if any(
                pmatch_func(evt["tag"], ptag) for ptag, pmatch_func in self.pending_tags
            ):
                self.pending_events.append(evt)

    def connect_pub(self, timeout=None):
        """
        Establish the publish connection
        """
        if self.cpub:
            return True

        if self._run_io_loop_sync:
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                if self.subscriber is None:
                    self.subscriber = salt.transport.ipc.IPCMessageSubscriber(
                        self.puburi, io_loop=self.io_loop
                    )
                try:
                    self.io_loop.run_sync(
                        lambda: self.subscriber.connect(timeout=timeout)
                    )
                    self.cpub = True
                except Exception:  # pylint: disable=broad-except
                    pass
        else:
            if self.subscriber is None:
                self.subscriber = salt.transport.ipc.IPCMessageSubscriber(
                    self.puburi, io_loop=self.io_loop
                )

            # For the asynchronous case, the connect will be defered to when
            # set_event_handler() is invoked.
            self.cpub = True
        return self.cpub

    def close_pub(self):
        """
        Close the publish connection (if established)
        """
        if not self.cpub:
            return

        self.subscriber.close()
        self.subscriber = None
        self.pending_events = []
        self.cpub = False

    def connect_pull(self, timeout=1):
        """
        Establish a connection with the event pull socket
        Default timeout is 1 s
        """
        if self.cpush:
            return True

        if self._run_io_loop_sync:
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                if self.pusher is None:
                    self.pusher = salt.transport.ipc.IPCMessageClient(
                        self.pulluri, io_loop=self.io_loop
                    )
                try:
                    self.io_loop.run_sync(lambda: self.pusher.connect(timeout=timeout))
                    self.cpush = True
                except Exception:  # pylint: disable=broad-except
                    pass
        else:
            if self.pusher is None:
                self.pusher = salt.transport.ipc.IPCMessageClient(
                    self.pulluri, io_loop=self.io_loop
                )
            # For the asynchronous case, the connect will be deferred to when
            # fire_event() is invoked.
            self.cpush = True
        return self.cpush

    def close_pull(self):
        """
        Close the pusher connection (if established)
        """
        if not self.cpush:
            return

        self.pusher.close()
        self.pusher = None
        self.cpush = False

    @classmethod
    def unpack(cls, raw, serial=None):
        if serial is None:
            serial = salt.payload.Serial({"serial": "msgpack"})

        if six.PY2:
            mtag, sep, mdata = raw.partition(TAGEND)  # split tag from data
            data = serial.loads(mdata, encoding="utf-8")
        else:
            mtag, sep, mdata = raw.partition(
                salt.utils.stringutils.to_bytes(TAGEND)
            )  # split tag from data
            mtag = salt.utils.stringutils.to_str(mtag)
            data = serial.loads(mdata, encoding="utf-8")
        return mtag, data

    def _get_match_func(self, match_type=None):
        if match_type is None:
            match_type = self.opts["event_match_type"]
        return getattr(self, "_match_tag_{0}".format(match_type), None)

    def _check_pending(self, tag, match_func=None):
        """Check the pending_events list for events that match the tag

        :param tag: The tag to search for
        :type tag: str
        :param tags_regex: List of re expressions to search for also
        :type tags_regex: list[re.compile()]
        :return:
        """
        if match_func is None:
            match_func = self._get_match_func()
        old_events = self.pending_events
        self.pending_events = []
        ret = None
        for evt in old_events:
            if match_func(evt["tag"], tag):
                if ret is None:
                    ret = evt
                    log.trace("get_event() returning cached event = %s", ret)
                else:
                    self.pending_events.append(evt)
            elif any(
                pmatch_func(evt["tag"], ptag) for ptag, pmatch_func in self.pending_tags
            ):
                self.pending_events.append(evt)
            else:
                log.trace(
                    "get_event() discarding cached event that no longer has any subscriptions = %s",
                    evt,
                )
        return ret

    @staticmethod
    def _match_tag_startswith(event_tag, search_tag):
        """
        Check if the event_tag matches the search check.
        Uses startswith to check.
        Return True (matches) or False (no match)
        """
        return event_tag.startswith(search_tag)

    @staticmethod
    def _match_tag_endswith(event_tag, search_tag):
        """
        Check if the event_tag matches the search check.
        Uses endswith to check.
        Return True (matches) or False (no match)
        """
        return event_tag.endswith(search_tag)

    @staticmethod
    def _match_tag_find(event_tag, search_tag):
        """
        Check if the event_tag matches the search check.
        Uses find to check.
        Return True (matches) or False (no match)
        """
        return event_tag.find(search_tag) >= 0

    def _match_tag_regex(self, event_tag, search_tag):
        """
        Check if the event_tag matches the search check.
        Uses regular expression search to check.
        Return True (matches) or False (no match)
        """
        return self.cache_regex.get(search_tag).search(event_tag) is not None

    def _match_tag_fnmatch(self, event_tag, search_tag):
        """
        Check if the event_tag matches the search check.
        Uses fnmatch to check.
        Return True (matches) or False (no match)
        """
        return fnmatch.fnmatch(event_tag, search_tag)

    def _get_event(self, wait, tag, match_func=None, no_block=False):
        if match_func is None:
            match_func = self._get_match_func()
        start = time.time()
        timeout_at = start + wait
        run_once = False
        if no_block is True:
            wait = 0
        elif wait == 0:
            # If no_block is False and wait is 0, that
            # means an infinite timeout.
            wait = None
        while (run_once is False and not wait) or time.time() <= timeout_at:
            if no_block is True:
                if run_once is True:
                    break
                # Trigger that at least a single iteration has gone through
                run_once = True
            try:
                # salt.ext.tornado.ioloop.IOLoop.run_sync() timeouts are in seconds.
                # IPCMessageSubscriber.read_sync() uses this type of timeout.
                if not self.cpub and not self.connect_pub(timeout=wait):
                    break
                raw = self.subscriber.read_sync(timeout=wait)
                if raw is None:
                    break
                mtag, data = self.unpack(raw, self.serial)
                ret = {"data": data, "tag": mtag}
            except KeyboardInterrupt:
                return {"tag": "salt/event/exit", "data": {}}
            except salt.ext.tornado.iostream.StreamClosedError:
                if self.raise_errors:
                    raise
                else:
                    return None
            except RuntimeError:
                return None

            if not match_func(ret["tag"], tag):
                # tag not match
                if any(
                    pmatch_func(ret["tag"], ptag)
                    for ptag, pmatch_func in self.pending_tags
                ):
                    log.trace("get_event() caching unwanted event = %s", ret)
                    self.pending_events.append(ret)
                if wait:  # only update the wait timeout if we had one
                    wait = timeout_at - time.time()
                continue

            log.trace("get_event() received = %s", ret)
            return ret
        log.trace("_get_event() waited %s seconds and received nothing", wait)
        return None

    def get_event(
        self,
        wait=5,
        tag="",
        full=False,
        match_type=None,
        no_block=False,
        auto_reconnect=False,
    ):
        """
        Get a single publication.
        If no publication is available, then block for up to ``wait`` seconds.
        Return publication if it is available or ``None`` if no publication is
        available.

        If wait is 0, then block forever.

        tag
            Only return events matching the given tag. If not specified, or set
            to an empty string, all events are returned. It is recommended to
            always be selective on what is to be returned in the event that
            multiple requests are being multiplexed.

        match_type
            Set the function to match the search tag with event tags.
             - 'startswith' : search for event tags that start with tag
             - 'endswith' : search for event tags that end with tag
             - 'find' : search for event tags that contain tag
             - 'regex' : regex search '^' + tag event tags
             - 'fnmatch' : fnmatch tag event tags matching
            Default is opts['event_match_type'] or 'startswith'

            .. versionadded:: 2015.8.0

        no_block
            Define if getting the event should be a blocking call or not.
            Defaults to False to keep backwards compatibility.

            .. versionadded:: 2015.8.0

        Notes:

        Searches cached publications first. If no cached publications are found
        that match the given tag specification, new publications are received
        and checked.

        If a publication is received that does not match the tag specification,
        it is DISCARDED unless it is subscribed to via subscribe() which will
        cause it to be cached.

        If a caller is not going to call get_event immediately after sending a
        request, it MUST subscribe the result to ensure the response is not lost
        should other regions of code call get_event for other purposes.
        """
        log.trace("Get event. tag: %s", tag)
        assert self._run_io_loop_sync

        match_func = self._get_match_func(match_type)

        ret = self._check_pending(tag, match_func)
        if ret is None:
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                if auto_reconnect:
                    raise_errors = self.raise_errors
                    self.raise_errors = True
                    while True:
                        try:
                            ret = self._get_event(wait, tag, match_func, no_block)
                            break
                        except salt.ext.tornado.iostream.StreamClosedError:
                            self.close_pub()
                            self.connect_pub(timeout=wait)
                            continue
                    self.raise_errors = raise_errors
                else:
                    ret = self._get_event(wait, tag, match_func, no_block)

        if ret is None or full:
            return ret
        else:
            return ret["data"]

    def get_event_noblock(self):
        """
        Get the raw event without blocking or any other niceties
        """
        assert self._run_io_loop_sync

        if not self.cpub:
            if not self.connect_pub():
                return None
        raw = self.subscriber.read_sync(timeout=0)
        if raw is None:
            return None
        mtag, data = self.unpack(raw, self.serial)
        return {"data": data, "tag": mtag}

    def get_event_block(self):
        """
        Get the raw event in a blocking fashion. This is slower, but it decreases the
        possibility of dropped events.
        """
        assert self._run_io_loop_sync

        if not self.cpub:
            if not self.connect_pub():
                return None
        raw = self.subscriber.read_sync(timeout=None)
        if raw is None:
            return None
        mtag, data = self.unpack(raw, self.serial)
        return {"data": data, "tag": mtag}

    def iter_events(self, tag="", full=False, match_type=None, auto_reconnect=False):
        """
        Creates a generator that continuously listens for events
        """
        while True:
            data = self.get_event(
                tag=tag, full=full, match_type=match_type, auto_reconnect=auto_reconnect
            )
            if data is None:
                continue
            yield data

    def fire_event(self, data, tag, timeout=1000):
        """
        Send a single event into the publisher with payload dict "data" and
        event identifier "tag"

        The default is 1000 ms
        """
        if not six.text_type(tag):  # no empty tags allowed
            raise ValueError("Empty tag.")

        if not isinstance(data, MutableMapping):  # data must be dict
            raise ValueError("Dict object expected, not '{0}'.".format(data))

        if not self.cpush:
            if timeout is not None:
                timeout_s = float(timeout) / 1000
            else:
                timeout_s = None
            if not self.connect_pull(timeout=timeout_s):
                return False

        data["_stamp"] = datetime.datetime.utcnow().isoformat()

        tagend = TAGEND
        if six.PY2:
            dump_data = self.serial.dumps(data)
        else:
            # Since the pack / unpack logic here is for local events only,
            # it is safe to change the wire protocol. The mechanism
            # that sends events from minion to master is outside this
            # file.
            dump_data = self.serial.dumps(data, use_bin_type=True)

        serialized_data = salt.utils.dicttrim.trim_dict(
            dump_data,
            self.opts["max_event_size"],
            is_msgpacked=True,
            use_bin_type=six.PY3,
        )
        log.debug("Sending event: tag = %s; data = %s", tag, data)
        event = b"".join(
            [
                salt.utils.stringutils.to_bytes(tag),
                salt.utils.stringutils.to_bytes(tagend),
                serialized_data,
            ]
        )
        msg = salt.utils.stringutils.to_bytes(event, "utf-8")
        if self._run_io_loop_sync:
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                try:
                    self.io_loop.run_sync(lambda: self.pusher.send(msg))
                except Exception as ex:  # pylint: disable=broad-except
                    log.debug(ex)
                    raise
        else:
            self.io_loop.spawn_callback(self.pusher.send, msg)
        return True

    def fire_master(self, data, tag, timeout=1000):
        """'
        Send a single event to the master, with the payload "data" and the
        event identifier "tag".

        Default timeout is 1000ms
        """
        msg = {"tag": tag, "data": data, "events": None, "pretag": None}
        return self.fire_event(msg, "fire_master", timeout)

    def destroy(self):
        if self.subscriber is not None:
            self.close_pub()
        if self.pusher is not None:
            self.close_pull()
        if self._run_io_loop_sync and not self.keep_loop:
            self.io_loop.close()

    def _fire_ret_load_specific_fun(self, load, fun_index=0):
        """
        Helper function for fire_ret_load
        """
        if isinstance(load["fun"], list):
            # Multi-function job
            fun = load["fun"][fun_index]
            # 'retcode' was already validated to exist and be non-zero
            # for the given function in the caller.
            if isinstance(load["retcode"], list):
                # Multi-function ordered
                ret = load.get("return")
                if isinstance(ret, list) and len(ret) > fun_index:
                    ret = ret[fun_index]
                else:
                    ret = {}
                retcode = load["retcode"][fun_index]
            else:
                ret = load.get("return", {})
                ret = ret.get(fun, {})
                retcode = load["retcode"][fun]
        else:
            # Single-function job
            fun = load["fun"]
            ret = load.get("return", {})
            retcode = load["retcode"]

        try:
            for tag, data in six.iteritems(ret):
                data["retcode"] = retcode
                tags = tag.split("_|-")
                if data.get("result") is False:
                    self.fire_event(
                        data, "{0}.{1}".format(tags[0], tags[-1])
                    )  # old dup event
                    data["jid"] = load["jid"]
                    data["id"] = load["id"]
                    data["success"] = False
                    data["return"] = "Error: {0}.{1}".format(tags[0], tags[-1])
                    data["fun"] = fun
                    data["user"] = load["user"]
                    self.fire_event(
                        data,
                        tagify([load["jid"], "sub", load["id"], "error", fun], "job"),
                    )
        except Exception:  # pylint: disable=broad-except
            pass

    def fire_ret_load(self, load):
        """
        Fire events based on information in the return load
        """
        if load.get("retcode") and load.get("fun"):
            if isinstance(load["fun"], list):
                # Multi-function job
                if isinstance(load["retcode"], list):
                    multifunc_ordered = True
                else:
                    multifunc_ordered = False

                for fun_index in range(0, len(load["fun"])):
                    fun = load["fun"][fun_index]
                    if multifunc_ordered:
                        if (
                            len(load["retcode"]) > fun_index
                            and load["retcode"][fun_index]
                            and fun in SUB_EVENT
                        ):
                            # Minion fired a bad retcode, fire an event
                            self._fire_ret_load_specific_fun(load, fun_index)
                    else:
                        if load["retcode"].get(fun, 0) and fun in SUB_EVENT:
                            # Minion fired a bad retcode, fire an event
                            self._fire_ret_load_specific_fun(load, fun_index)
            else:
                # Single-function job
                if load["fun"] in SUB_EVENT:
                    # Minion fired a bad retcode, fire an event
                    self._fire_ret_load_specific_fun(load)

    def set_event_handler(self, event_handler):
        """
        Invoke the event_handler callback each time an event arrives.
        """
        assert not self._run_io_loop_sync

        if not self.cpub:
            self.connect_pub()
        # This will handle reconnects
        return self.subscriber.read_async(event_handler)

    # pylint: disable=W1701
    def __del__(self):
        # skip exceptions in destroy-- since destroy() doesn't cover interpreter
        # shutdown-- where globals start going missing
        try:
            self.destroy()
        except Exception:  # pylint: disable=broad-except
            pass

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()


class MasterEvent(SaltEvent):
    """
    Warning! Use the get_event function or the code will not be
    RAET compatible
    Create a master event management object
    """

    def __init__(
        self,
        sock_dir,
        opts=None,
        listen=True,
        io_loop=None,
        keep_loop=False,
        raise_errors=False,
    ):
        super(MasterEvent, self).__init__(
            "master",
            sock_dir,
            opts,
            listen=listen,
            io_loop=io_loop,
            keep_loop=keep_loop,
            raise_errors=raise_errors,
        )


class LocalClientEvent(MasterEvent):
    """
    Warning! Use the get_event function or the code will not be
    RAET compatible
    This class is just used to differentiate who is handling the events,
    specially on logs, but it's the same as MasterEvent.
    """


class NamespacedEvent(object):
    """
    A wrapper for sending events within a specific base namespace
    """

    def __init__(self, event, base, print_func=None):
        self.event = event
        self.base = base
        self.print_func = print_func

    def fire_event(self, data, tag):
        self.event.fire_event(data, tagify(tag, base=self.base))
        if self.print_func is not None:
            self.print_func(tag, data)

    def destroy(self):
        self.event.destroy()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()


class MinionEvent(SaltEvent):
    """
    Warning! Use the get_event function or the code will not be
    RAET compatible
    Create a master event management object
    """

    def __init__(self, opts, listen=True, io_loop=None, raise_errors=False):
        super(MinionEvent, self).__init__(
            "minion",
            sock_dir=opts.get("sock_dir"),
            opts=opts,
            listen=listen,
            io_loop=io_loop,
            raise_errors=raise_errors,
        )


class AsyncEventPublisher(object):
    """
    An event publisher class intended to run in an ioloop (within a single process)

    TODO: remove references to "minion_event" whenever we need to use this for other things
    """

    def __init__(self, opts, io_loop=None):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        default_minion_sock_dir = self.opts["sock_dir"]
        self.opts.update(opts)

        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()
        self._closing = False

        hash_type = getattr(hashlib, self.opts["hash_type"])
        # Only use the first 10 chars to keep longer hashes from exceeding the
        # max socket path length.
        id_hash = hash_type(
            salt.utils.stringutils.to_bytes(self.opts["id"])
        ).hexdigest()[:10]
        epub_sock_path = os.path.join(
            self.opts["sock_dir"], "minion_event_{0}_pub.ipc".format(id_hash)
        )
        if os.path.exists(epub_sock_path):
            os.unlink(epub_sock_path)
        epull_sock_path = os.path.join(
            self.opts["sock_dir"], "minion_event_{0}_pull.ipc".format(id_hash)
        )
        if os.path.exists(epull_sock_path):
            os.unlink(epull_sock_path)

        if self.opts["ipc_mode"] == "tcp":
            epub_uri = int(self.opts["tcp_pub_port"])
            epull_uri = int(self.opts["tcp_pull_port"])
        else:
            epub_uri = epub_sock_path
            epull_uri = epull_sock_path

        log.debug("%s PUB socket URI: %s", self.__class__.__name__, epub_uri)
        log.debug("%s PULL socket URI: %s", self.__class__.__name__, epull_uri)

        minion_sock_dir = self.opts["sock_dir"]

        if not os.path.isdir(minion_sock_dir):
            # Let's try to create the directory defined on the configuration
            # file
            try:
                os.makedirs(minion_sock_dir, 0o755)
            except OSError as exc:
                log.error("Could not create SOCK_DIR: %s", exc)
                # Let's not fail yet and try using the default path
                if minion_sock_dir == default_minion_sock_dir:
                    # We're already trying the default system path, stop now!
                    raise

                if not os.path.isdir(default_minion_sock_dir):
                    try:
                        os.makedirs(default_minion_sock_dir, 0o755)
                    except OSError as exc:
                        log.error("Could not create SOCK_DIR: %s", exc)
                        # Let's stop at this stage
                        raise

        self.publisher = salt.transport.ipc.IPCMessagePublisher(
            self.opts, epub_uri, io_loop=self.io_loop
        )

        self.puller = salt.transport.ipc.IPCMessageServer(
            epull_uri, io_loop=self.io_loop, payload_handler=self.handle_publish
        )

        log.info("Starting pull socket on %s", epull_uri)
        with salt.utils.files.set_umask(0o177):
            self.publisher.start()
            self.puller.start()

    def handle_publish(self, package, _):
        """
        Get something from epull, publish it out epub, and return the package (or None)
        """
        try:
            self.publisher.publish(package)
            return package
        # Add an extra fallback in case a forked process leeks through
        except Exception:  # pylint: disable=broad-except
            log.critical("Unexpected error while polling minion events", exc_info=True)
            return None

    def close(self):
        if self._closing:
            return
        self._closing = True
        if hasattr(self, "publisher"):
            self.publisher.close()
        if hasattr(self, "puller"):
            self.puller.close()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701


class EventPublisher(salt.utils.process.SignalHandlingProcess):
    """
    The interface that takes master events and republishes them out to anyone
    who wants to listen
    """

    def __init__(self, opts, **kwargs):
        super(EventPublisher, self).__init__(**kwargs)
        self.opts = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.opts.update(opts)
        self._closing = False

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self.__init__(
            state["opts"],
            log_queue=state["log_queue"],
            log_queue_level=state["log_queue_level"],
        )

    def __getstate__(self):
        return {
            "opts": self.opts,
            "log_queue": self.log_queue,
            "log_queue_level": self.log_queue_level,
        }

    def run(self):
        """
        Bind the pub and pull sockets for events
        """
        salt.utils.process.appendproctitle(self.__class__.__name__)
        self.io_loop = salt.ext.tornado.ioloop.IOLoop()
        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            if self.opts["ipc_mode"] == "tcp":
                epub_uri = int(self.opts["tcp_master_pub_port"])
                epull_uri = int(self.opts["tcp_master_pull_port"])
            else:
                epub_uri = os.path.join(self.opts["sock_dir"], "master_event_pub.ipc")
                epull_uri = os.path.join(self.opts["sock_dir"], "master_event_pull.ipc")

            self.publisher = salt.transport.ipc.IPCMessagePublisher(
                self.opts, epub_uri, io_loop=self.io_loop
            )

            self.puller = salt.transport.ipc.IPCMessageServer(
                epull_uri, io_loop=self.io_loop, payload_handler=self.handle_publish,
            )

            # Start the master event publisher
            with salt.utils.files.set_umask(0o177):
                self.publisher.start()
                self.puller.start()
                if self.opts["ipc_mode"] != "tcp" and (
                    self.opts["publisher_acl"] or self.opts["external_auth"]
                ):
                    os.chmod(
                        os.path.join(self.opts["sock_dir"], "master_event_pub.ipc"),
                        0o666,
                    )

            # Make sure the IO loop and respective sockets are closed and
            # destroyed
            Finalize(self, self.close, exitpriority=15)

            self.io_loop.start()

    def handle_publish(self, package, _):
        """
        Get something from epull, publish it out epub, and return the package (or None)
        """
        try:
            self.publisher.publish(package)
            return package
        # Add an extra fallback in case a forked process leeks through
        except Exception:  # pylint: disable=broad-except
            log.critical("Unexpected error while polling master events", exc_info=True)
            return None

    def close(self):
        if self._closing:
            return
        self._closing = True
        if hasattr(self, "publisher"):
            self.publisher.close()
        if hasattr(self, "puller"):
            self.puller.close()
        if hasattr(self, "io_loop"):
            self.io_loop.close()

    def _handle_signals(self, signum, sigframe):
        self.close()
        super(EventPublisher, self)._handle_signals(signum, sigframe)

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701


class EventReturn(salt.utils.process.SignalHandlingProcess):
    """
    A dedicated process which listens to the master event bus and queues
    and forwards events to the specified returner.
    """

    def __init__(self, opts, **kwargs):
        """
        Initialize the EventReturn system

        Return an EventReturn instance
        """
        # This is required because the process is forked and the module no
        # longer exists in the global namespace.
        import salt.minion

        super(EventReturn, self).__init__(**kwargs)

        self.opts = opts
        self.event_return_queue = self.opts["event_return_queue"]
        self.event_return_queue_max_seconds = self.opts.get(
            "event_return_queue_max_seconds", 0
        )
        local_minion_opts = self.opts.copy()
        local_minion_opts["file_client"] = "local"
        self.minion = salt.minion.MasterMinion(local_minion_opts)
        self.event_queue = []
        self.stop = False

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self.__init__(
            state["opts"],
            log_queue=state["log_queue"],
            log_queue_level=state["log_queue_level"],
        )

    def __getstate__(self):
        return {
            "opts": self.opts,
            "log_queue": self.log_queue,
            "log_queue_level": self.log_queue_level,
        }

    def _handle_signals(self, signum, sigframe):
        # Flush and terminate
        if self.event_queue:
            self.flush_events()
        self.stop = True
        super(EventReturn, self)._handle_signals(signum, sigframe)

    def flush_events(self):
        if isinstance(self.opts["event_return"], list):
            # Multiple event returners
            for r in self.opts["event_return"]:
                log.debug("Calling event returner %s, one of many.", r)
                event_return = "{0}.event_return".format(r)
                self._flush_event_single(event_return)
        else:
            # Only a single event returner
            log.debug(
                "Calling event returner %s, only one " "configured.",
                self.opts["event_return"],
            )
            event_return = "{0}.event_return".format(self.opts["event_return"])
            self._flush_event_single(event_return)
        del self.event_queue[:]

    def _flush_event_single(self, event_return):
        if event_return in self.minion.returners:
            try:
                self.minion.returners[event_return](self.event_queue)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Could not store events - returner '%s' raised " "exception: %s",
                    event_return,
                    exc,
                )
                # don't waste processing power unnecessarily on converting a
                # potentially huge dataset to a string
                if log.level <= logging.DEBUG:
                    log.debug(
                        "Event data that caused an exception: %s", self.event_queue
                    )
        else:
            log.error(
                "Could not store return for event(s) - returner " "'%s' not found.",
                event_return,
            )

    def run(self):
        """
        Spin up the multiprocess event returner
        """
        salt.utils.process.appendproctitle(self.__class__.__name__)
        self.event = get_event("master", opts=self.opts, listen=True)
        events = self.event.iter_events(full=True)
        self.event.fire_event({}, "salt/event_listen/start")
        try:
            # events below is a generator, we will iterate until we get the salt/event/exit tag
            oldestevent = None
            for event in events:

                if event["tag"] == "salt/event/exit":
                    # We're done eventing
                    self.stop = True
                if self._filter(event):
                    # This event passed the filter, add it to the queue
                    self.event_queue.append(event)
                too_long_in_queue = False

                # if max_seconds is >0, then we want to make sure we flush the queue
                # every event_return_queue_max_seconds seconds,  If it's 0, don't
                # apply any of this logic
                if self.event_return_queue_max_seconds > 0:
                    rightnow = datetime.datetime.now()
                    if not oldestevent:
                        oldestevent = rightnow
                    age_in_seconds = (rightnow - oldestevent).seconds
                    if age_in_seconds > 0:
                        log.debug(
                            "Oldest event in queue is %s seconds old.", age_in_seconds
                        )
                    if age_in_seconds >= self.event_return_queue_max_seconds:
                        too_long_in_queue = True
                        oldestevent = None
                    else:
                        too_long_in_queue = False

                    if too_long_in_queue:
                        log.debug(
                            "Oldest event has been in queue too long, will flush queue"
                        )

                # If we are over the max queue size or the oldest item in the queue has been there too long
                # then flush the queue
                if (
                    len(self.event_queue) >= self.event_return_queue
                    or too_long_in_queue
                ):
                    log.debug("Flushing %s events.", len(self.event_queue))
                    self.flush_events()
                    oldestevent = None
                if self.stop:
                    # We saw the salt/event/exit tag, we can stop eventing
                    break
        finally:  # flush all we have at this moment
            # No matter what, make sure we flush the queue even when we are exiting
            # and there will be no more events.
            if self.event_queue:
                log.debug("Flushing %s events.", len(self.event_queue))

                self.flush_events()

    def _filter(self, event):
        """
        Take an event and run it through configured filters.

        Returns True if event should be stored, else False
        """
        tag = event["tag"]
        if self.opts["event_return_whitelist"]:
            ret = False
        else:
            ret = True
        for whitelist_match in self.opts["event_return_whitelist"]:
            if fnmatch.fnmatch(tag, whitelist_match):
                ret = True
                break
        for blacklist_match in self.opts["event_return_blacklist"]:
            if fnmatch.fnmatch(tag, blacklist_match):
                ret = False
                break
        return ret


class StateFire(object):
    """
    Evaluate the data from a state run and fire events on the master and minion
    for each returned chunk that is not "green"
    This object is made to only run on a minion
    """

    def __init__(self, opts, auth=None):
        self.opts = opts
        if not auth:
            self.auth = salt.crypt.SAuth(self.opts)
        else:
            self.auth = auth

    def fire_master(self, data, tag, preload=None):
        """
        Fire an event off on the master server

        CLI Example:

        .. code-block:: bash

            salt '*' event.fire_master 'stuff to be in the event' 'tag'
        """
        load = {}
        if preload:
            load.update(preload)

        load.update(
            {
                "id": self.opts["id"],
                "tag": tag,
                "data": data,
                "cmd": "_minion_event",
                "tok": self.auth.gen_token(b"salt"),
            }
        )

        with salt.transport.client.ReqChannel.factory(self.opts) as channel:
            try:
                channel.send(load)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "An exception occurred on fire_master: %s",
                    exc,
                    exc_info_on_loglevel=logging.DEBUG,
                )
        return True

    def fire_running(self, running):
        """
        Pass in a state "running" dict, this is the return dict from a state
        call. The dict will be processed and fire events.

        By default yellows and reds fire events on the master and minion, but
        this can be configured.
        """
        load = {"id": self.opts["id"], "events": [], "cmd": "_minion_event"}
        for stag in sorted(running, key=lambda k: running[k].get("__run_num__", 0)):
            if running[stag]["result"] and not running[stag]["changes"]:
                continue
            tag = "state_{0}_{1}".format(
                six.text_type(running[stag]["result"]),
                "True" if running[stag]["changes"] else "False",
            )
            load["events"].append({"tag": tag, "data": running[stag]})
        with salt.transport.client.ReqChannel.factory(self.opts) as channel:
            try:
                channel.send(load)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "An exception occurred on fire_master: %s",
                    exc,
                    exc_info_on_loglevel=logging.DEBUG,
                )
        return True
