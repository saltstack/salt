"""
Rabbitmq transport classes
This is a copy/modify of zeromq implementation with zeromq-specific bits removed.
TODO: refactor transport implementations so that tcp, zeromq, rabbitmq share common code
"""
import copy
import errno
import hashlib
import logging
import os
import signal
import sys
import threading
import weakref
from typing import Any, Callable
from uuid import uuid4

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
import salt.transport.mixins.auth
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
from pika.exchange_type import ExchangeType
from salt.exceptions import SaltException, SaltReqTimeoutError
from salt.ext import tornado

# pylint: enable=3rd-party-module-not-gated


try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        from Crypto.Cipher import PKCS1_OAEP  # nosec

log = logging.getLogger(__name__)


def _get_master_uri(master_ip, master_port):
    """
    TODO: this method is a zeromq remnant and likely should be removed
    """
    from salt.utils.zeromq import ip_bracket

    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip=ip_bracket(master_ip), master_port=master_port
    )

    return master_uri


class RMQConnectionWrapperBase:
    def __init__(self, opts, queue_name=None):
        self._opts = opts

        # rmq broker address
        self._host = (
            self._opts["transport_rabbitmq_address"]
            if "transport_rabbitmq_address" in self._opts
            else "localhost"
        )
        if not self._host:
            raise ValueError("Host must be set")

        # rmq broker credentials (TODO: support other types of auth. eventually)
        creds_key = "transport_rabbitmq_auth"
        if creds_key not in self._opts:
            raise KeyError("Missing key {!r}".format(creds_key))
        creds = self._opts[creds_key]

        if "username" not in creds and "password" not in creds:
            raise KeyError("username or password must be set")
        self._creds = pika.PlainCredentials(creds["username"], creds["password"])

        # TODO: think about abetter way to generate queue names
        # each possibly running on different machine
        master_port = (
            self._opts["master_port"]
            if "master_port" in self._opts
            else self._opts["ret_port"]
        )
        if not master_port:
            raise KeyError("master_port must be set")

        self._queue_name = (
            queue_name
            if queue_name
            else "master_consumer_{}_{}".format(self._host, master_port)
        )

        # set up exchange for message broadcast
        self._fanout_exchange_name = self.queue_name
        self._connection = None
        self._channel = None
        self._closing = False

    @property
    def queue_name(self):
        return self._queue_name

    def close(self):
        if not self._closing:
            try:
                if self._channel and self._channel.is_open:
                    self._channel.close()
            except pika.exceptions.ChannelWrongStateError:
                pass

            try:
                if self._connection and self._connection.is_open:
                    self._connection.close()
            except pika.exceptions.ConnectionClosedByBroker:
                pass
            self._closing = True
        else:
            log.debug("Already closing. Do nothing")


class RMQBlockingConnectionWrapper(RMQConnectionWrapperBase):

    """
    RMQConnection wrapper implemented that wraps a BlockingConnection.
    Declares and binds a queue to a fanout exchange for publishing messages.
    Caches connection and channel for reuse.
    Not thread safe.
    """

    def __init__(self, opts, queue_name=None):
        super().__init__(opts, queue_name=queue_name)

        self._connect(self._host, self._creds)

        # set up exchange for message broadcast
        self._fanout_exchange_name = self.queue_name
        self._channel.exchange_declare(
            exchange=self._fanout_exchange_name, exchange_type=ExchangeType.fanout
        )

    def _connect(self, host, creds):
        self._connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, credentials=creds)
        )
        self._channel = self._connection.channel()

    def publish(
        self,
        payload,
        queue_name=None,
        reply_queue_name=None,
        correlation_id=None,
        auto_delete_queue=False,
        broadcast=True,
    ):
        """
        Publishes ``payload`` to the specified ``queue_name`` (via direct exchange or via fanout/broadcast),
        passes along optional name of the reply queue in message metadata. Non-blocking.
        Recover from connection failure (with a retry).
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).

        :param correlation_id: correlation_id (used for the RPC pattern in conjunction with reply queue)
        :param payload: message body
        :param queue_name: queue name
        :param reply_queue_name: optional name of the reply queue
        :param auto_delete_queue: set the type of queue to "auto_delete"
        (it will be deleted when the last consumer disappears)
        :param broadcast: whether to broadcast via fanout exchange
        :return:
        """
        while (
            not self._closing
        ):  # TODO: limit number of retries and use some retry decorator
            try:
                self._publish(
                    payload,
                    queue_name=queue_name,
                    reply_queue_name=reply_queue_name,
                    correlation_id=correlation_id,
                    auto_delete_queue=auto_delete_queue,
                    broadcast=broadcast,
                )
                break

            except pika.exceptions.ConnectionClosedByBroker:
                # Connection may have been terminated cleanly by the broker, e.g.
                # as a result of "rabbitmqtl" cli call. Attempt to reconnect anyway.
                log.exception("Connection exception when publishing.")
                log.info("Attempting to re-establish RMQ connection.")
                self._connect(self._host, self._creds)
            except pika.exceptions.ChannelWrongStateError:
                # Note: RabbitMQ uses heartbeats to detect and close "dead" connections and to prevent network devices
                # (firewalls etc.) from terminating "idle" connections.
                # From version 3.5.5 on, the default timeout is set to 60 seconds
                log.exception("Channel exception when publishing.")
                log.info("Attempting to re-establish RMQ connection.")
                self._connect(self._host, self._creds)

    def _publish(
        self,
        payload,
        queue_name=None,
        reply_queue_name=None,
        correlation_id=None,
        auto_delete_queue=False,
        broadcast=True,
    ):
        """
        Publishes ``payload`` to the specified ``queue_name`` (via direct exchange or via fanout/broadcast),
        passes along optional name of the reply queue in message metadata. Non-blocking.
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).

        :param correlation_id: correlation_id (used for the RPC pattern in conjunction with reply queue)
        :param payload: message body
        :param queue_name: queue name
        :param reply_queue_name: optional name of the reply queue
        :param auto_delete_queue: set the type of queue to "auto_delete"
        (it will be deleted when the last consumer disappears)
        :param broadcast: whether to broadcast via fanout exchange
        :return:
        """

        publish_queue_name = queue_name if queue_name else self.queue_name

        # See https://www.rabbitmq.com/tutorials/amqp-concepts.html
        exchange = self._fanout_exchange_name if broadcast else ""

        # For the IPC pattern, set up the "reply-to" header and "correlation_id"
        properties = pika.BasicProperties()
        properties.reply_to = reply_queue_name if reply_queue_name else None
        properties.correlation_id = correlation_id if correlation_id else uuid4().hex
        properties.app_id = str(threading.get_ident())  # use this for tracing

        log.info(
            "Sending payload to queue [%s] via exchange [%s]: %s. Payload properties: %s",
            publish_queue_name,
            exchange,
            payload,
            properties,
        )

        try:
            # TODO: consider different queue types (durable, quorum, etc.)
            self._channel.queue_declare(
                publish_queue_name, auto_delete=auto_delete_queue
            )
            log.info(
                "declared queue: %s with auto_delete=%s",
                publish_queue_name,
                auto_delete_queue,
            )

            if broadcast:
                log.info(
                    "Binding queue [%s] to exchange [%s]", publish_queue_name, exchange
                )
                self._channel.queue_bind(
                    publish_queue_name, exchange, routing_key=publish_queue_name
                )
            self._channel.basic_publish(
                exchange=exchange,
                routing_key=publish_queue_name,
                body=payload,
                properties=properties,
            )  # add reply queue to the properties
            log.info(
                "Sent payload to queue [%s] via exchange [%s]: [%s]",
                publish_queue_name,
                exchange,
                payload,
            )
        except:
            log.exception(
                "Error publishing to queue [%s] via exchange [%s]",
                publish_queue_name,
                exchange,
            )
            raise

    def publish_reply(self, payload, properties: BasicProperties):
        """
        Publishes reply ``payload`` to the reply queue. Non-blocking.
        :param payload: message body
        :param properties: payload properties/metadata
        :return:
        """
        reply_queue_name = properties.reply_to

        if not reply_queue_name:
            raise ValueError("properties.reply_to must be set")

        log.info(
            "Sending reply payload on queue [%s]: %s. Payload properties: %s",
            reply_queue_name,
            payload,
            properties,
        )

        # publish reply on a queue that will be deleted after consumer cancels or disconnects
        # do not broadcast replies
        # TODO: look into queue types (durable, quorum, etc.)
        self.publish(
            payload,
            queue_name=reply_queue_name,
            auto_delete_queue=True,
            broadcast=False,
        )

    def consume(self, queue_name=None, timeout=60):
        """
        A non-blocking consume takes the next message off the queue.
        :param queue_name:
        :param timeout:
        :return:
        """
        log.info("Consuming payload on queue [%s]", queue_name)

        queue_name = queue_name or self.queue_name
        self._channel.queue_declare(queue_name)
        log.info("declared queue: %s", queue_name)
        (method, properties, body) = next(
            self._channel.consume(
                queue=queue_name, inactivity_timeout=timeout, auto_ack=True
            )
        )
        return body

    def consume_reply(self, callback, reply_queue_name=None, timeout=60):
        """
        Blocks until reply is received on the reply queue and processes it in a ``callback``
        :param callback:
        :param reply_queue_name:
        :param timeout
        :return:
        """
        self._channel.queue_declare(queue=reply_queue_name, auto_delete=True)
        log.info("declared queue: %s with auto_delete=True", reply_queue_name)

        def _callback(ch, method, properties, body):
            log.info(
                "Received reply on queue [%s]: %s. Payload properties: %s",
                reply_queue_name,
                body,
                properties,
            )
            callback(body)
            log.info("Processed callback for reply on queue [%s]", reply_queue_name)

            # Stop consuming so that auto_delete queue will be deleted
            # TODO: explicitly acknowledge response after processing callback instead of relying on "auto_ack"
            self._channel.stop_consuming()
            log.info("Done consuming reply on queue [%s]", reply_queue_name)

        # blocking call with a callback
        log.info("Starting consuming reply on queue [%s]", reply_queue_name)

        # TODO: reconsider auto_ack
        consumer_tag = self._channel.basic_consume(
            queue=reply_queue_name, on_message_callback=_callback, auto_ack=True
        )
        self._channel.start_consuming()  # a blocking call

    def blocking_consume(self, callback, timeout=None):
        """
        Blocks until message is available (pushed by the broker) and process it with ``callback``
        :param callback:
        :param timeout:
        :return:
        """
        self._channel.queue_declare(queue=self.queue_name, auto_delete=False)
        log.info("declared queue: %s with auto_delete=False", self.queue_name)

        def _callback(ch, method, properties, body):
            log.info(
                "Received on queue [%s] %s. Payload properties: [%s]",
                self.queue_name,
                body,
                properties,
            )

            callback(
                payload=body, message_properties=properties, rmq_connection_wrapper=self
            )

        # TODO: reconsider auto_ack
        self._channel.basic_consume(
            self.queue_name, on_message_callback=_callback, auto_ack=True
        )

        try:
            log.info("Starting consuming on queue [%s]", self.queue_name)
            self._channel.start_consuming()  # a blocking call
        except KeyboardInterrupt:
            self.stop_blocking_consume()
            self._connection.close()
        except:
            log.exception("Error consuming on queue [%s]", self.queue_name)
            raise

    def stop_blocking_consume(self):
        log.info("Stopping consuming on queue [%s]", self.queue_name)
        self._channel.stop_consuming()


class RMQNonBlockingConnectionWrapper(RMQConnectionWrapperBase):
    """
    Async RMQConnection wrapper implemented in a Continuation-Passing style. Reuses a custom io_loop.
    Declares and binds a queue to a fanout exchange for publishing messages.
    Caches connection and channel for reuse.
    Not thread safe.
    TODO: implement event-based connection recovery and error handling (see rabbitmq docs for examples).
    """

    def __init__(self, opts, io_loop=None, queue_name=None, timeout=60):
        super().__init__(opts, queue_name=queue_name)

        self._io_loop = io_loop or tornado.ioloop.IOLoop.instance()
        self._io_loop.make_current()

        self._channel = None
        self._timeout = timeout
        self._callback = None

        # set up exchange for message broadcast
        self._fanout_exchange_name = self.queue_name

    def connect(self):
        """

        :return:
        """
        self._connection = SelectConnection(
            parameters=pika.ConnectionParameters(
                host=self._host, credentials=self._creds
            ),
            on_open_callback=self._on_connection_open,
            on_open_error_callback=self._on_connection_error,
            custom_ioloop=self._io_loop,
        )

    def _on_connection_open(self, connection):
        """
        Invoked by pika when connection is opened successfully
        :param connection:
        :return:
        """
        connection.add_on_close_callback(self._on_connection_closed)
        self._channel = connection.channel(on_open_callback=self._on_channel_open)

    def _on_connection_error(self, connection, exception):
        """
        Invoked by pika when connection on connection error
        :param connection:
        :param exception:
        :return:
        """
        log.error("Failed to connect", exc_info=True)

    def _on_connection_closed(self, connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.

        """
        log.info("Connection closed for reason [%s]", reason)
        self._reconnect()

    def _reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.

        Note: RabbitMQ uses heartbeats to detect and close "dead" connections and to prevent network devices
        (firewalls etc.) from terminating "idle" connections.
        From version 3.5.5 on, the default timeout is set to 60 seconds

        """
        if not self._closing:
            # Create a new connection
            log.info("Reconnecting...")
            self.connect()

    def _on_channel_open(self, channel):
        """
        Invoked by pika when channel is opened successfully
        :param channel:
        :return:
        """
        self._channel.exchange_declare(
            exchange=self._fanout_exchange_name,
            exchange_type=ExchangeType.fanout,
            callback=self.on_exchange_declare,
        )

    def on_exchange_declare(self, method):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        """
        log.info("Exchange declared: %s", self._fanout_exchange_name)
        self._channel.queue_declare(
            queue=self.queue_name, callback=self._on_queue_declared
        )

    def _on_queue_declared(self, method):
        """
        Invoked by pika when queue is declared successfully
        :param method:
        :return:
        """
        log.info("Queue declared: %s", method.method.queue)

        self._channel.queue_bind(
            method.method.queue,
            self._fanout_exchange_name,
            routing_key=self.queue_name,
            callback=self._on_queue_bind,
        )

    def _on_queue_bind(self, method):
        """
        Invoked by pika when queue bound successfully. Set up consumer message callback as well.
        :param method:
        :return:
        """

        log.info("Queue bound [%s]", self.queue_name)

        def _callback_wrapper(channel, method, properties, payload):
            if self._callback:
                log.info("Calling message callback")
                return self._callback(payload, properties)

        self._channel.basic_consume(self.queue_name, _callback_wrapper, auto_ack=True)

    def register_message_callback(
        self, callback: Callable[[Any, BasicProperties], None]
    ):
        """
        Register a callback that receives message on a queue
        :param callback:
        :return:
        """
        self._callback = callback

    @salt.ext.tornado.gen.coroutine
    def publish(
        self,
        payload,
        queue_name=None,
        reply_queue_name=None,
        correlation_id=None,
        auto_delete_queue=False,
        broadcast=True,
    ):
        """
        Publishes ``payload`` with thr routing key ``queue_name`` (via direct exchange or via fanout/broadcast),
        passes along optional name of the reply queue in message metadata. Non-blocking.
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).
        :param correlation_id: correlation_id (used for the RPC pattern in conjunction with reply queue)
        :param payload: message body
        :param queue_name: queue name
        :param reply_queue_name: optional name of the reply queue
        :param auto_delete_queue: set the type of queue to "auto_delete"
        (it will be deleted when the last consumer disappears)
        :param broadcast: whether to broadcast via fanout exchange
        :return:
        """

        publish_queue_name = queue_name if queue_name else self.queue_name

        # See https://www.rabbitmq.com/tutorials/amqp-concepts.html
        exchange = self._fanout_exchange_name if broadcast else ""

        # For the IPC pattern, set up the "reply-to" header and "correlation_id"
        properties = pika.BasicProperties()
        properties.reply_to = reply_queue_name if reply_queue_name else None
        properties.correlation_id = correlation_id if correlation_id else uuid4().hex
        properties.app_id = str(threading.get_ident())  # use this for tracing

        log.info(
            "Sending payload to queue [%s] via exchange [%s]: %s. Payload properties: %s",
            publish_queue_name,
            exchange,
            payload,
            properties,
        )

        try:
            # TODO: consider different queue types (durable, quorum, etc.)
            res = yield self._async_queue_declare(
                publish_queue_name, auto_delete_queue=auto_delete_queue
            )

            if broadcast:
                log.info(
                    "Binding queue [%s] to exchange [%s]", publish_queue_name, exchange
                )
                res = yield self._async_queue_bind(publish_queue_name, exchange)

            self._channel.basic_publish(
                exchange=exchange,
                routing_key=publish_queue_name,
                body=payload,
                properties=properties,
            )  # add reply queue to the properties
            log.info(
                "Sent payload to queue [%s] via exchange [%s]: %s",
                publish_queue_name,
                exchange,
                payload,
            )
        except:
            log.exception(
                "Error publishing to queue [%s] via exchange [%s]",
                publish_queue_name,
                exchange,
            )
            raise

    @salt.ext.tornado.gen.coroutine
    def publish_reply(self, payload, properties: BasicProperties):
        """
        Publishes reply ``payload`` routing it to the reply queue. Non-blocking.
        :param payload: message body
        :param properties: payload properties/metadata
        :return:
        """
        reply_queue_name = properties.reply_to

        if not reply_queue_name:
            raise ValueError("properties.reply_to must be set")

        log.info(
            "Sending reply payload on queue [%s]: %s. Payload properties: %s",
            reply_queue_name,
            payload,
            properties,
        )

        # publish reply on a queue that will be deleted after consumer cancels or disconnects
        # do not broadcast replies
        # TODO: look into queue types (durable, quorum, etc.)

        self.publish(
            payload,
            queue_name=reply_queue_name,
            auto_delete_queue=True,
            broadcast=False,
        )

    @salt.ext.tornado.gen.coroutine
    def _async_queue_bind(self, publish_queue_name: str, exchange: str):
        future = salt.ext.tornado.concurrent.Future()

        def callback(method):
            log.info("bound queue: %s to exchange: %s", method.method.queue, exchange)
            future.set_result(method)

        # TODO: consider different queue types (durable, quorum, etc.)
        res = self._channel.queue_bind(
            publish_queue_name,
            exchange,
            routing_key=publish_queue_name,
            callback=callback,
        )
        return future

    @salt.ext.tornado.gen.coroutine
    def _async_queue_declare(self, publish_queue_name: str, auto_delete_queue: bool):
        future = salt.ext.tornado.concurrent.Future()

        def callback(method):
            log.info("declared queue: %s", method.method.queue)
            future.set_result(method)

        if not self._channel:
            raise ValueError("_channel must be set")

        # TODO: consider different queue types (durable, quorum, etc.)
        res = self._channel.queue_declare(
            publish_queue_name, auto_delete=auto_delete_queue, callback=callback
        )
        return future


class AsyncRabbitMQReqChannel(salt.transport.client.ReqChannel):
    """
    Encapsulate sending routines to RabbitMQ broker. TODO: simplify this. Original implementation was copied from ZeroMQ.
    RMQ Channels default to 'crypt=aes'
    """

    # This class is only a singleton per minion/master pair
    # mapping of io_loop -> {key -> channel}
    instance_map = weakref.WeakKeyDictionary()
    async_methods = [
        "crypted_transfer_decode_dictentry",
        "_crypted_transfer",
        "_do_transfer",
        "_uncrypted_transfer",
        "send",
    ]
    close_methods = [
        "close",
    ]

    def __new__(cls, opts, **kwargs):
        """
        Only create one instance of channel per __key()
        """

        # do we have any mapping for this io_loop
        io_loop = kwargs.get("io_loop")
        if io_loop is None:
            io_loop = tornado.ioloop.IOLoop.current()

        if io_loop not in cls.instance_map:
            cls.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = cls.instance_map[io_loop]

        key = cls.__key(opts, **kwargs)
        obj = loop_instance_map.get(key)
        if obj is None:
            log.info("Initializing new AsyncRabbitMQReqChannel for %s", key)
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            obj = object.__new__(cls)
            obj.__singleton_init__(opts, **kwargs)
            obj._instance_key = key
            loop_instance_map[key] = obj
            obj._refcount = 1
            obj._refcount_lock = threading.RLock()
            log.trace(
                "Inserted key into loop_instance_map id %s for key %s and process %s",
                id(loop_instance_map),
                key,
                os.getpid(),
            )
        else:
            with obj._refcount_lock:
                obj._refcount += 1
            log.info("Re-using AsyncRabbitMQReqChannel for %s", key)
        return obj

    def __deepcopy__(self, memo):
        cls = self.__class__
        # pylint: disable=too-many-function-args
        result = cls.__new__(cls, copy.deepcopy(self.opts, memo))
        # pylint: enable=too-many-function-args
        memo[id(self)] = result
        for key in self.__dict__:
            if key in ("_io_loop", "_refcount", "_refcount_lock"):
                continue
                # The _io_loop has a thread Lock which will fail to be deep
                # copied. Skip it because it will just be recreated on the
                # new copy.
            if key == "message_client":
                # Recreate the message client because it will fail to be deep
                # copied. The reason is the same as the io_loop skip above.
                setattr(
                    result,
                    key,
                    AsyncReqMessageClientPool(
                        result.opts,
                        args=(
                            result.opts,
                            self.master_uri,
                        ),
                        kwargs={"io_loop": self._io_loop},
                    ),
                )

                continue
            setattr(result, key, copy.deepcopy(self.__dict__[key], memo))
        return result

    @classmethod
    def force_close_all_instances(cls):
        """
        Will force close all instances

        TODO: PR - add a justification why we need this for RMQ. Do we need this?

        :return: None
        """
        for weak_dict in list(cls.instance_map.values()):
            for instance in list(weak_dict.values()):
                instance.close()

    @classmethod
    def __key(cls, opts, **kwargs):
        return (
            opts["pki_dir"],  # where the keys are stored
            opts["id"],  # minion ID
            kwargs.get("master_uri", opts.get("master_uri")),  # master ID
            kwargs.get("crypt", "aes"),  # TODO: use the same channel for crypt
        )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, **kwargs):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, **kwargs):
        self.opts = dict(opts)
        self.ttype = "rabbitmq"

        # crypt defaults to 'aes'
        self.crypt = kwargs.get("crypt", "aes")

        if "master_uri" in kwargs:
            self.opts["master_uri"] = kwargs["master_uri"]

        self._io_loop = kwargs.get("io_loop")
        if self._io_loop is None:
            self._io_loop = tornado.ioloop.IOLoop.current()

        if self.crypt != "clear":
            # we don't need to worry about auth as a kwarg, since its a singleton
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self._io_loop)
        log.info(
            "Connecting the Minion to the Master RabbitMQ queue for master with URI: %s",
            self.master_uri,
        )
        self.message_client = AsyncReqMessageClientPool(
            self.opts,
            args=(
                self.opts,
                self.master_uri,
            ),
            kwargs={"io_loop": self._io_loop},
        )

        self._closing = False

    def close(self):
        """
        Since the message_client creates sockets and assigns them to the IOLoop we have to
        specifically destroy them, since we aren't the only ones with references to the FDs
        """
        if self._closing:
            return

        if self._refcount > 1:
            # Decrease refcount
            with self._refcount_lock:
                self._refcount -= 1
            log.info(
                "This is not the last %s instance. Not closing yet.",
                self.__class__.__name__,
            )
            return

        log.info("Closing %s instance", self.__class__.__name__)
        self._closing = True
        if hasattr(self, "message_client"):
            self.message_client.close()

        # Remove the entry from the instance map so that a closed entry may not
        # be reused.
        # This forces this operation even if the reference count of the entry
        # has not yet gone to zero.
        if self._io_loop in self.__class__.instance_map:
            loop_instance_map = self.__class__.instance_map[self._io_loop]
            if self._instance_key in loop_instance_map:
                del loop_instance_map[self._instance_key]
            if not loop_instance_map:
                del self.__class__.instance_map[self._io_loop]

    # pylint: disable=no-dunder-del
    def __del__(self):
        with self._refcount_lock:
            # Make sure we actually close no matter if something
            # went wrong with our ref counting
            self._refcount = 1
        try:
            self.close()
        except OSError as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise

    # pylint: enable=no-dunder-del

    @property
    def master_uri(self):
        if "master_uri" in self.opts:
            return self.opts["master_uri"]

        # if by chance master_uri is not there..
        if "master_ip" in self.opts:
            return _get_master_uri(
                self.opts["master_ip"],
                self.opts["master_port"],
            )

        # if we've reached here something is very abnormal
        raise SaltException("ReqChannel: missing master_uri/master_ip in self.opts")

    def _package_load(self, load):
        return {
            "enc": self.crypt,
            "load": load,
        }

    @salt.ext.tornado.gen.coroutine
    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        if not self.auth.authenticated:
            # Return control back to the caller, continue when authentication succeeds
            yield self.auth.authenticate()
        # Return control to the caller. When send() completes, resume by populating ret with the Future.result
        ret = yield self.message_client.send(
            self._package_load(self.auth.crypticle.dumps(load)),
            timeout=timeout,
            tries=tries,
        )
        key = self.auth.get_keys()
        if "key" not in ret:
            # Reauth in the case our key is deleted on the master side.
            yield self.auth.authenticate()
            ret = yield self.message_client.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
                tries=tries,
            )
        if HAS_M2:
            aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            aes = cipher.decrypt(ret["key"])
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        data = pcrypt.loads(ret[dictkey])
        data = salt.transport.frame.decode_embedded_strs(data)
        raise salt.ext.tornado.gen.Return(data)

    @salt.ext.tornado.gen.coroutine
    def _crypted_transfer(self, load, tries=3, timeout=60, raw=False):
        """
        Send a load across the wire, with encryption

        In case of authentication errors, try to renegotiate authentication
        and retry the method.

        Indeed, we can fail too early in case of a master restart during a
        minion state execution call

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        """

        @salt.ext.tornado.gen.coroutine
        def _do_transfer():
            # Yield control to the caller. When send() completes, resume by populating data with the Future.result
            data = yield self.message_client.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
                tries=tries,
            )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data, raw)
            if not raw:
                data = salt.transport.frame.decode_embedded_strs(data)
            raise salt.ext.tornado.gen.Return(data)

        if not self.auth.authenticated:
            # Return control back to the caller, resume when authentication succeeds
            yield self.auth.authenticate()
        try:
            # We did not get data back the first time. Retry.
            ret = yield _do_transfer()
        except salt.crypt.AuthenticationError:
            # If auth error, return control back to the caller, continue when authentication succeeds
            yield self.auth.authenticate()
            ret = yield _do_transfer()
        raise salt.ext.tornado.gen.Return(ret)

    @salt.ext.tornado.gen.coroutine
    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        """
        Send a load across the wire in cleartext

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        """
        ret = yield self.message_client.send(
            self._package_load(load),
            timeout=timeout,
            tries=tries,
        )

        raise salt.ext.tornado.gen.Return(ret)

    @salt.ext.tornado.gen.coroutine
    def send(self, load, tries=3, timeout=60, raw=False):
        """
        Send a request, return a future which will complete when we send the message
        """
        if self.crypt == "clear":
            ret = yield self._uncrypted_transfer(load, tries=tries, timeout=timeout)
        else:
            ret = yield self._crypted_transfer(
                load, tries=tries, timeout=timeout, raw=raw
            )
        raise salt.ext.tornado.gen.Return(ret)


class AsyncRabbitMQPubChannel(
    salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.AsyncPubChannel
):
    """
    A transport channel backed by RabbitMQ for a Salt Publisher to use to
    publish commands to connected minions
    """

    async_methods = [
        "connect",
        "_decode_messages",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.ttype = "rabbitmq"
        self.io_loop = kwargs.get("io_loop") or tornado.ioloop.IOLoop.instance()
        if not self.io_loop:
            raise ValueError("self.io_loop must be set")

        self._closing = False

        self.hexid = hashlib.sha1(
            salt.utils.stringutils.to_bytes(self.opts["id"])
        ).hexdigest()
        self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)
        self.serial = salt.payload.Serial(self.opts)
        self._rmq_non_blocking_connection_wrapper = RMQNonBlockingConnectionWrapper(
            self.opts, io_loop=self.io_loop, queue_name="minion_consumer_queue"
        )
        self._rmq_non_blocking_connection_wrapper.connect()

    def close(self):
        if self._closing is True:
            return

        self._closing = True

    # pylint: disable=no-dunder-del
    def __del__(self):
        self.close()

    # pylint: enable=no-dunder-del
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # TODO: this is the time to see if we are connected, maybe use the req channel to guess?
    @salt.ext.tornado.gen.coroutine
    def connect(self):
        """
        Connects minion to master.
        TODO: anything else that needs to be done for broker-based connections?
        :return:
        """

        if not self.auth.authenticated:
            yield self.auth.authenticate()

        log.info(
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
            payload = self.serial.loads(messages[0])
            payload = (
                self.serial.loads(payload["payload"])
                if "payload" in payload
                else self.serial.loads(payload)
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
                log.info("Publish received for not this minion: %s", message_target)
                raise salt.ext.tornado.gen.Return(None)
            payload = self.serial.loads(messages[1])
        else:
            raise Exception(
                (
                    "Invalid number of messages ({}) in rabbitmq pub"
                    "message from master"
                ).format(len(messages_len))
            )
        # Yield control back to the caller. When the payload has been decoded, assign
        # the decoded payload to 'ret' and resume operation
        ret = yield self._decode_payload(payload)
        raise salt.ext.tornado.gen.Return(ret)

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        if callback is None:
            self._rmq_non_blocking_connection_wrapper.register_message_callback(
                callback=None
            )

        @salt.ext.tornado.gen.coroutine
        def wrap_callback(messages, _):
            payload = yield self._decode_messages(messages)
            if payload is not None:
                callback(payload)

        self._rmq_non_blocking_connection_wrapper.register_message_callback(
            callback=wrap_callback
        )


class RabbitMQReqServerChannel(
    salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel
):
    """
    Encapsulate synchronous operations for a request channel
    """

    def __init__(self, opts):
        salt.transport.server.ReqServerChannel.__init__(self, opts)
        self._closing = False
        self._monitor = None
        self._w_monitor = None
        self._rmq_blocking_connection_wrapper = RMQBlockingConnectionWrapper(opts)

    def close(self):
        """
        Cleanly shutdown the router socket
        """
        if self._closing:
            return

    def pre_fork(self, process_manager):
        """
        Pre-fork we need to generate AES encryption key

        :param func process_manager: An instance of salt.utils.process.ProcessManager
        """
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)

    def post_fork(self, payload_handler, io_loop):
        """
        After forking we need to set up handlers to listen to the
        router

        :param func payload_handler: A function to called to handle incoming payloads as
                                     they are picked up off the wire
        :param IOLoop io_loop: An instance of a Tornado IOLoop, to handle event scheduling
        """

        if not io_loop:
            raise ValueError("io_loop must be set")

        self.payload_handler = payload_handler
        self.io_loop = io_loop

        salt.transport.mixins.auth.AESReqServerMixin.post_fork(
            self, payload_handler, io_loop
        )

        self._rmq_nonblocking_connection_wrapper = RMQNonBlockingConnectionWrapper(
            self.opts, io_loop=io_loop
        )
        self._rmq_nonblocking_connection_wrapper.register_message_callback(
            self.handle_message
        )
        self._rmq_nonblocking_connection_wrapper.connect()

    @salt.ext.tornado.gen.coroutine
    def handle_message(self, payload, message_properties: pika.BasicProperties):
        """
        Handle incoming messages from underlying streams

        :param rmq_connection_wrapper:
        :param dict payload: A payload to process
        :param message_properties message metadata of type ``pika.BasicProperties``
        """

        rmq_connection_wrapper = self._rmq_nonblocking_connection_wrapper

        try:
            payload = self.serial.loads(payload)
            if (
                "payload" in payload
            ):  # TODO: FIXME. Looks like double-encoding somewhere
                payload = payload["payload"]
                payload = self.serial.loads(payload)

            payload = self._decode_payload(payload)
        except Exception as exc:  # pylint: disable=broad-except
            exc_type = type(exc).__name__
            if exc_type == "AuthenticationError":
                log.info(
                    "Minion failed to auth to master. Since the payload is "
                    "encrypted, it is not known which minion failed to "
                    "authenticate. It is likely that this is a transient "
                    "failure due to the master rotating its public key."
                )
            else:
                log.error("Bad load from minion: %s: %s", exc_type, exc)
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps("bad load"), message_properties
            )

            raise salt.ext.tornado.gen.Return()

        # TODO helper functions to normalize payload?
        if not isinstance(payload, dict) or not isinstance(payload.get("load"), dict):
            log.error(
                "payload and load must be a dict. Payload was: %s and load was %s",
                payload,
                payload.get("load"),
            )
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps("payload and load must be a dict"), message_properties
            )
            raise salt.ext.tornado.gen.Return()

        try:
            id_ = payload["load"].get("id", "")
            if "\0" in id_:
                log.error("Payload contains an id with a null byte: %s", payload)
                rmq_connection_wrapper.publish_reply(
                    self.serial.dumps("bad load: id contains a null byte"),
                    message_properties,
                )
                raise salt.ext.tornado.gen.Return()
        except TypeError:
            log.error("Payload contains non-string id: %s", payload)
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps("bad load: id {} is not a string".format(id_)),
                message_properties,
            )
            raise salt.ext.tornado.gen.Return()

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload["enc"] == "clear" and payload.get("load", {}).get("cmd") == "_auth":
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps(self._auth(payload["load"])), message_properties
            )
            raise salt.ext.tornado.gen.Return()

        # TODO: test
        try:
            # Take the payload_handler function that was registered when we created the channel
            # and call it, returning control to the caller until it completes
            ret, req_opts = yield self.payload_handler(
                payload, message_properties=message_properties
            )
        except Exception as e:  # pylint: disable=broad-except
            log.error("Some exception handling a payload from minion", exc_info=True)
            # always attempt to return an error to the minion
            rmq_connection_wrapper.publish_reply(
                "Some exception handling minion payload", message_properties
            )
            raise salt.ext.tornado.gen.Return()

        req_fun = req_opts.get("fun", "send")
        if req_fun == "send_clear":
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps(ret), message_properties
            )

        elif req_fun == "send":
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps(self.crypticle.dumps(ret)), message_properties
            )

        elif req_fun == "send_private":
            rmq_connection_wrapper.publish_reply(
                self.serial.dumps(
                    self._encrypt_private(
                        ret,
                        req_opts["key"],
                        req_opts["tgt"],
                    )
                ),
                message_properties,
            )
        else:
            log.error("Unknown req_fun %s", req_fun)
            # always attempt to return an error to the minion
            rmq_connection_wrapper.publish_reply(
                "Server-side exception handling payload", message_properties
            )
        raise salt.ext.tornado.gen.Return()

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


class RabbitMQPubServerChannel(salt.transport.server.PubServerChannel):
    """
    Encapsulate synchronous operations for a publisher channel
    """

    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?
        self.ckminions = salt.utils.minions.CkMinions(self.opts)

        self._rmq_blocking_connection_wrapper = RMQBlockingConnectionWrapper(
            opts, queue_name="minion_consumer_queue"
        )  # RMQBlockingConnectionWrapper(opts, queue_name="minion_consumer_queue")

    def connect(self):
        return salt.ext.tornado.gen.sleep(5)  # TODO: why is this here?

    def pre_fork(self, process_manager, kwargs=None):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        """

    def pub_connect(self):
        """
        Do nothing, assuming RMQ broker is running
        """

    def _generate_payload(self, load):
        payload = {"enc": "aes"}
        crypticle = salt.crypt.Crypticle(
            self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
        )
        payload["load"] = crypticle.dumps(load)
        if self.opts["sign_pub_messages"]:
            master_pem_path = os.path.join(self.opts["pki_dir"], "master.pem")
            log.info("Signing data packet")
            payload["sig"] = salt.crypt.sign_message(master_pem_path, payload["load"])
        int_payload = {"payload": self.serial.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load["tgt_type"] == "list":
            int_payload["topic_lst"] = load["tgt"]

        # If zmq_filtering is enabled, target matching has to happen master side
        match_targets = ["pcre", "glob", "list"]
        if self.opts["zmq_filtering"] and load["tgt_type"] in match_targets:
            # Fetch a list of minions that match
            _res = self.ckminions.check_minions(load["tgt"], tgt_type=load["tgt_type"])
            match_ids = _res["minions"]

            log.info("Publish Side Match: %s", match_ids)
            # Send list of minions thru so zmq can target them
            int_payload["topic_lst"] = match_ids
        payload = self.serial.dumps(int_payload)
        return payload

    def publish(self, load, **optional_transport_args):
        """
        Publish "load" to minions. This sends the load to the RMQ broker
        process which does the actual sending to minions.

        :param dict load: A load to be sent across the wire to minions
        """

        payload = self._generate_payload(load)

        log.info(
            "Sending payload to rabbitmq publish daemon. jid=%s size=%d",
            load.get("jid", None),
            len(payload),
        )

        message_properties = None
        if optional_transport_args:
            message_properties = optional_transport_args.get("message_properties", None)
            if not isinstance(message_properties, BasicProperties):
                raise TypeError(
                    "message_properties must be of type {!r} instead of {!r}".format(
                        type(BasicProperties), type(message_properties)
                    )
                )

        # send
        self._rmq_blocking_connection_wrapper.publish(
            payload,
            reply_queue_name=message_properties.reply_to
            if message_properties
            else None,
            correlation_id=message_properties.correlation_id
            if message_properties
            else None,
        )
        log.info("Sent payload to rabbitmq publish daemon.")


class AsyncReqMessageClientPool(salt.transport.MessageClientPool):
    """
    Wrapper class of AsyncReqMessageClientPool to avoid blocking waiting while writing data to socket.
    """

    def __init__(self, opts, args=None, kwargs=None):
        self._closing = False
        super().__init__(AsyncReqMessageClient, opts, args=args, kwargs=kwargs)

    def close(self):
        if self._closing:
            return

        self._closing = True
        for message_client in self.message_clients:
            message_client.close()
        self.message_clients = []

    def send(self, *args, **kwargs):
        message_clients = sorted(self.message_clients, key=lambda x: len(x.send_queue))
        return message_clients[0].send(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# TODO: unit tests!
class AsyncReqMessageClient:
    """
    This class gives a future-based
    interface to sending and receiving messages. This works around the primary
    limitation of serialized send/recv on the underlying socket by queueing the
    message sends in this class. In the future if we decide to attempt to multiplex
    we can manage a pool of REQ/REP sockets-- but for now we'll just do them in serial

    TODO: this implementation was adapted from ZeroMQ. Simplify this for RMQ.
    """

    def __init__(self, opts, addr, io_loop=None):
        """
        Create an asynchronous message client

        :param dict opts: The salt opts dictionary
        :param str addr: The interface IP address to bind to
        :param IOLoop io_loop: A Tornado IOLoop event scheduler [tornado.ioloop.IOLoop]
        """
        self.opts = opts
        self.addr = addr
        self._rmq_blocking_connection_wrapper = RMQBlockingConnectionWrapper(opts)

        if io_loop is None:
            self.io_loop = salt.ext.tornado.ioloop.IOLoop.current()
        else:
            self.io_loop = io_loop

        self.serial = salt.payload.Serial(self.opts)

        self.send_queue = []
        # mapping of message -> future
        self.send_future_map = {}

        self.send_timeout_map = {}  # message -> timeout
        self._closing = False

    # TODO: timeout all in-flight sessions, or error
    def close(self):
        try:
            if self._closing:
                return
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

    @salt.ext.tornado.gen.coroutine
    def _internal_send_recv(self):
        while self.send_queue:
            message = self.send_queue[0]
            future = self.send_future_map.get(message, None)
            if future is None:
                # Timedout
                del self.send_queue[0]
                continue

            # send
            def mark_future(msg):
                if not future.done():
                    data = self.serial.loads(msg)
                    future.set_result(data)

            # send message
            message_correlation_id = (
                uuid4().hex
            )  # TODO: optimize this to use a combination of hostname/port
            self._rmq_blocking_connection_wrapper.publish(
                message, reply_queue_name=message_correlation_id
            )
            self._rmq_blocking_connection_wrapper.consume_reply(
                mark_future, reply_queue_name=message_correlation_id
            )

            try:
                ret = yield future
            except Exception as err:  # pylint: disable=broad-except
                del self.send_queue[0]
                continue
            del self.send_queue[0]
            self.send_future_map.pop(message, None)
            self.remove_message_timeout(message)

    def remove_message_timeout(self, message):
        if message not in self.send_timeout_map:
            return
        timeout = self.send_timeout_map.pop(message, None)
        if timeout is not None:
            # Hasn't been already timedout
            self.io_loop.remove_timeout(timeout)

    def timeout_message(self, message):
        """
        Handle a message timeout by removing it from the sending queue
        and informing the caller

        :raises: SaltReqTimeoutError
        """
        future = self.send_future_map.pop(message, None)
        # In a race condition the message might have been sent by the time
        # we're timing it out. Make sure the future is not None
        if future is not None:
            del self.send_timeout_map[message]
            if future.attempts < future.tries:
                future.attempts += 1
                log.info(
                    "SaltReqTimeoutError, retrying. (%s/%s)",
                    future.attempts,
                    future.tries,
                )
                self.send(
                    message,
                    timeout=future.timeout,
                    tries=future.tries,
                    future=future,
                )

            else:
                future.set_exception(SaltReqTimeoutError("Message timed out"))

    def send(
        self, message, timeout=None, tries=3, future=None, callback=None, raw=False
    ):
        """
        Return a future which will be completed when the message has a response
        """
        if future is None:
            future = salt.ext.tornado.concurrent.Future()
            future.tries = tries
            future.attempts = 0
            future.timeout = timeout
            # if a future wasn't passed in, we need to serialize the message
            message = self.serial.dumps(message)

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)
        # Add this future to the mapping
        self.send_future_map[message] = future

        if self.opts.get("detect_mode") is True:
            timeout = 1

        if timeout is not None:
            send_timeout = self.io_loop.call_later(
                timeout, self.timeout_message, message
            )
            self.send_timeout_map[message] = send_timeout

        if not self.send_queue:
            self.io_loop.spawn_callback(self._internal_send_recv)

        self.send_queue.append(message)

        return future
