# Author: Ovidiu Predescu
# Date: July 2011
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Bridges between the Twisted reactor and Tornado IOLoop.

This module lets you run applications and libraries written for
Twisted in a Tornado application.  It can be used in two modes,
depending on which library's underlying event loop you want to use.

This module has been tested with Twisted versions 11.0.0 and newer.
"""
# pylint: skip-file

from __future__ import absolute_import, division, print_function

import datetime
import functools
import numbers
import socket
import sys

import twisted.internet.abstract  # type: ignore
from twisted.internet.defer import Deferred  # type: ignore
from twisted.internet.posixbase import PosixReactorBase  # type: ignore
from twisted.internet.interfaces import IReactorFDSet, IDelayedCall, IReactorTime, IReadDescriptor, IWriteDescriptor  # type: ignore
from twisted.python import failure, log  # type: ignore
from twisted.internet import error  # type: ignore
import twisted.names.cache  # type: ignore
import twisted.names.client  # type: ignore
import twisted.names.hosts  # type: ignore
import twisted.names.resolve  # type: ignore

from zope.interface import implementer  # type: ignore

from salt.ext.tornado.concurrent import Future
from salt.ext.tornado.escape import utf8
from salt.ext.tornado import gen
import salt.ext.tornado.ioloop
from salt.ext.tornado.log import app_log
from salt.ext.tornado.netutil import Resolver
from salt.ext.tornado.stack_context import NullContext, wrap
from salt.ext.tornado.ioloop import IOLoop
from salt.ext.tornado.util import timedelta_to_seconds


@implementer(IDelayedCall)
class TornadoDelayedCall(object):
    """DelayedCall object for Tornado."""
    def __init__(self, reactor, seconds, f, *args, **kw):
        self._reactor = reactor
        self._func = functools.partial(f, *args, **kw)
        self._time = self._reactor.seconds() + seconds
        self._timeout = self._reactor._io_loop.add_timeout(self._time,
                                                           self._called)
        self._active = True

    def _called(self):
        self._active = False
        self._reactor._removeDelayedCall(self)
        try:
            self._func()
        except:
            app_log.error("_called caught exception", exc_info=True)

    def getTime(self):
        return self._time

    def cancel(self):
        self._active = False
        self._reactor._io_loop.remove_timeout(self._timeout)
        self._reactor._removeDelayedCall(self)

    def delay(self, seconds):
        self._reactor._io_loop.remove_timeout(self._timeout)
        self._time += seconds
        self._timeout = self._reactor._io_loop.add_timeout(self._time,
                                                           self._called)

    def reset(self, seconds):
        self._reactor._io_loop.remove_timeout(self._timeout)
        self._time = self._reactor.seconds() + seconds
        self._timeout = self._reactor._io_loop.add_timeout(self._time,
                                                           self._called)

    def active(self):
        return self._active


@implementer(IReactorTime, IReactorFDSet)
class TornadoReactor(PosixReactorBase):
    """Twisted reactor built on the Tornado IOLoop.

    `TornadoReactor` implements the Twisted reactor interface on top of
    the Tornado IOLoop.  To use it, simply call `install` at the beginning
    of the application::

        import tornado.platform.twisted
        tornado.platform.twisted.install()
        from twisted.internet import reactor

    When the app is ready to start, call ``IOLoop.current().start()``
    instead of ``reactor.run()``.

    It is also possible to create a non-global reactor by calling
    ``tornado.platform.twisted.TornadoReactor(io_loop)``.  However, if
    the `.IOLoop` and reactor are to be short-lived (such as those used in
    unit tests), additional cleanup may be required.  Specifically, it is
    recommended to call::

        reactor.fireSystemEvent('shutdown')
        reactor.disconnectAll()

    before closing the `.IOLoop`.

    .. versionchanged:: 4.1
       The ``io_loop`` argument is deprecated.
    """
    def __init__(self, io_loop=None):
        if not io_loop:
            io_loop = salt.ext.tornado.ioloop.IOLoop.current()
        self._io_loop = io_loop
        self._readers = {}  # map of reader objects to fd
        self._writers = {}  # map of writer objects to fd
        self._fds = {}  # a map of fd to a (reader, writer) tuple
        self._delayedCalls = {}
        PosixReactorBase.__init__(self)
        self.addSystemEventTrigger('during', 'shutdown', self.crash)

        # IOLoop.start() bypasses some of the reactor initialization.
        # Fire off the necessary events if they weren't already triggered
        # by reactor.run().
        def start_if_necessary():
            if not self._started:
                self.fireSystemEvent('startup')
        self._io_loop.add_callback(start_if_necessary)

    # IReactorTime
    def seconds(self):
        return self._io_loop.time()

    def callLater(self, seconds, f, *args, **kw):
        dc = TornadoDelayedCall(self, seconds, f, *args, **kw)
        self._delayedCalls[dc] = True
        return dc

    def getDelayedCalls(self):
        return [x for x in self._delayedCalls if x._active]

    def _removeDelayedCall(self, dc):
        if dc in self._delayedCalls:
            del self._delayedCalls[dc]

    # IReactorThreads
    def callFromThread(self, f, *args, **kw):
        assert callable(f), "%s is not callable" % f
        with NullContext():
            # This NullContext is mainly for an edge case when running
            # TwistedIOLoop on top of a TornadoReactor.
            # TwistedIOLoop.add_callback uses reactor.callFromThread and
            # should not pick up additional StackContexts along the way.
            self._io_loop.add_callback(f, *args, **kw)

    # We don't need the waker code from the super class, Tornado uses
    # its own waker.
    def installWaker(self):
        pass

    def wakeUp(self):
        pass

    # IReactorFDSet
    def _invoke_callback(self, fd, events):
        if fd not in self._fds:
            return
        (reader, writer) = self._fds[fd]
        if reader:
            err = None
            if reader.fileno() == -1:
                err = error.ConnectionLost()
            elif events & IOLoop.READ:
                err = log.callWithLogger(reader, reader.doRead)
            if err is None and events & IOLoop.ERROR:
                err = error.ConnectionLost()
            if err is not None:
                self.removeReader(reader)
                reader.readConnectionLost(failure.Failure(err))
        if writer:
            err = None
            if writer.fileno() == -1:
                err = error.ConnectionLost()
            elif events & IOLoop.WRITE:
                err = log.callWithLogger(writer, writer.doWrite)
            if err is None and events & IOLoop.ERROR:
                err = error.ConnectionLost()
            if err is not None:
                self.removeWriter(writer)
                writer.writeConnectionLost(failure.Failure(err))

    def addReader(self, reader):
        if reader in self._readers:
            # Don't add the reader if it's already there
            return
        fd = reader.fileno()
        self._readers[reader] = fd
        if fd in self._fds:
            (_, writer) = self._fds[fd]
            self._fds[fd] = (reader, writer)
            if writer:
                # We already registered this fd for write events,
                # update it for read events as well.
                self._io_loop.update_handler(fd, IOLoop.READ | IOLoop.WRITE)
        else:
            with NullContext():
                self._fds[fd] = (reader, None)
                self._io_loop.add_handler(fd, self._invoke_callback,
                                          IOLoop.READ)

    def addWriter(self, writer):
        if writer in self._writers:
            return
        fd = writer.fileno()
        self._writers[writer] = fd
        if fd in self._fds:
            (reader, _) = self._fds[fd]
            self._fds[fd] = (reader, writer)
            if reader:
                # We already registered this fd for read events,
                # update it for write events as well.
                self._io_loop.update_handler(fd, IOLoop.READ | IOLoop.WRITE)
        else:
            with NullContext():
                self._fds[fd] = (None, writer)
                self._io_loop.add_handler(fd, self._invoke_callback,
                                          IOLoop.WRITE)

    def removeReader(self, reader):
        if reader in self._readers:
            fd = self._readers.pop(reader)
            (_, writer) = self._fds[fd]
            if writer:
                # We have a writer so we need to update the IOLoop for
                # write events only.
                self._fds[fd] = (None, writer)
                self._io_loop.update_handler(fd, IOLoop.WRITE)
            else:
                # Since we have no writer registered, we remove the
                # entry from _fds and unregister the handler from the
                # IOLoop
                del self._fds[fd]
                self._io_loop.remove_handler(fd)

    def removeWriter(self, writer):
        if writer in self._writers:
            fd = self._writers.pop(writer)
            (reader, _) = self._fds[fd]
            if reader:
                # We have a reader so we need to update the IOLoop for
                # read events only.
                self._fds[fd] = (reader, None)
                self._io_loop.update_handler(fd, IOLoop.READ)
            else:
                # Since we have no reader registered, we remove the
                # entry from the _fds and unregister the handler from
                # the IOLoop.
                del self._fds[fd]
                self._io_loop.remove_handler(fd)

    def removeAll(self):
        return self._removeAll(self._readers, self._writers)

    def getReaders(self):
        return self._readers.keys()

    def getWriters(self):
        return self._writers.keys()

    # The following functions are mainly used in twisted-style test cases;
    # it is expected that most users of the TornadoReactor will call
    # IOLoop.start() instead of Reactor.run().
    def stop(self):
        PosixReactorBase.stop(self)
        fire_shutdown = functools.partial(self.fireSystemEvent, "shutdown")
        self._io_loop.add_callback(fire_shutdown)

    def crash(self):
        PosixReactorBase.crash(self)
        self._io_loop.stop()

    def doIteration(self, delay):
        raise NotImplementedError("doIteration")

    def mainLoop(self):
        # Since this class is intended to be used in applications
        # where the top-level event loop is ``io_loop.start()`` rather
        # than ``reactor.run()``, it is implemented a little
        # differently than other Twisted reactors. We override
        # ``mainLoop`` instead of ``doIteration`` and must implement
        # timed call functionality on top of `.IOLoop.add_timeout`
        # rather than using the implementation in
        # ``PosixReactorBase``.
        self._io_loop.start()


class _TestReactor(TornadoReactor):
    """Subclass of TornadoReactor for use in unittests.

    This can't go in the test.py file because of import-order dependencies
    with the Twisted reactor test builder.
    """
    def __init__(self):
        # always use a new ioloop
        super(_TestReactor, self).__init__(IOLoop())

    def listenTCP(self, port, factory, backlog=50, interface=''):
        # default to localhost to avoid firewall prompts on the mac
        if not interface:
            interface = '127.0.0.1'
        return super(_TestReactor, self).listenTCP(
            port, factory, backlog=backlog, interface=interface)

    def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
        if not interface:
            interface = '127.0.0.1'
        return super(_TestReactor, self).listenUDP(
            port, protocol, interface=interface, maxPacketSize=maxPacketSize)


def install(io_loop=None):
    """Install this package as the default Twisted reactor.

    ``install()`` must be called very early in the startup process,
    before most other twisted-related imports. Conversely, because it
    initializes the `.IOLoop`, it cannot be called before
    `.fork_processes` or multi-process `~.TCPServer.start`. These
    conflicting requirements make it difficult to use `.TornadoReactor`
    in multi-process mode, and an external process manager such as
    ``supervisord`` is recommended instead.

    .. versionchanged:: 4.1
       The ``io_loop`` argument is deprecated.

    """
    if not io_loop:
        io_loop = salt.ext.tornado.ioloop.IOLoop.current()
    reactor = TornadoReactor(io_loop)
    from twisted.internet.main import installReactor  # type: ignore
    installReactor(reactor)
    return reactor


@implementer(IReadDescriptor, IWriteDescriptor)
class _FD(object):
    def __init__(self, fd, fileobj, handler):
        self.fd = fd
        self.fileobj = fileobj
        self.handler = handler
        self.reading = False
        self.writing = False
        self.lost = False

    def fileno(self):
        return self.fd

    def doRead(self):
        if not self.lost:
            self.handler(self.fileobj, salt.ext.tornado.ioloop.IOLoop.READ)

    def doWrite(self):
        if not self.lost:
            self.handler(self.fileobj, salt.ext.tornado.ioloop.IOLoop.WRITE)

    def connectionLost(self, reason):
        if not self.lost:
            self.handler(self.fileobj, salt.ext.tornado.ioloop.IOLoop.ERROR)
            self.lost = True

    def logPrefix(self):
        return ''


class TwistedIOLoop(salt.ext.tornado.ioloop.IOLoop):
    """IOLoop implementation that runs on Twisted.

    `TwistedIOLoop` implements the Tornado IOLoop interface on top of
    the Twisted reactor. Recommended usage::

        from salt.ext.tornado.platform.twisted import TwistedIOLoop
        from twisted.internet import reactor
        TwistedIOLoop().install()
        # Set up your tornado application as usual using `IOLoop.instance`
        reactor.run()

    Uses the global Twisted reactor by default.  To create multiple
    ``TwistedIOLoops`` in the same process, you must pass a unique reactor
    when constructing each one.

    Not compatible with `tornado.process.Subprocess.set_exit_callback`
    because the ``SIGCHLD`` handlers used by Tornado and Twisted conflict
    with each other.

    See also :meth:`tornado.ioloop.IOLoop.install` for general notes on
    installing alternative IOLoops.
    """
    def initialize(self, reactor=None, **kwargs):
        super(TwistedIOLoop, self).initialize(**kwargs)
        if reactor is None:
            import twisted.internet.reactor  # type: ignore
            reactor = twisted.internet.reactor
        self.reactor = reactor
        self.fds = {}

    def close(self, all_fds=False):
        fds = self.fds
        self.reactor.removeAll()
        for c in self.reactor.getDelayedCalls():
            c.cancel()
        if all_fds:
            for fd in fds.values():
                self.close_fd(fd.fileobj)

    def add_handler(self, fd, handler, events):
        if fd in self.fds:
            raise ValueError('fd %s added twice' % fd)
        fd, fileobj = self.split_fd(fd)
        self.fds[fd] = _FD(fd, fileobj, wrap(handler))
        if events & salt.ext.tornado.ioloop.IOLoop.READ:
            self.fds[fd].reading = True
            self.reactor.addReader(self.fds[fd])
        if events & salt.ext.tornado.ioloop.IOLoop.WRITE:
            self.fds[fd].writing = True
            self.reactor.addWriter(self.fds[fd])

    def update_handler(self, fd, events):
        fd, fileobj = self.split_fd(fd)
        if events & salt.ext.tornado.ioloop.IOLoop.READ:
            if not self.fds[fd].reading:
                self.fds[fd].reading = True
                self.reactor.addReader(self.fds[fd])
        else:
            if self.fds[fd].reading:
                self.fds[fd].reading = False
                self.reactor.removeReader(self.fds[fd])
        if events & salt.ext.tornado.ioloop.IOLoop.WRITE:
            if not self.fds[fd].writing:
                self.fds[fd].writing = True
                self.reactor.addWriter(self.fds[fd])
        else:
            if self.fds[fd].writing:
                self.fds[fd].writing = False
                self.reactor.removeWriter(self.fds[fd])

    def remove_handler(self, fd):
        fd, fileobj = self.split_fd(fd)
        if fd not in self.fds:
            return
        self.fds[fd].lost = True
        if self.fds[fd].reading:
            self.reactor.removeReader(self.fds[fd])
        if self.fds[fd].writing:
            self.reactor.removeWriter(self.fds[fd])
        del self.fds[fd]

    def start(self):
        old_current = IOLoop.current(instance=False)
        try:
            self._setup_logging()
            self.make_current()
            self.reactor.run()
        finally:
            if old_current is None:
                IOLoop.clear_current()
            else:
                old_current.make_current()

    def stop(self):
        self.reactor.crash()

    def add_timeout(self, deadline, callback, *args, **kwargs):
        # This method could be simplified (since tornado 4.0) by
        # overriding call_at instead of add_timeout, but we leave it
        # for now as a test of backwards-compatibility.
        if isinstance(deadline, numbers.Real):
            delay = max(deadline - self.time(), 0)
        elif isinstance(deadline, datetime.timedelta):
            delay = timedelta_to_seconds(deadline)
        else:
            raise TypeError("Unsupported deadline %r")
        return self.reactor.callLater(
            delay, self._run_callback,
            functools.partial(wrap(callback), *args, **kwargs))

    def remove_timeout(self, timeout):
        if timeout.active():
            timeout.cancel()

    def add_callback(self, callback, *args, **kwargs):
        self.reactor.callFromThread(
            self._run_callback,
            functools.partial(wrap(callback), *args, **kwargs))

    def add_callback_from_signal(self, callback, *args, **kwargs):
        self.add_callback(callback, *args, **kwargs)


class TwistedResolver(Resolver):
    """Twisted-based asynchronous resolver.

    This is a non-blocking and non-threaded resolver.  It is
    recommended only when threads cannot be used, since it has
    limitations compared to the standard ``getaddrinfo``-based
    `~tornado.netutil.Resolver` and
    `~tornado.netutil.ThreadedResolver`.  Specifically, it returns at
    most one result, and arguments other than ``host`` and ``family``
    are ignored.  It may fail to resolve when ``family`` is not
    ``socket.AF_UNSPEC``.

    Requires Twisted 12.1 or newer.

    .. versionchanged:: 4.1
       The ``io_loop`` argument is deprecated.
    """
    def initialize(self, io_loop=None):
        self.io_loop = io_loop or IOLoop.current()
        # partial copy of twisted.names.client.createResolver, which doesn't
        # allow for a reactor to be passed in.
        self.reactor = salt.ext.tornado.platform.twisted.TornadoReactor(io_loop)

        host_resolver = twisted.names.hosts.Resolver('/etc/hosts')
        cache_resolver = twisted.names.cache.CacheResolver(reactor=self.reactor)
        real_resolver = twisted.names.client.Resolver('/etc/resolv.conf',
                                                      reactor=self.reactor)
        self.resolver = twisted.names.resolve.ResolverChain(
            [host_resolver, cache_resolver, real_resolver])

    @gen.coroutine
    def resolve(self, host, port, family=0):
        # getHostByName doesn't accept IP addresses, so if the input
        # looks like an IP address just return it immediately.
        if twisted.internet.abstract.isIPAddress(host):
            resolved = host
            resolved_family = socket.AF_INET
        elif twisted.internet.abstract.isIPv6Address(host):
            resolved = host
            resolved_family = socket.AF_INET6
        else:
            deferred = self.resolver.getHostByName(utf8(host))
            resolved = yield gen.Task(deferred.addBoth)
            if isinstance(resolved, failure.Failure):
                try:
                    resolved.raiseException()
                except twisted.names.error.DomainError as e:
                    raise IOError(e)
            elif twisted.internet.abstract.isIPAddress(resolved):
                resolved_family = socket.AF_INET
            elif twisted.internet.abstract.isIPv6Address(resolved):
                resolved_family = socket.AF_INET6
            else:
                resolved_family = socket.AF_UNSPEC
        if family != socket.AF_UNSPEC and family != resolved_family:
            raise Exception('Requested socket family %d but got %d' %
                            (family, resolved_family))
        result = [
            (resolved_family, (resolved, port)),
        ]
        raise gen.Return(result)


if hasattr(gen.convert_yielded, 'register'):
    @gen.convert_yielded.register(Deferred)  # type: ignore
    def _(d):
        f = Future()

        def errback(failure):
            try:
                failure.raiseException()
                # Should never happen, but just in case
                raise Exception("errback called without error")
            except:
                f.set_exc_info(sys.exc_info())
        d.addCallbacks(f.set_result, errback)
        return f
