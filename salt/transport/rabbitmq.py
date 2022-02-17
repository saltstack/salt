"""
Rabbitmq transport classes
"""
import functools
import hashlib
import logging
import os
import random
import signal
import sys
import threading
from typing import Any, Callable

# pylint: disable=3rd-party-module-not-gated
import pika
import salt.auth
import salt.crypt
import salt.ext.tornado
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.payload
import salt.transport.client
import salt.transport.server
import salt.utils.event
import salt.utils.files
import salt.utils.minions
import salt.utils.process
import salt.utils.stringutils
import salt.utils.verify
import salt.utils.versions
import salt.utils.zeromq
from pika import BasicProperties, SelectConnection
from pika.exceptions import (
    AMQPConnectionError,
    ChannelClosedByBroker,
    ConnectionClosedByBroker,
    StreamLostError,
)
from pika.exchange_type import ExchangeType
from pika.spec import PERSISTENT_DELIVERY_MODE
from salt.exceptions import SaltReqTimeoutError

# pylint: enable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


class RMQWrapperBase:
    """
    Base class for things that are common to connections and channels
    """

    def __init__(self, opts, **kwargs):
        self.log = (
            kwargs["log"]
            if "log" in kwargs
            else logging.getLogger(self.__class__.__name__)
        )

        self._opts = opts
        self._validate_set_broker_topology(self._opts, **kwargs)

        self._connection = None
        self._closing = False

    def _validate_set_broker_topology(self, opts, **kwargs):
        """
        Validate broker topology and set private variables. For example:
            {
                "transport: rabbitmq",
                "transport_rabbitmq_url": "amqp://salt:salt@localhost",
                "transport_rabbitmq_create_topology_ondemand": "True",
                "transport_rabbitmq_publisher_exchange_name":" "exchange_to_publish_messages",
                "transport_rabbitmq_consumer_exchange_name": "exchange_to_bind_queue_to_receive_messages_from",
                "transport_rabbitmq_consumer_queue_name": "queue_to_consume_messages_from",

                "transport_rabbitmq_consumer_queue_declare_arguments": {
                    "x-expires": 600000,
                    "x-max-length": 10000,
                    "x-queue-type": "quorum",
                    "x-queue-mode": "lazy",
                    "x-message-ttl": 259200000,
                },
                "transport_rabbitmq_publisher_exchange_declare_arguments": ""
                "transport_rabbitmq_consumer_exchange_declare_arguments": ""
            }
        """

        # rmq broker url (encodes credentials, address, vhost, timeouts, etc.).
        # See https://www.rabbitmq.com/uri-spec.html
        self._url = (
            opts["transport_rabbitmq_url"]
            if "transport_rabbitmq_url" in opts
            else "amqp://salt:salt@localhost"
        )
        if not self._url:
            raise ValueError("RabbitMQ URL must be set")

        # optionally create the RMQ topology if instructed
        # some use cases require topology creation out-of-band with permissions
        # rmq consumer queue arguments
        create_topology_key = "transport_rabbitmq_create_topology_ondemand"
        self._create_topology_ondemand = (
            kwargs.get(create_topology_key, False)
            if create_topology_key in kwargs
            else opts.get(create_topology_key, False)
        )

        # publisher exchange name
        publisher_exchange_name_key = "transport_rabbitmq_publisher_exchange_name"
        if (
            publisher_exchange_name_key not in opts
            and publisher_exchange_name_key not in kwargs
        ):
            raise KeyError(
                "Missing configuration key {!r}".format(publisher_exchange_name_key)
            )
        self._publisher_exchange_name = (
            kwargs.get(publisher_exchange_name_key)
            if publisher_exchange_name_key in kwargs
            else opts[publisher_exchange_name_key]
        )

        # consumer exchange name
        consumer_exchange_name_key = "transport_rabbitmq_consumer_exchange_name"
        if (
            consumer_exchange_name_key not in opts
            and consumer_exchange_name_key not in kwargs
        ):
            raise KeyError(
                "Missing configuration key {!r}".format(consumer_exchange_name_key)
            )
        self._consumer_exchange_name = (
            kwargs.get(consumer_exchange_name_key)
            if consumer_exchange_name_key in kwargs
            else opts[consumer_exchange_name_key]
        )

        # consumer queue name
        consumer_queue_name_key = "transport_rabbitmq_consumer_queue_name"
        if (
            consumer_queue_name_key not in opts
            and consumer_queue_name_key not in kwargs
        ):
            raise KeyError(
                "Missing configuration key {!r}".format(consumer_queue_name_key)
            )
        self._consumer_queue_name = (
            kwargs.get(consumer_queue_name_key)
            if consumer_queue_name_key in kwargs
            else opts[consumer_queue_name_key]
        )

        # rmq consumer exchange arguments when declaring exchanges
        consumer_exchange_declare_arguments_key = (
            "transport_rabbitmq_consumer_exchange_declare_arguments"
        )
        self._consumer_exchange_declare_arguments = (
            kwargs.get(consumer_exchange_declare_arguments_key)
            if consumer_exchange_declare_arguments_key in kwargs
            else opts.get(consumer_exchange_declare_arguments_key, None)
        )

        # rmq consumer queue arguments when declaring queues
        consumer_queue_declare_arguments_key = (
            "transport_rabbitmq_consumer_queue_declare_arguments"
        )
        self._consumer_queue_declare_arguments = (
            kwargs.get(consumer_queue_declare_arguments_key)
            if consumer_queue_declare_arguments_key in kwargs
            else opts.get(consumer_queue_declare_arguments_key, None)
        )

        # rmq publisher exchange arguments when declaring exchanges
        publisher_exchange_declare_arguments_key = (
            "transport_rabbitmq_publisher_exchange_declare_arguments"
        )
        self._publisher_exchange_declare_arguments = (
            kwargs.get(publisher_exchange_declare_arguments_key)
            if publisher_exchange_declare_arguments_key in kwargs
            else opts.get(publisher_exchange_declare_arguments_key, None)
        )

        # rmq publisher exchange arguments when declaring exchanges
        message_auto_ack_key = "transport_rabbitmq_message_auto_ack"
        self._message_auto_ack = (
            kwargs.get(message_auto_ack_key)
            if message_auto_ack_key in kwargs
            else opts.get(message_auto_ack_key, True)
        )

    @property
    def queue_name(self):
        return self._consumer_queue_name


class RMQNonBlockingConnectionWrapper(RMQWrapperBase):
    """
    Async RMQConnection wrapper implemented in a Continuation-Passing style. Reuses a custom io_loop.
    Manages a single connection. Implements some event-based connection recovery.
    Not thread safe.
    """

    def __init__(self, opts, io_loop=None, **kwargs):
        super().__init__(opts, **kwargs)

        self._io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop()

        self._message_callback = None
        self._connection_future = None  # a future that is complete when connection is in terminal state (open or closed)

    @property
    def raw_connection(self):
        return self._connection

    @salt.ext.tornado.gen.coroutine
    def connect(self, **kwargs):
        """
        Do not reconnect if we are already connected
        :return:
        """
        if self._connection and self._connection.is_open:
            self.log.debug(
                "Already connected. Reusing existing connection [%s]", self._connection
            )
            return self._connection

        res = yield self._connect(**kwargs)
        return res

    @salt.ext.tornado.gen.coroutine
    def _connect(self, **kwargs):

        if not self._connection_future or self._connection_future.done():
            self._connection_future = salt.ext.tornado.concurrent.Future()
            self.log.info(
                "Connecting to amqp broker identified by URL [%s]. Additional args: %s",
                self._url,
                kwargs,
            )

        params = pika.URLParameters(self._url)
        params.client_properties = {
            "connection_name": "{}-{}".format(
                self.log.name, self._opts.get("id")
            )  # use the log name for connection name
        }

        if not self._connection or self._connection.is_closed:
            self._connection = SelectConnection(
                parameters=params,
                on_open_callback=self._on_connection_open,
                on_open_error_callback=self._on_connection_error,
                custom_ioloop=self._io_loop,
            )
        res = yield self._connection_future
        return res

    @salt.ext.tornado.gen.coroutine
    def close(self):
        if not self._closing:
            try:
                if not self._connection_future or self._connection_future.done():
                    self._connection_future = salt.ext.tornado.concurrent.Future()
                self._closing = True
                self._connection.close()
                self._connection = None

                res = yield self._connection_future
                return res
            except pika.exceptions.ConnectionClosedByBroker:
                pass
        else:
            self.log.debug("Already closing. Do nothing.")

    @salt.ext.tornado.gen.coroutine
    def _reconnect(self):
        """Called if the connection is lost. See the ```on_connection_closed``` method, for example.

        Note: RabbitMQ uses heartbeats to detect and close "dead" connections and to prevent network devices
        (firewalls etc.) from terminating "idle" connections.

        """
        if not self._closing:
            # Create a new connection
            self.log.info("Reconnecting (connection)...")
            # sleep for a bit so that if for some reason we get into a reconnect loop we won't kill the system
            yield salt.ext.tornado.gen.sleep(random.randint(5, 10))
            yield self.connect()

    def _on_connection_open(self, connection):
        """
        Invoked by pika when connection is opened successfully
        :param connection:
        :return:
        """
        self.log.debug("Connection opened: [%s]", connection)
        self._connection = connection
        connection.add_on_close_callback(self._on_connection_closed)
        self._mark_future_complete(self._connection_future)

    def _on_connection_error(self, connection, exception):
        """
        Invoked by pika on connection error
        :param connection:
        :param exception:
        :return:
        """
        self.log.debug("Connection error", exc_info=True)
        if isinstance(exception, AMQPConnectionError):
            # One possibility for this code path is for the case when salt is trying to connect to a broker that is not (yet) running.
            # Upon broker startup, when RMQ is not fully initialized yet, we end up in this state (due to a ProtocolError)
            # until RMQ broker has a chance to fully initialize and accept connections
            self._reconnect()
        else:
            self._mark_future_complete(self._connection_future, exception=exception)

    def _on_connection_closed(self, connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed. If it is unexpected, we will reconnect to
        RabbitMQ.

        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.

        """
        self.log.debug(
            "Connection closed for reason [%s]. Connection: [%s]", reason, connection
        )
        if self._connection and connection != self._connection:
            # we are already tracking a new connection, so we can safely forget about the connection that was closed
            # this can happen on reconnects() when connection open/closed events arrive for different connections,
            # e.g. previous connection was terminated and a reconnect() request created a new connection
            return

        self._mark_future_complete(self._connection_future)
        if isinstance(reason, ChannelClosedByBroker) or isinstance(
            reason, ConnectionClosedByBroker
        ):
            if reason.reply_code == 404:
                self.log.debug(
                    "Not recovering from 404. Make sure RMQ topology exists."
                )
                raise reason
            else:
                self._reconnect()

    def _mark_future_complete(self, future, exception=None):
        if future and not future.done():
            if exception:
                future.set_exception(exception)
            else:
                future.set_result(self._connection)


class RMQConnectionCache:
    """
    A static connection pool/cache that maintains a connection per processes/io_loop. Intended to simplify connection
    management for processes that require multiple connections or channels.
    Not thread safe.
    """

    _connection_map = {}

    @staticmethod
    def get_connection(opts, io_loop, **kwargs) -> RMQNonBlockingConnectionWrapper:
        """
        Retrieves cached connection. Use io_loop as key, which is acceptable for our master/minion/salt cli use cases
        and how master/minion/cli manage io_loops. Note that ideally, we should be instantiating one RMQ connection
        per process and one RMQ channel per thread.
        """
        conn = RMQConnectionCache._connection_map.get(io_loop)
        if not conn:
            conn = RMQNonBlockingConnectionWrapper(opts, io_loop=io_loop, **kwargs)
            RMQConnectionCache._connection_map[io_loop] = conn
        return conn


class RMQNonBlockingChannelWrapper(RMQWrapperBase):
    """
    Async RMQChannel wrapper implemented in a Continuation-Passing style.
    Supports management of multiple channels, but at most one channel per thread.
    Implements some event-based channel/connection recovery.
    Creates on-demand RMQ topology (queues, exchanges) and exposes basic operations such as publish/consume.
    Note: multiple rmq lightweight channels can be created for the same rmq connection (one per process).
    Reuses a custom io_loop. Not thread safe.
    """

    def __init__(self, opts, io_loop=None, **kwargs):

        super().__init__(opts, **kwargs)

        self._io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop()

        self._message_callback = None
        self._connection_future = None  # a future that is complete when connection is in terminal state (open or closed)
        self._rmq_connection_wrapper = RMQConnectionCache.get_connection(
            opts, io_loop=io_loop, **kwargs
        )
        self._channels = {}

        self._last_processed_stream_offset = None  # PR - fixme -- this is one per channel. Cache for the duration of the process

    def _get_channel(self):
        chan = self._channels.get(threading.get_ident())
        return chan

    @salt.ext.tornado.gen.coroutine
    def connect(self, message_callback=None):
        if not self._rmq_connection_wrapper:
            raise ValueError("_rmq_connection_wrapper must be set")

        if (
            self._rmq_connection_wrapper
            and self._rmq_connection_wrapper.raw_connection
            and self._rmq_connection_wrapper.raw_connection.is_open
            and self._get_channel()
            and self._get_channel().is_open
        ):
            self.log.debug("Already connected")
            return

        if message_callback:
            self._message_callback = message_callback

        res = yield self._connect()
        return res

    @salt.ext.tornado.gen.coroutine
    def _connect(self):
        if not self._connection_future or self._connection_future.done():
            self._connection_future = salt.ext.tornado.concurrent.Future()
        self.log.debug("Establishing rmq connection...")
        yield self._rmq_connection_wrapper.connect(
            caller=self
        )  # should be a no-op if already connected
        self.log.debug(
            "Opening a new channel in thread [%s] for connection [%s]",
            threading.get_ident(),
            self._rmq_connection_wrapper.raw_connection,
        )
        self._open_new_channel(self._rmq_connection_wrapper.raw_connection)

        res = yield self._connection_future
        return res

    @salt.ext.tornado.gen.coroutine
    def close(self):
        if not self._closing:
            if not self._connection_future or self._connection_future.done():
                self._connection_future = salt.ext.tornado.concurrent.Future()
            channel = self._get_channel()
            res = None
            if channel:
                self.log.debug("Closing channel [%s]", channel)
                channel.close()
                res = yield self._connection_future
            else:
                self.log.debug(
                    "Closing - no channel for thread [%s]", threading.get_ident()
                )
                self._mark_future_complete(self._connection_future)
            return res

    @salt.ext.tornado.gen.coroutine
    def _reconnect(self):
        """Called if the channel is lost. See the ```on_channel_closed``` method, for example."""
        if not self._closing:
            # Create a new connection
            self.log.info("Reconnecting (channel)...")
            # sleep for a bit so that if for some reason we get into a reconnect loop we won't kill the system
            yield salt.ext.tornado.gen.sleep(random.randint(5, 10))
            yield self.connect()

    def _open_new_channel(self, connection, create_topology_ondemand=True):
        if not connection:
            raise ValueError("connection must exist before opening a new channel")

        self._channels[threading.get_ident()] = connection.channel(
            on_open_callback=functools.partial(
                self._on_channel_open, create_topology_ondemand=create_topology_ondemand
            )
        )
        self._get_channel().add_on_close_callback(self._on_channel_closed)

    def _on_channel_closed(self, channel, reason):
        self.log.debug(
            "Channel [%s] closed for reason [%s] in thread [%s]",
            channel.channel_number,
            reason,
            threading.get_ident(),
        )

        tracked_channel_for_thread = self._channels.get(threading.get_ident())
        if tracked_channel_for_thread and tracked_channel_for_thread != channel:
            # We are already tracking a new channel, so we can safely forget about the channel that was closed.
            # This can happen on reconnects() when channel open/closed events arrive for different channels,
            # e.g. previous channel was terminated and a reconnect() request already created a new channel
            return

        self._channels.pop(threading.get_ident(), None)
        self._mark_future_complete(self._connection_future)

        if isinstance(reason, ChannelClosedByBroker) or isinstance(
            reason, ConnectionClosedByBroker
        ):
            if reason.reply_code == 404:
                self.log.warning(
                    "Not recovering from 404. Make sure RMQ topology exists."
                )
                raise reason
            else:
                self._reconnect()
        elif isinstance(reason, StreamLostError) or isinstance(
            reason, pika.exceptions.AMQPHeartbeatTimeout
        ):
            self._reconnect()
        else:
            self.log.debug(
                "Not attempting to recover. Channel likely closed explicitly for legitimate reasons."
            )

    def _on_channel_open(self, channel, create_topology_ondemand=True):
        """
        Invoked by pika when channel is opened successfully
        :param channel:
        :return:
        """
        self.log.debug(
            "Channel number [%s] opened. Enabling delivery confirmation.",
            channel.channel_number,
        )

        # see https://www.rabbitmq.com/confirms.html
        channel.confirm_delivery(self._ack_nack_callback)
        channel.basic_qos(prefetch_count=1000)  # PR - FIXME: need a callback here
        self._channels[threading.get_ident()] = channel

        if create_topology_ondemand:
            channel.exchange_declare(
                exchange=self._publisher_exchange_name,
                exchange_type=ExchangeType.fanout,
                durable=True,
                auto_delete=True,  # exchange is deleted when last queue is unbound from it (if at least one queue was ever bound)
                arguments=self._publisher_exchange_declare_arguments,
                callback=self._on_publisher_exchange_declared,
            )
        else:
            self.log.debug("Skipping amqp topology creation.")
            if self._message_callback:
                self.start_consuming(self._message_callback, self._connection_future)
            else:
                self._mark_future_complete(self._connection_future)

    def _ack_nack_callback(self, frame: pika.frame.Method):
        self.log.debug("Acked or Nacked: %s", frame)

    def _mark_future_complete(self, future, exception=None):
        if future and not future.done():
            if exception:
                future.set_exception(exception)
            else:
                future.set_result(self._get_channel())

    def _on_publisher_exchange_declared(self, method):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        """
        self.log.debug("Publisher exchange declared: %s", self._publisher_exchange_name)
        if not self._get_channel():
            raise ValueError("_channel must be set")

        if self._consumer_exchange_name:
            self._get_channel().exchange_declare(
                exchange=self._consumer_exchange_name,
                exchange_type=ExchangeType.fanout,
                durable=True,
                auto_delete=True,  # exchange is deleted when last queue is unbound from it (if at least one queue was ever bound)
                arguments=self._consumer_exchange_declare_arguments,
                callback=self._on_consumer_exchange_declared,
            )
        else:
            self.log.debug(
                "No consumer exchange configured. Skipping consumer exchange declaration"
            )
            self._mark_future_complete(self._connection_future)

    def _on_consumer_exchange_declared(self, method):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        """
        self.log.debug("Consumer exchange declared: %s", self._consumer_exchange_name)
        if not self._get_channel():
            raise ValueError("_channel must be set")

        if self.queue_name:
            self._get_channel().queue_declare(
                queue=self._consumer_queue_name,
                durable=True,
                arguments=self._consumer_queue_declare_arguments,
                callback=self._on_consumer_queue_declared,
            )
        else:
            log.debug(
                "No consumer queue configured. Skipping basic_consume on queue %s",
                self.queue_name,
            )
            self._mark_future_complete(self._connection_future)

    def _on_consumer_queue_declared(self, method):
        """
        Invoked by pika when queue is declared successfully
        :param method:
        :return:
        """
        self.log.debug("Consumer queue declared: %s", method.method.queue)
        if not self._get_channel():
            raise ValueError("_channel must be set")

        self._get_channel().queue_bind(
            method.method.queue,
            self._consumer_exchange_name,
            routing_key=method.method.queue,
            callback=self._on_consumer_queue_bound,
        )

    def _on_consumer_queue_bound(self, method):
        """
        Invoked by pika when queue bound successfully. Set up consumer message callback as well.
        :param method:
        :return:
        """

        self.log.debug("Queue bound [%s]", self.queue_name)
        if self._message_callback:
            self.start_consuming(self._message_callback, self._connection_future)
            log.debug(
                "Started basic_consume on queue [%s]",
                self.queue_name,
            )
        else:
            log.debug(
                "No message callback configured. Skipping basic_consume on queue [%s]",
                self.queue_name,
            )
        self._mark_future_complete(self._connection_future)

    @salt.ext.tornado.gen.coroutine
    def start_consuming(
        self, callback: Callable[[Any, BasicProperties], None], future=None
    ):
        """
        Set up a consumer on configured queue with provided ```callback``` and return a future that is
        complete when consumer is set up
        :param future:
        :param callback: callback to call when message is received on queue
        :return: a future that is complete when consumer is set up
        """

        self._message_callback = callback
        future = future or salt.ext.tornado.concurrent.Future()

        def _callback_consumer_registered(method):
            if not future.done():
                future.set_result(self._get_channel())

        def _on_message_callback_wrapper(channel, method, properties, payload):
            self.log.debug(
                "MESSAGE - Received message on queue [%s]: %s. Payload properties: %s",
                self.queue_name,
                salt.payload.loads(payload),
                properties,
            )

            if callback:
                callback(payload, message_properties=properties)
                self.log.debug(
                    "Processed callback for message on queue [%s]", self.queue_name
                )
            if not self._message_auto_ack:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                if properties.headers and "x-stream-offset" in properties.headers:
                    self._last_processed_stream_offset = properties.headers[
                        "x-stream-offset"
                    ]
                self.log.debug(
                    "Acknowledged message on queue [%s] with delivery tag [%s]",
                    self.queue_name,
                    method.delivery_tag,
                )

        if not self._get_channel():
            raise ValueError("_channel must be set")

        arguments = {}
        if self._last_processed_stream_offset:
            arguments["x-stream-offset"] = (
                self._last_processed_stream_offset + 1
            )  # do not re-process the same message
        self._get_channel().basic_consume(
            self.queue_name,
            arguments=arguments,
            callback=_callback_consumer_registered,
            on_message_callback=_on_message_callback_wrapper,
            auto_ack=self._message_auto_ack,  # stream queues do not support auto-ack=True
        )

        self.log.debug(
            "Starting basic_consume on queue [%s] with arguments [%s]",
            self.queue_name,
            arguments,
        )

        yield future

    @salt.ext.tornado.gen.coroutine
    def consume_reply(self, callback, reply_queue_name=None):
        """
        Registers RPC reply callback on the designated reply queue and return a future that is complete when
        reply consumer is registered
        :param callback:
        :param reply_queue_name:
        :return:
        """
        future = salt.ext.tornado.concurrent.Future()

        def _callback_consumer_registered(method):
            future.set_result(method.method.consumer_tag)

        def _on_message_callback(channel, method, properties, body):
            self.log.debug(
                "Received reply on queue [%s]: %s. Reply payload properties: %s",
                reply_queue_name,
                body,
                properties,
            )
            callback(body, properties.correlation_id)
            self.log.debug(
                "Processed callback for reply on queue [%s]", reply_queue_name
            )

            if not self._message_auto_ack:
                # channel.basic_ack(delivery_tag=method.delivery_tag) # reply queues do not support acks
                self.log.debug(
                    "Acknowledged reply on queue [%s] with delivery tag [%s]",
                    reply_queue_name,
                    method.delivery_tag,
                )

        self.log.debug("Starting basic_consume reply on queue [%s]", reply_queue_name)

        if not self._get_channel():
            raise ValueError("_channel must be set")

        consumer_tag = "rmq_direct_reply_consumer"  # an arbitrarily chosen consumer tag
        try:
            consumer_tag = self._get_channel().basic_consume(
                consumer_tag=consumer_tag,
                queue=reply_queue_name,
                on_message_callback=_on_message_callback,
                auto_ack=True,  # reply-to queues only support auto_ack=True
                callback=_callback_consumer_registered,
            )
        except pika.exceptions.DuplicateConsumerTag:
            # this could happen when retrying to send the request multiple times and the retry loop will end up here
            # see ```timeout_message``` for reference
            self.log.debug(
                "Ignoring attempt to set up a second consumer with consumer tag [%s]",
                consumer_tag,
            )
            future.set_result(consumer_tag)

        self.log.debug(
            "Started basic_consume reply on queue [%s] with consumer tag [%s]",
            reply_queue_name,
            consumer_tag,
        )

        yield future

    @salt.ext.tornado.gen.coroutine
    def publish(
        self,
        payload,
        exchange_name=None,
        routing_key: str = "",  # must be a string
        reply_queue_name=None,
        correlation_id=None,
    ):
        """
        Publishes ``payload`` to the specified exchange ``exchange_name`` with the routing key ``routing_key``
        (via direct exchange or via fanout/broadcast),
        passes along optional name of the reply queue in message metadata. Non-blocking.
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).

        :param correlation_id: optional message correlation id (used in RPC request/response pattern)
        :param payload: message body
        :param exchange_name: exchange name
        :param routing_key: and exchange-specific routing key
        :param reply_queue_name: optional name of the reply queue
        :return:
        """
        properties = pika.BasicProperties()
        properties.reply_to = reply_queue_name if reply_queue_name else None
        properties.app_id = str(threading.get_ident())  # use this for tracing
        # enable persistent message delivery
        # see https://www.rabbitmq.com/confirms.html#publisher-confirms and
        # https://kousiknath.medium.com/dabbling-around-rabbit-mq-persistence-durability-message-routing-f4efc696098c
        properties.delivery_mode = PERSISTENT_DELIVERY_MODE
        # This property helps relate request/response when using amq.rabbitmq.reply-to pattern
        properties.correlation_id = correlation_id or str(hash(payload))

        # Note: exchange name that is an empty string ("") has meaning -- it is the name of the "direct exchange"
        exchange_name = (
            exchange_name
            if exchange_name is not None
            else self._publisher_exchange_name
        )
        self.log.debug(
            "Sending payload to exchange [%s] with routing key [%s]: %s. Payload properties: %s",
            exchange_name,
            routing_key,
            salt.payload.loads(payload),
            properties,
        )

        try:
            self._get_channel().basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=payload,
                properties=properties,
                mandatory=True,
            )
            self.log.debug(
                "MESSAGE - Sent payload to exchange [%s] with routing key [%s]: [%s]. Payload properties: %s",
                exchange_name,
                routing_key,
                salt.payload.loads(payload),
                properties,
            )
        except:
            self.log.exception(
                "Exception publishing to exchange [%s] with routing_key [%s]",
                exchange_name,
                routing_key,
            )
            raise

    @salt.ext.tornado.gen.coroutine
    def publish_reply(self, payload, **optional_transport_args):
        """
        Publishes reply ``payload`` routing it to the reply queue. Non-blocking.
        :param payload: message body
        :param optional_transport_args: payload properties/metadata
        :return:
        """

        message_properties = None
        if optional_transport_args:
            message_properties = optional_transport_args.get("message_properties", None)
            if not isinstance(message_properties, BasicProperties):
                raise TypeError(
                    "message_properties must be of type {!r} instead of {!r}".format(
                        type(BasicProperties), type(message_properties)
                    )
                )

        if message_properties:
            routing_key = message_properties.reply_to

        if not routing_key:
            raise ValueError("properties.reply_to must be set")

        self.log.debug(
            "MESSAGE - Sending reply payload to direct exchange with routing key [%s]: %s. Payload properties: %s",
            routing_key,
            salt.payload.loads(payload),  # PR - AES - FIXME
            message_properties,
        )

        # publish reply on a queue that will be deleted after consumer cancels or disconnects
        # do not broadcast replies
        yield self.publish(
            payload,
            exchange_name="",  # use the special default/direct exchange for replies with the name that is empty string
            routing_key=routing_key,
            correlation_id=message_properties.correlation_id,
        )


class RabbitMQRequestClient(salt.transport.base.RequestClient):
    ttype = "rabbitmq"

    def __init__(self, opts, io_loop, **kwargs):
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.message_client = AsyncReqMessageClient(
            self.opts,
            # self.master_uri,
            io_loop=io_loop,
        )

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        """
        TODO: enable this for all transports for consistency
        :return:
        """
        yield self.message_client.connect()

    @salt.ext.tornado.gen.coroutine
    def send(self, load, tries=3, timeout=60):
        ret = yield self.message_client.send(load, timeout, tries)
        raise salt.ext.tornado.gen.Return(ret)

    def close(self):
        self.message_client.close()


class RabbitMQPubClient(salt.transport.base.PublishClient):
    """
    A transport channel backed by RabbitMQ for a Salt Publisher to use to
    publish commands to connected minions.
    Typically, this class is instantiated by a minion
    """

    def __init__(self, opts, io_loop, **kwargs):
        super().__init__(opts, io_loop, **kwargs)
        self.log = logging.getLogger(self.__class__.__name__)
        self.opts = opts
        self.ttype = "rabbitmq"
        self.io_loop = io_loop
        if not self.io_loop:
            raise ValueError("self.io_loop must be set")

        self._closing = False

        self.hexid = hashlib.sha1(
            salt.utils.stringutils.to_bytes(self.opts["id"])
        ).hexdigest()
        self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)
        self.serial = salt.payload.Serial(self.opts)
        self._rmq_non_blocking_channel_wrapper = RMQNonBlockingChannelWrapper(
            self.opts,
            io_loop=self.io_loop,
            log=self.log,
        )

    def close(self):
        if self._closing is True:
            return
        self._closing = True
        self._rmq_non_blocking_channel_wrapper.close()

    # pylint: disable=no-dunder-del
    def __del__(self):
        self.close()

    # pylint: enable=no-dunder-del
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # TODO: this is the time to see if we are connected, maybe use the req channel to guess?
    @salt.ext.tornado.gen.coroutine
    def connect(
        self, publish_port=None, connect_callback=None, disconnect_callback=None
    ):
        """
        Connects minion to master.
        :return:
        """
        # connect() deserves its own method wrapped in a coroutine called by the upstream layer when appropriate
        yield self._rmq_non_blocking_channel_wrapper.connect()

        if not self.auth.authenticated:
            yield self.auth.authenticate()

        self.log.info(
            "Minion already authenticated with master. Nothing else to do for broker-based transport."
        )

    @salt.ext.tornado.gen.coroutine
    def _decode_messages(self, messages):
        """
        Take the rmq messages, decrypt/decode them into a payload

        :param list messages: A list of messages to be decoded
        """
        messages = [
            messages
        ]  # TODO: FIXME - figure out why this does not match zeromq payload packing
        messages_len = len(messages)
        # if it was one message, then its old style
        if messages_len == 1:
            if isinstance(messages[0], dict):
                return messages[0]
            else:
                payload = salt.payload.loads(messages[0])
                payload = (
                    salt.payload.loads(payload["payload"])
                    if "payload" in payload
                    else payload
                )
        # 2 includes a header which says who should do it
        elif messages_len == 2:
            message_target = salt.utils.stringutils.to_str(messages[0])
            if (
                self.opts.get("__role") != "syndic"
                and message_target not in ("broadcast", self.hexid)
            ) or (
                self.opts.get("__role") == "syndic"
                and message_target not in ("broadcast", "syndic")
            ):
                self.log.info(
                    "Publish received not for this minion: %s", message_target
                )
                raise salt.ext.tornado.gen.Return(None)
            payload = salt.payload.loads(messages[1])
        else:
            raise Exception(
                (
                    "Invalid number of messages ({}) in rabbitmq pub"
                    "message from master"
                ).format(len(messages_len))
            )
        # Yield control back to the caller. When the payload has been decoded, assign
        # the decoded payload to 'ret' and resume operation
        # ret = yield self._decode_payload(payload)
        raise salt.ext.tornado.gen.Return(payload)

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        if callback:

            @salt.ext.tornado.gen.coroutine
            def wrap_callback(messages, **kwargs):
                payload = yield self._decode_messages(messages)
                if payload is not None:
                    callback(payload)

            self._rmq_non_blocking_channel_wrapper.start_consuming(wrap_callback)


class RabbitMQReqServer(salt.transport.base.DaemonizedRequestServer):
    """
    Encapsulate synchronous operations for a request channel
    Typically, this class is instantiated by a master
    """

    def pre_fork(self, process_manager):
        pass

    def __init__(self, opts):
        super().__init__(opts)
        self.log = logging.getLogger(self.__class__.__name__)
        self.opts = opts
        self._closing = False

    def close(self):
        """
        Cleanly shutdown
        """
        if self._closing:
            return

    def post_fork(self, message_handler, io_loop):
        """
        After forking we need to set up handlers to listen to the
        router

        :param func message_handler: A function to called to handle incoming payloads as
                                     they are picked up off the wire
        :param IOLoop io_loop: An instance of a Tornado IOLoop, to handle event scheduling
        """

        if not io_loop:
            raise ValueError("io_loop must be set")

        self.payload_handler = message_handler
        self._rmq_nonblocking_connection_wrapper = RMQNonBlockingChannelWrapper(
            self.opts, io_loop=io_loop, log=self.log
        )

        # PR - FIXME. Consider moving the connect() call into a coroutine to that we can yield it
        self._rmq_nonblocking_connection_wrapper.connect(
            message_callback=self.handle_message
        )

    @salt.ext.tornado.gen.coroutine
    def handle_message(
        self, payload, **optional_transport_args
    ):  # message_properties: pika.BasicProperties
        payload = self.decode_payload(payload)
        reply = yield self.payload_handler(payload, **optional_transport_args)
        yield self._rmq_nonblocking_connection_wrapper.publish_reply(
            self.encode_payload(reply), **optional_transport_args
        )

    def encode_payload(self, payload):
        return salt.payload.dumps(payload)

    def decode_payload(self, payload):
        payload = salt.payload.loads(payload)
        return payload

    def __setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_signals)
        signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):
        msg = "{} received a ".format(self.__class__.__name__)
        if signum == signal.SIGINT:
            msg += "SIGINT"
        elif signum == signal.SIGTERM:
            msg += "SIGTERM"
        msg += ". Exiting"
        log.info(msg)
        self.close()
        sys.exit(salt.defaults.exitcodes.EX_OK)


class RabbitMQPublishServer(salt.transport.base.DaemonizedPublishServer):
    """
    Encapsulate synchronous operations for a publisher channel.
    Typically, this class is instantiated by a master
    """

    def __init__(self, opts):
        super().__init__()
        self.log = logging.getLogger(self.__class__.__name__)
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?

        self._rmq_non_blocking_channel_wrapper = None
        self.pub_sock = None

    def pre_fork(self, process_manager, kwargs=None):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        """
        process_manager.add_process(
            self.publish_daemon, args=(self.publish_payload,), kwargs=kwargs
        )

    def post_fork(self, message_handler, io_loop):
        pass

    def publish_daemon(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
        **kwargs
    ):
        """
        Bind to the interface specified in the configuration file
        """
        log_queue = kwargs.get("log_queue")
        if log_queue is not None:
            salt.log.setup.set_multiprocessing_logging_queue(log_queue)
        log_queue_level = kwargs.get("log_queue_level")
        if log_queue_level is not None:
            salt.log.setup.set_multiprocessing_logging_level(log_queue_level)
        io_loop = salt.ext.tornado.ioloop.IOLoop()

        # Spin up the publisher
        self._rmq_non_blocking_channel_wrapper = RMQNonBlockingChannelWrapper(
            self.opts, log=self.log, io_loop=io_loop
        )

        self._rmq_non_blocking_channel_wrapper.connect()

        # Set up Salt IPC server
        if self.opts.get("ipc_mode", "") == "tcp":
            # typically used on Windows
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")

        pull_sock = salt.transport.ipc.IPCMessageServer(
            pull_uri,
            io_loop=io_loop,
            payload_handler=publish_payload,
        )

        # Securely create socket
        log.info("Starting the Salt Puller on %s", pull_uri)
        with salt.utils.files.set_umask(0o177):
            pull_sock.start()

        # run forever
        try:
            io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            pull_sock.close()

    @salt.ext.tornado.gen.coroutine
    def publish_payload(self, payload, *args):
        payload_serialized = salt.payload.dumps(payload)

        self.log.debug(
            "Sending payload to rabbitmq broker. jid=%s size=%d",
            payload.get("jid", None),
            len(payload_serialized),
        )

        ret = yield self._rmq_non_blocking_channel_wrapper.connect()
        self._rmq_non_blocking_channel_wrapper.publish(
            payload_serialized,
        )
        self.log.debug("Sent payload to rabbitmq broker.")

        raise salt.ext.tornado.gen.Return(ret)

    def publish(self, payload, **optional_transport_args):
        """
        Publish "load" to minions
        """
        self.log.debug("Sending payload to minions via publish daemon via IPC")
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")
        if not self.pub_sock:
            self.pub_sock = salt.utils.asynchronous.SyncWrapper(
                salt.transport.ipc.IPCMessageClient,
                (pull_uri,),
                loop_kwarg="io_loop",
            )
            self.pub_sock.connect()
        self.pub_sock.send(payload)

    @property
    def topic_support(self):
        # we may support this eventually
        return False

    def close(self):
        self._rmq_non_blocking_channel_wrapper.close()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()


# TODO: unit tests!
class AsyncReqMessageClient:
    """
    This class gives a future-based
    interface to sending and receiving messages. This works around the primary
    limitation of serialized send/recv on the underlying socket by queueing the
    message sends in this class. In the future if we decide to attempt to multiplex
    we can manage a pool of REQ/REP sockets-- but for now we'll just do them in serial

    """

    def __init__(self, opts, io_loop=None):
        """
        Create an asynchronous message client

        :param dict opts: The salt opts dictionary
        :param IOLoop io_loop: A Tornado IOLoop event scheduler [tornado.ioloop.IOLoop]
        """

        self.log = logging.getLogger(self.__class__.__name__)
        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop()
        self.opts = opts

        if (
            self.opts.get("__role") == "master"
        ):  # TODO: fix this so that this check is done upstream
            # local client uses master config file but acts as a client to the master
            # swap the exchange to that we can reach the master
            self._rmq_non_blocking_channel_wrapper = RMQNonBlockingChannelWrapper(
                self.opts,
                io_loop=self.io_loop,
                log=self.log,
                transport_rabbitmq_publisher_exchange_name=self.opts[
                    "transport_rabbitmq_consumer_exchange_name"
                ],
                transport_rabbitmq_consumer_exchange_name=None,
                transport_rabbitmq_consumer_queue_name=None,
            )
        else:
            self._rmq_non_blocking_channel_wrapper = RMQNonBlockingChannelWrapper(
                self.opts, io_loop=self.io_loop, log=self.log
            )

        self.serial = salt.payload.Serial(self.opts)

        self.send_queue = []
        # mapping of str(hash(message)) -> future
        self.send_future_map = {}

        self.send_timeout_map = {}  # message -> timeout
        self._closing = False

    # TODO: timeout all in-flight sessions, or error
    def close(self):
        try:
            if self._closing:
                return
            self._rmq_non_blocking_channel_wrapper.close()
        except AttributeError:
            # We must have been called from __del__
            # The python interpreter has nuked most attributes already
            return
        else:
            self._closing = True

    # pylint: disable=no-dunder-del
    def __del__(self):
        self.close()

    # pylint: enable=no-dunder-del

    def timeout_message(self, message):
        """
        Handle a message timeout by removing it from the sending queue
        and informing the caller

        :raises: SaltReqTimeoutError
        """
        future = self.send_future_map.pop(str(hash(message)), None)
        # In a race condition the message might have been sent by the time
        # we're timing it out. Make sure the future is not None
        if future is not None:
            if future.attempts < future.tries:
                future.attempts += 1
                log.debug(
                    "SaltReqTimeoutError, retrying. (%s/%s)",
                    future.attempts,
                    future.tries,
                )
                self.send(
                    message,
                    timeout=future.timeout,
                    tries=future.tries,
                    reply_future=future,
                )

            else:
                future.set_exception(SaltReqTimeoutError("Message timed out"))

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        yield self._rmq_non_blocking_channel_wrapper.connect()

    @salt.ext.tornado.gen.coroutine
    def send(
        self,
        message,
        timeout=None,
        tries=3,
        reply_future=None,
        callback=None,
    ):
        """
        Return a future which will be completed when the message has a response
        """

        yield self._rmq_non_blocking_channel_wrapper.connect()

        if reply_future is None:
            reply_future = salt.ext.tornado.concurrent.Future()
            reply_future.tries = tries
            reply_future.attempts = 0
            reply_future.timeout = timeout
            # if a future wasn't passed in, we need to serialize the message
            message = salt.payload.dumps(message)

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            reply_future.add_done_callback(handle_future)

        # Add this future to the mapping; use message hash as key
        correlation_id = str(hash(message))
        self.send_future_map[correlation_id] = reply_future

        if self.opts.get("detect_mode") is True:
            # This code path is largely untested in the product
            timeout = 5

        if timeout is not None:
            send_timeout = self.io_loop.call_later(
                timeout, self.timeout_message, message
            )

        def mark_reply_future(reply_msg, corr_id):
            # reference the mutable map in this closure so that we complete the correct future,
            # as this callback can be called multiple times for multiple invocations of the outer send() function
            future = self.send_future_map.get(corr_id)
            if future and not future.done():
                # future may be None if there is a race condition between ```mark_reply_future`` and ```timeout_message```
                data = salt.payload.loads(reply_msg)
                future.set_result(data)
                self.send_future_map.pop(corr_id)

        # send message and consume reply; callback must be configured first when using amq.rabbitmq.reply-to pattern
        # See https://www.rabbitmq.com/direct-reply-to.html
        consumer_tag = yield self._rmq_non_blocking_channel_wrapper.consume_reply(
            mark_reply_future, reply_queue_name="amq.rabbitmq.reply-to"
        )

        yield self._rmq_non_blocking_channel_wrapper.publish(
            message,
            # Use a special reserved direct-reply queue. See https://www.rabbitmq.com/direct-reply-to.html
            reply_queue_name="amq.rabbitmq.reply-to",
        )

        recv = yield reply_future
        raise salt.ext.tornado.gen.Return(recv)
