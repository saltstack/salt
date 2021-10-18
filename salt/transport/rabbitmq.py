"""
Rabbitmq transport classes
This is a copy/modify of zeromq implementation with zeromq-specific bits removed.
TODO: refactor transport implementations so that tcp, zeromq, rabbitmq share common code
"""
import errno
import logging
import threading
import time
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
from pika.exceptions import ChannelClosedByBroker
from pika.exchange_type import ExchangeType
from pika.spec import PERSISTENT_DELIVERY_MODE
from salt.exceptions import SaltException, SaltReqTimeoutError

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
    def __init__(self, opts, **kwargs):
        self._opts = opts
        self._validate_set_broker_topology(self._opts, **kwargs)

        # TODO: think about a better way to generate queue names
        # each possibly running on different machine
        master_port = (
            self._opts["master_port"]
            if "master_port" in self._opts
            else self._opts["ret_port"]
        )
        if not master_port:
            raise KeyError("master_port must be set")

        self._connection = None
        self._channel = None
        self._closing = False

    def _validate_set_broker_topology(self, opts, **kwargs):
        """
        Validate broker topology and set private variables. For example:
            {
                "transport: rabbitmq",
                "transport_rabbitmq_address": "localhost",
                "transport_rabbitmq_auth": { "username": "user", "password": "bitnami"},
                "transport_rabbitmq_vhost": "/",
                "transport_rabbitmq_create_topology_ondemand": "True",
                "transport_rabbitmq_publisher_exchange_name":" "exchange_to_publish_messages",
                "transport_rabbitmq_consumer_exchange_name": "exchange_to_bind_queue_to_receive_messages_from",
                "transport_rabbitmq_consumer_queue_name": "queue_to_consume_messages_from",

                "transport_rabbitmq_consumer_queue_declare_arguments": "",
                "transport_rabbitmq_publisher_exchange_declare_arguments": ""
                "transport_rabbitmq_consumer_exchange_declare_arguments": ""
            }
        """

        # rmq broker address
        self._host = (
            opts["transport_rabbitmq_address"]
            if "transport_rabbitmq_address" in opts
            else "localhost"
        )
        if not self._host:
            raise ValueError("Host must be set")

        # rmq broker credentials (TODO: support other types of auth. eventually)
        creds_key = "transport_rabbitmq_auth"
        if creds_key not in opts:
            raise KeyError("Missing key {!r}".format(creds_key))
        creds = opts[creds_key]

        if "username" not in creds and "password" not in creds:
            raise KeyError("username or password must be set")
        self._creds = pika.PlainCredentials(creds["username"], creds["password"])

        # rmq broker vhost
        vhost_key = "transport_rabbitmq_vhost"
        if vhost_key not in opts:
            raise KeyError("Missing key {!r}".format(vhost_key))
        self._vhost = opts[vhost_key]

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

    @property
    def queue_name(self):
        return self._consumer_queue_name

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

    def __init__(self, opts, **kwargs):
        super().__init__(opts, **kwargs)

        self._connect(self._host, self._creds, self._vhost)

        if self._create_topology_ondemand:
            try:
                self._create_topology()
            except:
                log.exception("Exception when creating RMQ topology.")
                raise
        else:
            log.info("Skipping rmq topology creation.")

    def _connect(self, host, creds, vhost):
        log.debug("Connecting to host [%s] and vhost [%s]", host, vhost)
        self._connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, credentials=creds, virtual_host=vhost)
        )
        self._channel = self._connection.channel()

    def _create_topology(self):
        ret = self._channel.exchange_declare(
            exchange=self._publisher_exchange_name,
            exchange_type=ExchangeType.fanout,
            durable=True,
            arguments=self._publisher_exchange_declare_arguments,
        )
        log.info(
            "declared publisher exchange: %s",
            self._publisher_exchange_name,
        )

        ret = self._channel.exchange_declare(
            exchange=self._consumer_exchange_name,
            exchange_type=ExchangeType.fanout,
            durable=True,
            arguments=self._consumer_exchange_declare_arguments,
        )
        log.info(
            "declared consumer exchange: %s",
            self._consumer_exchange_name,
        )

        ret = self._channel.queue_declare(
            self._consumer_queue_name,
            durable=True,
            arguments=self._consumer_queue_declare_arguments,  # expire the quorum queue if unused
        )
        log.info(
            "declared queue: %s",
            self._consumer_queue_name,
        )

        log.info(
            "Binding queue [%s] to exchange [%s]",
            self._consumer_queue_name,
            self._consumer_exchange_name,
        )
        ret = self._channel.queue_bind(
            self._consumer_queue_name,
            self._consumer_exchange_name,
            routing_key=self._consumer_queue_name,
        )

    def publish(
        self,
        payload,
        exchange_name=None,
        routing_key="",  # must be a string
        reply_queue_name=None,
    ):
        """
        Publishes ``payload`` to the specified ``exchange_name`` (via direct exchange or via fanout/broadcast) with
        ``routing_key``, passes along optional name of the reply queue in message metadata. Non-blocking.
        Recover from connection failure (with a retry).

        :param reply_queue_name: optional reply queue name
        :param payload: message body
        :param exchange_name: exchange name
        :param routing_key: optional name of the routing key, exchange specific
        (it will be deleted when the last consumer disappears)
        :return:
        """
        while (
            not self._closing
        ):  # TODO: limit number of retries and use some retry decorator
            try:
                self._publish(
                    payload,
                    exchange_name=exchange_name
                    if exchange_name
                    else self._publisher_exchange_name,
                    routing_key=routing_key,
                    reply_queue_name=reply_queue_name,
                )

                break

            except pika.exceptions.ConnectionClosedByBroker:
                # Connection may have been terminated cleanly by the broker, e.g.
                # as a result of "rabbitmqtl" cli call. Attempt to reconnect anyway.
                log.exception("Connection exception when publishing.")
                log.info("Attempting to re-establish RMQ connection.")
                self._connect(self._host, self._creds, self._vhost)
            except pika.exceptions.ChannelWrongStateError:
                # Note: RabbitMQ uses heartbeats to detect and close "dead" connections and to prevent network devices
                # (firewalls etc.) from terminating "idle" connections.
                # From version 3.5.5 on, the default timeout is set to 60 seconds
                log.exception("Channel exception when publishing.")
                log.info("Attempting to re-establish RMQ connection.")
                self._connect(self._host, self._creds, self._vhost)

    def _publish(
        self,
        payload,
        exchange_name=None,
        routing_key=None,
        reply_queue_name=None,
    ):
        """
        Publishes ``payload`` to the specified ``queue_name`` (via direct exchange or via fanout/broadcast),
        passes along optional name of the reply queue in message metadata. Non-blocking.
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).

        :param payload: message body
        :param exchange_name: exchange name
        :param routing_key: and exchange-specific routing key
        :param reply_queue_name: optional name of the reply queue
        :return:
        """
        properties = pika.BasicProperties()
        properties.reply_to = reply_queue_name if reply_queue_name else None
        properties.app_id = str(threading.get_ident())  # use this for tracing
        # enable perisistent message delivery
        # see https://www.rabbitmq.com/confirms.html#publisher-confirms and
        # https://kousiknath.medium.com/dabbling-around-rabbit-mq-persistence-durability-message-routing-f4efc696098c
        properties.delivery_mode = PERSISTENT_DELIVERY_MODE

        log.info(
            "Sending payload to exchange [%s]: %s. Payload properties: %s",
            exchange_name,
            payload,
            properties,
        )

        try:
            self._channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=payload,
                properties=properties,  # added reply queue to the properties
                mandatory=True,
            )
            log.info(
                "Sent payload to exchange [%s] with routing_key [%s]: [%s]",
                exchange_name,
                routing_key,
                payload,
            )
        except:
            log.exception(
                "Error publishing to exchange [%s] with routing_key [%s]",
                exchange_name,
                routing_key,
            )
            raise

    def publish_reply(self, payload, properties: BasicProperties):
        """
        Publishes reply ``payload`` to the reply queue. Non-blocking.
        :param payload: message body
        :param properties: payload properties/metadata
        :return:
        """
        reply_to = properties.reply_to

        if not reply_to:
            raise ValueError("properties.reply_to must be set")

        log.info(
            "Sending reply payload with reply_to [%s]: %s. Payload properties: %s",
            reply_to,
            payload,
            properties,
        )

        self.publish(
            payload,
            exchange_name="",  # ExchangeType.direct,  # use the default exchange for replies
            routing_key=reply_to,
        )

    def consume(self, queue_name=None, timeout=60):
        """
        A non-blocking consume takes the next message off the queue.
        :param queue_name:
        :param timeout:
        :return:
        """
        log.info("Consuming payload on queue [%s]", queue_name)

        queue_name = queue_name or self._consumer_queue_name
        (method, properties, body) = next(
            self._channel.consume(
                queue=queue_name, inactivity_timeout=timeout, auto_ack=True
            )
        )
        return body

    def register_reply_callback(self, callback, reply_queue_name=None):
        """
        Registers RPC reply callback
        :param callback:
        :param reply_queue_name:
        :return:
        """

        def _callback(ch, method, properties, body):
            log.info(
                "Received reply on queue [%s]: %s. Reply payload properties: %s",
                reply_queue_name,
                body,
                properties,
            )
            callback(body)
            log.info("Processed callback for reply on queue [%s]", reply_queue_name)

            # Stop consuming so that auto_delete queue will be deleted
            self._channel.stop_consuming()
            log.info("Done consuming reply on queue [%s]", reply_queue_name)

        log.info("Starting basic_consume reply on queue [%s]", reply_queue_name)

        consumer_tag = self._channel.basic_consume(
            queue=reply_queue_name, on_message_callback=_callback, auto_ack=True
        )

        log.info("Started basic_consume reply on queue [%s]", reply_queue_name)

    def start_consuming(self):
        """
        Blocks and dispatches callbacks configured by ``self._channel.basic_consume()``
        :return:
        """
        # a blocking call until self._channel.stop_consuming() is called
        self._channel.start_consuming()


class RMQNonBlockingConnectionWrapper(RMQConnectionWrapperBase):
    """
    Async RMQConnection wrapper implemented in a Continuation-Passing style. Reuses a custom io_loop.
    Declares and binds a queue to a fanout exchange for publishing messages.
    Caches connection and channel for reuse.
    Not thread safe.
    TODO: implement event-based connection recovery and error handling (see rabbitmq docs for examples).
    """

    def __init__(self, opts, io_loop=None, **kwargs):
        super().__init__(opts, **kwargs)

        self._io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.instance()
        self._io_loop.make_current()

        self._channel = None
        self._callback = None

    def connect(self):
        """

        :return:
        """
        log.debug("Connecting to host [%s] and vhost [%s]", self._host, self._vhost)

        self._connection = SelectConnection(
            parameters=pika.ConnectionParameters(
                host=self._host, credentials=self._creds, virtual_host=self._vhost
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
        self._channel.add_on_close_callback(self._on_channel_closed)

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
        log.warning("Connection closed for reason [%s]", reason)
        if isinstance(reason, ChannelClosedByBroker):
            if reason.reply_code == 404:
                log.warning("Not recovering from 404. Make sure RMQ topology exists.")
                raise reason
            else:
                self._reconnect()

    def _on_channel_closed(self, channel, reason):
        log.warning("Channel closed for reason [%s]", reason)
        if isinstance(reason, ChannelClosedByBroker):
            if reason.reply_code == 404:
                log.warning("Not recovering from 404. Make sure RMQ topology exists.")
                raise reason
            else:
                self._reconnect()
        else:
            log.warning(
                "Not attempting to recover. Channel likely closed for legitimate reasons."
            )

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
            # sleep for a bit so that if for some reason we get into a reconnect loop we won't kill the system
            time.sleep(2)
            self.connect()

    def _on_channel_open(self, channel):
        """
        Invoked by pika when channel is opened successfully
        :param channel:
        :return:
        """
        if self._create_topology_ondemand:
            self._channel.exchange_declare(
                exchange=self._publisher_exchange_name,
                exchange_type=ExchangeType.fanout,
                durable=True,
                callback=self._on_exchange_declared,
            )
        else:
            log.info("Skipping rmq topology creation.")
            self._start_consuming(method=None)

    def _on_exchange_declared(self, method):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        """
        log.info("Exchange declared: %s", self._publisher_exchange_name)
        self._channel.queue_declare(
            queue=self._consumer_queue_name,
            durable=True,
            arguments=self._consumer_queue_declare_arguments,
            callback=self._on_queue_declared,
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
            self._consumer_exchange_name,
            routing_key=method.method.queue,
            callback=self._start_consuming,
        )

    def _start_consuming(self, method):
        """
        Invoked by pika when queue bound successfully. Set up consumer message callback as well.
        :param method:
        :return:
        """

        log.info("Starting consuming on queue [%s]", self.queue_name)

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
        exchange_name=None,
        routing_key=None,
    ):
        """
        Publishes ``payload`` with the routing key ``queue_name`` (via direct exchange or via fanout/broadcast),
        passes along optional name of the reply queue in message metadata. Non-blocking.
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).
        :param payload: message body
        :param routing_key: routing key
        :param exchange_name: exchange name to publish to
        :return:
        """

        properties = pika.BasicProperties()
        properties.reply_to = routing_key if routing_key else None
        properties.app_id = str(threading.get_ident())  # use this for tracing
        # enable persistent message delivery
        # see https://www.rabbitmq.com/confirms.html#publisher-confirms and
        # https://kousiknath.medium.com/dabbling-around-rabbit-mq-persistence-durability-message-routing-f4efc696098c
        properties.delivery_mode = PERSISTENT_DELIVERY_MODE

        log.info(
            "Sending payload to exchange [%s] with routing key [%s]: %s. Payload properties: %s",
            exchange_name,
            routing_key,
            payload,
            properties,
        )

        try:
            self._channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=payload,
                properties=properties,
                mandatory=True,  # see https://www.rabbitmq.com/confirms.html#publisher-confirms
            )

            log.info(
                "Sent payload to exchange [%s] with routing key [%s]: %s",
                exchange_name,
                routing_key,
                payload,
            )
        except:
            log.exception(
                "Error publishing to exchange [%s]",
                exchange_name,
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
        routing_key = properties.reply_to

        if not routing_key:
            raise ValueError("properties.reply_to must be set")

        log.info(
            "Sending reply payload to direct exchange with routing key [%s]: %s. Payload properties: %s",
            routing_key,
            payload,
            properties,
        )

        # publish reply on a queue that will be deleted after consumer cancels or disconnects
        # do not broadcast replies
        self.publish(
            payload,
            exchange_name="",  # ExchangeType.direct,  # use the default exchange for replies
            routing_key=routing_key,
        )

    @salt.ext.tornado.gen.coroutine
    def _async_queue_bind(self, queue_name: str, exchange: str):
        future = salt.ext.tornado.concurrent.Future()

        def callback(method):
            log.info("bound queue: %s to exchange: %s", method.method.queue, exchange)
            future.set_result(method)

        res = self._channel.queue_bind(
            queue_name,
            exchange,
            routing_key=queue_name,
            callback=callback,
        )
        return future

    @salt.ext.tornado.gen.coroutine
    def _async_queue_declare(self, queue_name: str):
        future = salt.ext.tornado.concurrent.Future()

        def callback(method):
            log.info("declared queue: %s", method.method.queue)
            future.set_result(method)

        if not self._channel:
            raise ValueError("_channel must be set")

        res = self._channel.queue_declare(
            queue_name,
            durable=True,
            arguments=self._consumer_queue_declare_arguments,
            callback=callback,
        )
        return future


class AsyncRabbitMQReqClient(salt.transport.base.RequestClient):
    """
    Encapsulate sending routines to RabbitMQ broker. TODO: simplify this. Original implementation was copied from ZeroMQ.
    RMQ Channels default to 'crypt=aes'
    """

    ttype = "rabbitmq"

    # an init for the singleton instance to call
    def __init__(self, opts, master_uri, io_loop, **kwargs):
        super().__init__(opts, master_uri, io_loop, **kwargs)
        self.opts = dict(opts)
        if "master_uri" in kwargs:
            self.opts["master_uri"] = kwargs["master_uri"]
        self.message_client = AsyncReqMessageClient(
            self.opts,
            self.master_uri,
            io_loop=self._io_loop,
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
    def send(self, load, tries=3, timeout=60):
        """
        Send a request, return a future which will complete when we send the message
        """
        ret = yield self.message_client.send(
            load,
            timeout=timeout,
            tries=tries,
        )
        raise salt.ext.tornado.gen.Return(ret)


class AsyncRabbitMQPubChannel(salt.transport.base.PublishClient):
    """
    A transport channel backed by RabbitMQ for a Salt Publisher to use to
    publish commands to connected minions
    """

    ttype = "rabbitmq"

    def __init__(self, opts, **kwargs):
        super().__init__(opts, **kwargs)
        self.opts = opts
        self.io_loop = (
            kwargs.get("io_loop") or salt.ext.tornado.ioloop.IOLoop.instance()
        )
        if not self.io_loop:
            raise ValueError("self.io_loop must be set")
        self._closing = False
        self._rmq_non_blocking_connection_wrapper = RMQNonBlockingConnectionWrapper(
            self.opts,
            io_loop=self.io_loop,
            transport_rabbitmq_consumer_queue_name="salt_minion_command_queue",
            transport_rabbitmq_publisher_exchange_name="salt_minion_command_exchange",
            transport_rabbitmq_consumer_exchange_name="salt_minion_command_exchange",
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # TODO: this is the time to see if we are connected, maybe use the req channel to guess?
    @salt.ext.tornado.gen.coroutine
    def connect(self, publish_port, connect_callback=None, disconnect_callback=None):
        """
        Connects minion to master.
        TODO: anything else that needs to be done for broker-based connections?
        :return:
        """

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        self._rmq_non_blocking_connection_wrapper.register_message_callback(
            callback=callback
        )


class RabbitMQReqServerChannel(salt.transport.RequestServer):
    """
    Encapsulate synchronous operations for a request channel
    """

    def __init__(self, opts):
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
        payload = self.decode_payload(payload)
        reply = yield self.message_handler(payload)
        rmq_connection_wrapper.publish_reply(
            self.encode_payload(reply), message_properties
        )


class RabbitMQPubServerChannel(salt.transport.base.PublishServer):
    """
    Encapsulate synchronous operations for a publisher channel
    """

    def __init__(self, opts):
        self.opts = opts
        self._rmq_blocking_connection_wrapper = RMQBlockingConnectionWrapper(
            opts,
            transport_rabbitmq_consumer_queue_name="salt_minion_command_queue",
            transport_rabbitmq_publisher_exchange_name="salt_minion_command_exchange",
            transport_rabbitmq_consumer_exchange_name="salt_minion_command_exchange",
        )

    def connect(self):
        return salt.ext.tornado.gen.sleep(5)  # TODO: why is this here?

    def pre_fork(self, process_manager, kwargs=None):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        """

    def publish(self, payload, **kwargs):
        """
        Publish "load" to minions. This sends the load to the RMQ broker
        process which does the actual sending to minions.

        :param dict load: A load to be sent across the wire to minions
        """

        payload = salt.payload.dumps(payload)
        message_properties = None
        if kwargs:
            message_properties = kwargs.get("message_properties", None)
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
        )
        log.info("Sent payload to rabbitmq publish daemon.")


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
        self._closing = False

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

    @salt.ext.tornado.gen.coroutine
    def send(self, message, timeout=None, tries=3, future=None, callback=None):
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

        # send
        def mark_future(msg):
            if not future.done():
                data = self.serial.loads(msg)
                future.set_result(data)

        # send message and consume reply; callback must be configured first when using amq.rabbitmq.reply-to pattern
        # See https://www.rabbitmq.com/direct-reply-to.html
        self._rmq_blocking_connection_wrapper.register_reply_callback(
            mark_future, reply_queue_name="amq.rabbitmq.reply-to"
        )

        self._rmq_blocking_connection_wrapper.publish(
            message,
            # Use a special reserved direct-rely queue. See https://www.rabbitmq.com/direct-reply-to.html
            reply_queue_name="amq.rabbitmq.reply-to",
        )

        self._rmq_blocking_connection_wrapper.start_consuming()
        yield future
