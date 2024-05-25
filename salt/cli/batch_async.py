"""
Execute a job on the targeted minions by using a moving window of fixed size `batch`.
"""

import asyncio
import logging
import re
import tornado

import salt.client
import salt.utils.event
from salt.cli.batch import batch_get_eauth, batch_get_opts, get_bnum
from tornado.iostream import StreamClosedError

log = logging.getLogger(__name__)


__SHARED_EVENTS_CHANNEL = None


def _get_shared_events_channel(opts, io_loop):
    global __SHARED_EVENTS_CHANNEL
    if __SHARED_EVENTS_CHANNEL is None:
        __SHARED_EVENTS_CHANNEL = SharedEventsChannel(opts, io_loop)
    return __SHARED_EVENTS_CHANNEL


def _destroy_unused_shared_events_channel():
    global __SHARED_EVENTS_CHANNEL
    if __SHARED_EVENTS_CHANNEL is not None and __SHARED_EVENTS_CHANNEL.destroy_unused():
        __SHARED_EVENTS_CHANNEL = None


def batch_async_required(opts, minions, extra):
    """
    Check opts to identify if batch async is required for the operation.
    """
    if not isinstance(minions, list):
        return False
    batch_async_opts = opts.get("batch_async", {})
    batch_async_threshold = (
        batch_async_opts.get("threshold", 1)
        if isinstance(batch_async_opts, dict)
        else 1
    )
    if batch_async_threshold == -1:
        batch_size = get_bnum(extra, minions, True)
        return len(minions) >= batch_size
    elif batch_async_threshold > 0:
        return len(minions) >= batch_async_threshold
    return False


class SharedEventsChannel:
    def __init__(self, opts, io_loop):
        self.io_loop = io_loop
        self.local_client = salt.client.get_local_client(
            opts["conf_file"], io_loop=self.io_loop
        )
        self.master_event = salt.utils.event.get_event(
            "master",
            sock_dir=self.local_client.opts["sock_dir"],
            opts=self.local_client.opts,
            listen=True,
            io_loop=self.io_loop,
            keep_loop=True,
        )
        self.master_event.set_event_handler(self.__handle_event)
        if self.master_event.subscriber._stream:
            self.master_event.subscriber._stream.set_close_callback(self.__handle_close)
        self._re_tag_ret_event = re.compile(r"salt\/job\/(\d+)\/ret\/.*")
        self._subscribers = {}
        self._subscriptions = {}
        self._used_by = set()
        batch_async_opts = opts.get("batch_async", {})
        if not isinstance(batch_async_opts, dict):
            batch_async_opts = {}
        self._subscriber_reconnect_tries = batch_async_opts.get(
            "subscriber_reconnect_tries", 5
        )
        self._subscriber_reconnect_interval = batch_async_opts.get(
            "subscriber_reconnect_interval", 1.0
        )
        self._reconnecting_subscriber = False

    def subscribe(self, jid, op, subscriber_id, handler):
        if subscriber_id not in self._subscribers:
            self._subscribers[subscriber_id] = set()
        if jid not in self._subscriptions:
            self._subscriptions[jid] = []
        self._subscribers[subscriber_id].add(jid)
        if (op, subscriber_id, handler) not in self._subscriptions[jid]:
            self._subscriptions[jid].append((op, subscriber_id, handler))
        if not self.master_event.subscriber.connected:
            self.__reconnect_subscriber()

    def unsubscribe(self, jid, op, subscriber_id):
        if subscriber_id not in self._subscribers:
            return
        jids = self._subscribers[subscriber_id].copy()
        if jid is not None:
            jids = set(jid)
        for i_jid in jids:
            self._subscriptions[i_jid] = list(
                filter(
                    lambda x: not (op in (x[0], None) and x[1] == subscriber_id),
                    self._subscriptions.get(i_jid, []),
                )
            )
            self._subscribers[subscriber_id].discard(i_jid)
        self._subscriptions = dict(filter(lambda x: x[1], self._subscriptions.items()))
        if not self._subscribers[subscriber_id]:
            del self._subscribers[subscriber_id]

    async def __handle_close(self):
        if not self._subscriptions:
            return
        log.warning("Master Event Subscriber was closed. Trying to reconnect...")
        await self.__reconnect_subscriber()

    async def __handle_event(self, raw):
        if self.master_event is None:
            return
        try:
            tag, data = self.master_event.unpack(raw)
            tag_match = self._re_tag_ret_event.match(tag)
            if tag_match:
                jid = tag_match.group(1)
                if jid in self._subscriptions:
                    for op, _, handler in self._subscriptions[jid]:
                        await handler(tag, data, op)
        except Exception as ex:  # pylint: disable=W0703
            log.error(
                "Exception occured while processing event: %s: %s",
                tag,
                ex,
                exc_info=True,
            )

    async def __reconnect_subscriber(self):
        if self.master_event.subscriber.connected() or self._reconnecting_subscriber:
            return
        self._reconnecting_subscriber = True
        max_tries = max(1, int(self._subscriber_reconnect_tries))
        _try = 1
        while _try <= max_tries:
            log.info(
                "Trying to reconnect to event publisher (try %d of %d) ...",
                _try,
                max_tries,
            )
            try:
                await self.master_event.subscriber.connect()
            except StreamClosedError:
                log.warning(
                    "Unable to reconnect to event publisher (try %d of %d)",
                    _try,
                    max_tries,
                )
            if self.master_event.subscriber.connected():
                self.master_event.subscriber.stream.set_close_callback(
                    self.__handle_close
                )
                log.info("Event publisher connection restored")
                self._reconnecting_subscriber = False
                return
            if _try < max_tries:
                await asyncio.sleep(self._subscriber_reconnect_interval)
            _try += 1
        self._reconnecting_subscriber = False

    def use(self, subscriber_id):
        self._used_by.add(subscriber_id)
        return self

    def unuse(self, subscriber_id):
        self._used_by.discard(subscriber_id)

    def destroy_unused(self):
        if self._used_by:
            return False
        self.master_event.remove_event_handler(self.__handle_event)
        self.master_event.destroy()
        self.master_event = None
        self.local_client.destroy()
        self.local_client = None
        return True


class BatchAsync:
    """
    Run a job on the targeted minions by using a moving window of fixed size `batch`.

    ``BatchAsync`` is used to execute a job on the targeted minions by keeping
    the number of concurrent running minions to the size of `batch` parameter.

    The control parameters are:
        - batch: number/percentage of concurrent running minions
        - batch_delay: minimum wait time between batches
        - batch_presence_ping_timeout: time to wait for presence pings before starting the batch
        - gather_job_timeout: `find_job` timeout
        - timeout: time to wait before firing a `find_job`

    When the batch starts, a `start` event is fired:
         - tag: salt/batch/<batch-jid>/start
         - data: {
             "available_minions": self.minions,
             "down_minions": targeted_minions - presence_ping_minions
           }

    When the batch ends, a `done` event is fired:
        - tag: salt/batch/<batch-jid>/done
        - data: {
             "available_minions": self.minions,
             "down_minions": targeted_minions - presence_ping_minions
             "done_minions": self.done_minions,
             "timedout_minions": self.timedout_minions
         }
    """

    def __init__(self, opts, jid_gen, clear_load):
        self.extra_job_kwargs = {}
        kwargs = clear_load.get("kwargs", {})
        for kwarg in ("module_executors", "executor_opts"):
            if kwarg in kwargs:
                self.extra_job_kwargs[kwarg] = kwargs[kwarg]
            elif kwarg in opts:
                self.extra_job_kwargs[kwarg] = opts[kwarg]
        self.io_loop = tornado.ioloop.IOLoop.current()
        self.events_channel = _get_shared_events_channel(opts, self.io_loop).use(
            id(self)
        )
        if "gather_job_timeout" in clear_load["kwargs"]:
            clear_load["gather_job_timeout"] = clear_load["kwargs"].pop(
                "gather_job_timeout"
            )
        else:
            clear_load["gather_job_timeout"] = self.events_channel.local_client.opts[
                "gather_job_timeout"
            ]
        self.batch_presence_ping_timeout = clear_load["kwargs"].get(
            "batch_presence_ping_timeout", None
        )
        self.batch_delay = clear_load["kwargs"].get("batch_delay", 1)
        self.opts = batch_get_opts(
            clear_load.pop("tgt"),
            clear_load.pop("fun"),
            clear_load["kwargs"].pop("batch"),
            self.events_channel.local_client.opts,
            **clear_load,
        )
        self.eauth = batch_get_eauth(clear_load["kwargs"])
        self.metadata = clear_load["kwargs"].get("metadata", {})
        self.minions = set()
        self.targeted_minions = set()
        self.timedout_minions = set()
        self.done_minions = set()
        self.active = set()
        self.initialized = False
        self.jid_gen = jid_gen
        self.ping_jid = jid_gen()
        self.batch_jid = jid_gen()
        self.find_job_returned = set()
        self.metadata.update({"batch_jid": self.batch_jid, "ping_jid": self.ping_jid})
        self.ended = False
        self.event = self.events_channel.master_event
        self.scheduled = False

    def __set_event_handler(self):
        self.events_channel.subscribe(
            self.ping_jid, "ping_return", id(self), self.__event_handler
        )
        self.events_channel.subscribe(
            self.batch_jid, "batch_run", id(self), self.__event_handler
        )

    async def __event_handler(self, tag, data, op):
        if not self.event:
            return
        try:
            minion = data["id"]
            if op == "ping_return":
                self.minions.add(minion)
                if self.targeted_minions == self.minions:
                    await self.start_batch()
            elif op == "find_job_return":
                if data.get("return", None):
                    self.find_job_returned.add(minion)
            elif op == "batch_run":
                if minion in self.active:
                    self.active.remove(minion)
                    self.done_minions.add(minion)
                    await self.schedule_next()
        except Exception as ex:  # pylint: disable=W0703
            log.error(
                "Exception occured while processing event: %s: %s",
                tag,
                ex,
                exc_info=True,
            )

    def _get_next(self):
        to_run = (
            self.minions.difference(self.done_minions)
            .difference(self.active)
            .difference(self.timedout_minions)
        )
        next_batch_size = min(
            len(to_run),  # partial batch (all left)
            self.batch_size - len(self.active),  # full batch or available slots
        )
        return set(list(to_run)[:next_batch_size])

    async def check_find_job(self, batch_minions, jid):
        """
        Check if the job with specified ``jid`` was finished on the minions
        """
        if not self.event:
            return
        self.events_channel.unsubscribe(jid, "find_job_return", id(self))

        timedout_minions = batch_minions.difference(self.find_job_returned).difference(
            self.done_minions
        )
        self.timedout_minions = self.timedout_minions.union(timedout_minions)
        self.active = self.active.difference(self.timedout_minions)
        running = batch_minions.difference(self.done_minions).difference(
            self.timedout_minions
        )

        if timedout_minions:
            await self.schedule_next()

        if self.event and running:
            self.find_job_returned = self.find_job_returned.difference(running)
            await self.find_job(running)

    async def find_job(self, minions):
        """
        Find if the job was finished on the minions
        """
        if not self.event:
            return
        not_done = minions.difference(self.done_minions).difference(
            self.timedout_minions
        )
        if not not_done:
            return
        try:
            jid = self.jid_gen()
            self.events_channel.subscribe(
                jid, "find_job_return", id(self), self.__event_handler
            )
            ret = await self.events_channel.local_client.run_job_async(
                not_done,
                "saltutil.find_job",
                [self.batch_jid],
                "list",
                gather_job_timeout=self.opts["gather_job_timeout"],
                jid=jid,
                io_loop=self.io_loop,
                listen=False,
                **self.eauth,
            )
            await asyncio.sleep(self.opts["gather_job_timeout"])
            if self.event:
                await self.check_find_job(not_done, jid)
        except Exception as ex:  # pylint: disable=W0703
            log.error(
                "Exception occured handling batch async: %s. Aborting execution.",
                ex,
                exc_info=True,
            )
            self.close_safe()

    async def start(self):
        """
        Start the batch execution
        """
        if not self.event:
            return
        self.__set_event_handler()
        ping_return = await self.events_channel.local_client.run_job_async(
            self.opts["tgt"],
            "test.ping",
            [],
            self.opts.get("selected_target_option", self.opts.get("tgt_type", "glob")),
            gather_job_timeout=self.opts["gather_job_timeout"],
            jid=self.ping_jid,
            metadata=self.metadata,
            io_loop=self.io_loop,
            listen=False,
            **self.eauth,
        )
        self.targeted_minions = set(ping_return["minions"])
        # start batching even if not all minions respond to ping
        await asyncio.sleep(
            self.batch_presence_ping_timeout or self.opts["gather_job_timeout"]
        )
        if self.event:
            await self.start_batch()

    async def start_batch(self):
        """
        Fire `salt/batch/*/start` and continue batch with `run_next`
        """
        if self.initialized:
            return
        self.batch_size = get_bnum(self.opts, self.minions, True)
        self.initialized = True
        data = {
            "available_minions": self.minions,
            "down_minions": self.targeted_minions.difference(self.minions),
            "metadata": self.metadata,
        }
        await self.events_channel.master_event.fire_event_async(
            data, f"salt/batch/{self.batch_jid}/start"
        )
        if self.event:
            await self.run_next()

    async def end_batch(self):
        """
        End the batch and call safe closing
        """
        left = self.minions.symmetric_difference(
            self.done_minions.union(self.timedout_minions)
        )
        # Send salt/batch/*/done only if there is nothing to do
        # and the event haven't been sent already
        if left or self.ended:
            return
        self.ended = True
        data = {
            "available_minions": self.minions,
            "down_minions": self.targeted_minions.difference(self.minions),
            "done_minions": self.done_minions,
            "timedout_minions": self.timedout_minions,
            "metadata": self.metadata,
        }
        await self.events_channel.master_event.fire_event_async(
            data, f"salt/batch/{self.batch_jid}/done"
        )

        # release to the IOLoop to allow the event to be published
        # before closing batch async execution
        await asyncio.sleep(1)
        self.close_safe()

    def close_safe(self):
        if self.events_channel is not None:
            self.events_channel.unsubscribe(None, None, id(self))
            self.events_channel.unuse(id(self))
            self.events_channel = None
            _destroy_unused_shared_events_channel()
        self.event = None

    async def schedule_next(self):
        if self.scheduled:
            return
        self.scheduled = True
        # call later so that we maybe gather more returns
        await asyncio.sleep(self.batch_delay)
        if self.event:
            await self.run_next()

    async def run_next(self):
        """
        Continue batch execution with the next targets
        """
        self.scheduled = False
        next_batch = self._get_next()
        if not next_batch:
            await self.end_batch()
            return
        self.active = self.active.union(next_batch)
        try:
            ret = await self.events_channel.local_client.run_job_async(
                next_batch,
                self.opts["fun"],
                self.opts["arg"],
                "list",
                raw=self.opts.get("raw", False),
                ret=self.opts.get("return", ""),
                gather_job_timeout=self.opts["gather_job_timeout"],
                jid=self.batch_jid,
                metadata=self.metadata,
                io_loop=self.io_loop,
                listen=False,
                **self.eauth,
                **self.extra_job_kwargs,
            )

            await asyncio.sleep(self.opts["timeout"])

            # The batch can be done already at this point, which means no self.event
            if self.event:
                await self.find_job(set(next_batch))
        except Exception as ex:  # pylint: disable=W0703
            log.error(
                "Error in scheduling next batch: %s. Aborting execution",
                ex,
                exc_info=True,
            )
            self.active = self.active.difference(next_batch)
            self.close_safe()
