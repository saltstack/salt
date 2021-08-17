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
from random import randint
from uuid import uuid4

import pika
from pika import SelectConnection
from pika.exchange_type import ExchangeType

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
from salt.exceptions import SaltException, SaltReqTimeoutError
from salt.ext import tornado

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
    def __init__(self, opts):
        self._opts = opts

        # rmq broker address
        self._host = self._opts["transport_rabbitmq_address"] if "transport_rabbitmq_address" in self._opts else "localhost"
        assert self._host

        # rmq broker credentials (TODO: support other types of auth. eventually)
        assert "transport_rabbitmq_auth" in self._opts
        creds = self._opts["transport_rabbitmq_auth"]
        self._creds = pika.PlainCredentials(creds["username"], creds["password"])


        # TODO: figure out a better way to generate common queue names that are accessible to both master and minion,
        # each possibly running on different machine
        master_port = self._opts["master_port"] if "master_port" in self._opts else self._opts["ret_port"]
        assert master_port
        assert self._opts["interface"]

        self._queue_name = "{}_{}".format(self._opts["interface"], master_port)

    @property
    def queue_name(self):
        return self._queue_name

    def __del__(self):
        try:
          if self._channel and self._channel.is_open:
             self._channel.close()
        except:
            pass

        try:
          if self._connection and self._connection.is_open:
             self._connection.close()
        except:
            pass


class RMQBlockingConnectionWrapper(RMQConnectionWrapperBase):
    """
    RMQConnection wrapper implemented that wraps a BlockingConnection.
    Declares and binds a queue to a fanout exchange for publishing messages.
    Caches connection and channel for reuse.
    TODO: implement connection recovery and error handling (see rabbitmq docs for examples).
    Not thread safe.
    """

    def __init__(self, opts):
        super(RMQBlockingConnectionWrapper, self).__init__(opts)

        self._connection = pika.BlockingConnection(pika.ConnectionParameters(host=self._host, credentials=self._creds))
        self._channel = self._connection.channel()

        # set up exchange for message broadcast
        self._fanout_exchange_name = self.queue_name
        self._channel.exchange_declare(exchange=self._fanout_exchange_name, exchange_type=ExchangeType.fanout)

    def publish(self, payload, queue_name=None, reply_queue_name=None,  auto_delete_queue=False, broadcast=True):
        """
        Publishes ``payload`` to the specified ``queue_name`` (via direct exchange), passes along optional name of the
        reply queue in message metadata. Non-blocking.
        Alternatively, broadcasts the ``payload`` to all bound queues (via fanout exchange).
        :param payload: message body
        :param queue_name: queue name
        :param reply_queue_name: optional name of the reply queue
        :param auto_delete_queue: set the type of queue to "auto_delete" (it will
        :param broadcast: whether to broadcast via fanout exchange
        :return:
        """

        publish_queue_name = queue_name if queue_name else self.queue_name

        # See https://www.rabbitmq.com/tutorials/amqp-concepts.html
        exchange = self._fanout_exchange_name if broadcast else ""

        # For the IPC pattern, set up the "reply-to" header
        properties = pika.BasicProperties(reply_to=reply_queue_name) if reply_queue_name else None

        log.debug("Sending payload to queue [{}] and exchange [{}]: {}".format(publish_queue_name, exchange, payload))

        try:
            # TODO: consider different queue types (durable, quorum, etc.)
            self._channel.queue_declare(publish_queue_name, auto_delete=auto_delete_queue)
            if broadcast:
                self._channel.queue_bind(publish_queue_name, exchange, routing_key=publish_queue_name)
            self._channel.basic_publish(exchange=exchange,
                                         routing_key=publish_queue_name,
                                         body=payload,
                                         properties=properties) # add reply queue to the properties
            log.debug("Sent payload to queue [{}] and exchange [{}]: {}".format(publish_queue_name, exchange, payload))
        except:
            log.exception("Error publishing to queue [{}] and exchange [{}]".format(publish_queue_name, exchange))
            raise

    def consume(self, queue_name=None, timeout=60):
        """
        A non-blocking consume takes the next message off the queue.
        :param queue_name:
        :param timeout:
        :return:
        """
        log.debug("Consuming payload on queue [{}]".format(queue_name))

        queue_name = queue_name if queue_name else self.queue_name
        self._channel.queue_declare(queue_name)
        (method, properties, body) = next(self._channel.consume(queue=queue_name, inactivity_timeout=timeout))
        return body

    def publish_reply(self, payload, properties):
        """
        Publishes reply ``payload`` to the reply queue. Non-blocking.
        :param payload: message body
        :param properties: payload properties/metadata
        :return:
        """
        reply_queue_name = properties.reply_to
        assert reply_queue_name

        log.debug("Sending reply payload on queue [{}]: {}".format(reply_queue_name, payload))

        # publish reply on a queue that will be deleted after consumer cancels or disconnects
        # TODO: look into queue types (durable, quorum, etc.)
        self.publish(payload, queue_name=reply_queue_name, auto_delete_queue=True)

    def consume_reply(self, callback, reply_queue_name=None, timeout=60):
        """
        Blocks until reply is received on the reply queue and processes it in a ``callback``
        :param callback:
        :param reply_queue_name:
        :param timeout
        :return:
        """
        self._channel.queue_declare(queue=reply_queue_name, auto_delete=True)

        def _callback(ch, method, properties, body):
            log.debug("Received reply on queue [{}]: {}".format(reply_queue_name, body))
            callback(body)
            log.debug("Processed callback for reply on queue [{}]".format(reply_queue_name))

            # Stop consuming so that auto_delete queue will be deleted
            # TODO: explicitly acknowledge response after processing callback instead of relying on "auto_ack"
            self._channel.stop_consuming()
            log.debug("Done consuming reply on queue [{}]".format(reply_queue_name))

        # blocking call with a callback
        log.debug("Starting consuming reply on queue [{}]".format(reply_queue_name))

        # TODO: reconsider auto_ack
        consumer_tag = self._channel.basic_consume(queue=reply_queue_name, on_message_callback=_callback, auto_ack=True)
        log.debug("Starting consuming reply on queue [{}]".format(reply_queue_name))

        self._channel.start_consuming() # a blocking call

    def blocking_consume(self, callback, timeout=None):
        """
        Blocks until message is available and process it with ``callback``
        :param callback:
        :param timeout:
        :return:
        """
        self._channel.queue_declare(queue=self.queue_name)

        def _callback(ch, method, properties, body):
            log.debug("Received on queue [{}] {}".format(self.queue_name, body))
            callback(payload=body, payload_properties=properties, rmq_connection_wrapper=self)

        # TODO: reconsider auto_ack
        self._channel.basic_consume(self.queue_name, on_message_callback=_callback, auto_ack=True)

        try:
            log.debug("Starting consuming on queue [{}]".format(self.queue_name))
            self._channel.start_consuming() # a blocking call
        except KeyboardInterrupt:
            self.stop_blocking_consume()
            self._connection.close()
        except:
            log.exception("Error consuming on queue [{}]".format(self.queue_name))
            raise

    def stop_blocking_consume(self):
        log.debug("Stopping consuming on queue [{}]".format(self.queue_name))
        self._channel.stop_consuming()


class RMQNonBlockingConnectionWrapper(RMQConnectionWrapperBase):
    """
    Async RMQConnection wrapper implemented in a Continuation-Passing style. Reuses a custom io_loop.
    Declares and binds a queue to a fanout exchange for publishing messages.
    Caches connection and channel for reuse.
    Not thread safe.
    TODO: implement connection recovery and error handling (see rabbitmq docs for examples).
    """
    def __init__(self, opts, io_loop=None, timeout=60):
        super(RMQNonBlockingConnectionWrapper, self).__init__(opts)

        self._io_loop = tornado.ioloop.IOLoop.instance() if io_loop is None else io_loop
        self._io_loop.make_current()

        self._channel = None
        self._timeout = timeout
        self._callback = None

        self._connection = SelectConnection(parameters=pika.ConnectionParameters(host=self._host, credentials=self._creds),
                                                             on_open_callback=self._on_connection_open,
                                                             on_open_error_callback=self._on_connection_error,
                                                             custom_ioloop=self._io_loop)

        # set up exchange for message broadcast
        self._fanout_exchange_name = self.queue_name

    def _on_connection_open(self, connection):
        """
        Invoked by pika when connection is opened successfully
        :param connection:
        :return:
        """
        self._channel = connection.channel(on_open_callback=self._on_channel_open)

    def _on_connection_error(self, connection_unused):
        raise Exception("Failed to connect")

    def _on_channel_open(self, channel):
        """
        Invoked by pika when channel is opened successfully
        :param channel:
        :return:
        """
        self._channel.exchange_declare(exchange=self._fanout_exchange_name, exchange_type=ExchangeType.fanout, callback=self.on_exchange_declare)

    def on_exchange_declare(self, method):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        """
        log.debug("Exchange declared: {}".format(self._fanout_exchange_name))
        self._channel.queue_declare(queue=self.queue_name, callback=self._on_queue_declared)

    def _on_queue_declared(self, method):
        """
        Invoked by pika when queue is declared successfully
        :param method:
        :return:
        """
        log.debug("Queue declared: {}".format(self._queue_name))

        self._channel.queue_bind(
            self.queue_name,
            self._fanout_exchange_name,
            routing_key=self.queue_name,
            callback=self._on_queue_bind)

    def _on_queue_bind(self, method):
        """
        Invoked by pika when queue bound successfully
        :param method:
        :return:
        """

        log.debug("Queue bound [{}]".format(self.queue_name))

        def _callback_wrapper(channel, method, properties, payload):
             if self._callback:
                log.debug("Calling message callback")
                return self._callback(payload)

        self._channel.basic_consume(self.queue_name, _callback_wrapper, auto_ack=True)

    def register_message_callback(self, callback):
        """
        Register a callback that receives message on a queue
        :param callback:
        :return:
        """
        self._callback = callback



class AsyncRabbitMQReqChannel(salt.transport.client.ReqChannel):
    """
    Encapsulate sending routines to RabbitMQ.

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
            log.debug("Initializing new AsyncRabbitMQReqChannel for %s", key)
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
            log.debug("Re-using AsyncRabbitMQReqChannel for %s", key)
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
                        args=(result.opts, self.master_uri,),
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
        log.debug(
            "Connecting the Minion to the Master URI (for the return server): %s",
            self.master_uri,
        )
        self.message_client = AsyncReqMessageClientPool(
            self.opts,
            args=(self.opts, self.master_uri,),
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
            log.debug(
                "This is not the last %s instance. Not closing yet.",
                self.__class__.__name__,
            )
            return

        log.debug("Closing %s instance", self.__class__.__name__)
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

    # pylint: disable=W1701
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

    # pylint: enable=W1701

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
            self._package_load(load), timeout=timeout, tries=tries,
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
        assert self.io_loop

        self._closing = False


        self.hexid = hashlib.sha1(
            salt.utils.stringutils.to_bytes(self.opts["id"])
        ).hexdigest()
        self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)
        self.serial = salt.payload.Serial(self.opts)
        self._rmq_non_blocking_connection_wrapper = RMQNonBlockingConnectionWrapper(self.opts, io_loop=self.io_loop)

    def close(self):
        if self._closing is True:
            return

        self._closing = True


    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701
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

        log.debug(
            "Minion already authenticated with master. Nothing else to do for broker-based transport.")

    @salt.ext.tornado.gen.coroutine
    def _decode_messages(self, messages):
        """
        Take the rmq messages, decrypt/decode them into a payload

        :param list messages: A list of messages to be decoded
        """
        messages_len = len(messages)
        # if it was one message, then its old style
        if messages_len == 1:
            payload = self.serial.loads(messages[0])
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
                log.debug("Publish received for not this minion: %s", message_target)
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
            self._rmq_non_blocking_connection_wrapper.register_message_callback(callback=None)

        @salt.ext.tornado.gen.coroutine
        def wrap_callback(messages):
            payload = yield self._decode_messages(messages)
            if payload is not None:
                callback(payload)

        self._rmq_non_blocking_connection_wrapper.register_message_callback(callback=wrap_callback)


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
        self._rmq_connection_wrapper = RMQBlockingConnectionWrapper(opts)

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
        self.payload_handler = payload_handler
        self.io_loop = io_loop


        salt.transport.mixins.auth.AESReqServerMixin.post_fork(
            self, payload_handler, io_loop
        )

        # We are starting a separate blocking thread, but we should consider using an async library instead
        threading.Thread(target=self._rmq_pika_message_handler_thread).start()
        log.debug("Pika message handling thread started")

    def _rmq_pika_message_handler_thread(self):
        """
        Block listening for events and dispatch event handlers.
        TODO: consider using async RMQNonBlockingConnectionWrapper with io_loop
        Note:
        :return:
        """

        log.debug("_rmq_pika_message_handler_thread thread starting")
        assert self.io_loop
        self.io_loop.make_current()

        rmq_connection_wrapper = RMQBlockingConnectionWrapper(self.opts)
        rmq_connection_wrapper.blocking_consume(self.handle_message)

    @salt.ext.tornado.gen.coroutine
    def handle_message(self, payload, payload_properties: pika.BasicProperties, rmq_connection_wrapper: RMQBlockingConnectionWrapper):
        """
        Handle incoming messages from underlying streams

        :param rmq_connection_wrapper:
        :param dict payload: A payload to process
        :param payload_properties: rmq-related payload metadata
        """

        try:
            payload = self.serial.loads(payload)
            payload = self._decode_payload(payload)
        except Exception as exc:  # pylint: disable=broad-except
            exc_type = type(exc).__name__
            if exc_type == "AuthenticationError":
                log.debug(
                    "Minion failed to auth to master. Since the payload is "
                    "encrypted, it is not known which minion failed to "
                    "authenticate. It is likely that this is a transient "
                    "failure due to the master rotating its public key."
                )
            else:
                log.error("Bad load from minion: %s: %s", exc_type, exc)
            rmq_connection_wrapper.publish_reply(self.serial.dumps("bad load"), payload_properties)

            raise salt.ext.tornado.gen.Return()

        # TODO helper functions to normalize payload?
        if not isinstance(payload, dict) or not isinstance(payload.get("load"), dict):
            log.error(
                "payload and load must be a dict. Payload was: %s and load was %s",
                payload,
                payload.get("load"),
            )
            rmq_connection_wrapper.publish_reply(self.serial.dumps("payload and load must be a dict"), payload_properties)
            raise salt.ext.tornado.gen.Return()

        try:
            id_ = payload["load"].get("id", "")
            if "\0" in id_:
                log.error("Payload contains an id with a null byte: %s", payload)
                rmq_connection_wrapper.publish_reply(self.serial.dumps("bad load: id contains a null byte"), payload_properties)
                raise salt.ext.tornado.gen.Return()
        except TypeError:
            log.error("Payload contains non-string id: %s", payload)
            rmq_connection_wrapper.publish_reply(self.serial.dumps("bad load: id {} is not a string".format(id_))), payload_properties
            raise salt.ext.tornado.gen.Return()

        # intercept the "_auth" commands, since the main daemon shouldn't know
        # anything about our key auth
        if payload["enc"] == "clear" and payload.get("load", {}).get("cmd") == "_auth":
            rmq_connection_wrapper.publish_reply(self.serial.dumps(self._auth(payload["load"])), payload_properties)
            raise salt.ext.tornado.gen.Return()

        # TODO: test
        try:
            # Take the payload_handler function that was registered when we created the channel
            # and call it, returning control to the caller until it completes
            ret, req_opts = yield self.payload_handler(payload)
        except Exception as e:  # pylint: disable=broad-except
            # always attempt to return an error to the minion
            rmq_connection_wrapper.publish_reply("Some exception handling minion payload", payload_properties)
            log.error("Some exception handling a payload from minion", exc_info=True)
            raise salt.ext.tornado.gen.Return()

        req_fun = req_opts.get("fun", "send")
        if req_fun == "send_clear":
            rmq_connection_wrapper.publish_reply(self.serial.dumps(ret), payload_properties)

        elif req_fun == "send":
            rmq_connection_wrapper.publish_reply(self.serial.dumps(self.crypticle.dumps(ret)), payload_properties)

        elif req_fun == "send_private":
            rmq_connection_wrapper.publish_reply(self.serial.dumps(
                    self._encrypt_private(ret, req_opts["key"], req_opts["tgt"],)
                ), payload_properties)
        else:
            log.error("Unknown req_fun %s", req_fun)
            # always attempt to return an error to the minion
            rmq_connection_wrapper.publish_reply("Server-side exception handling payload", payload_properties)
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
        log.debug(msg)
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
        self._rmq_connection_wrapper = RMQBlockingConnectionWrapper(opts)

    def connect(self):
        return salt.ext.tornado.gen.sleep(5) # TODO: why is this here?

    def pre_fork(self, process_manager, kwargs=None):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        """
        pass

    def pub_connect(self):
        """
        Do nothing, assuming RMQ broker is running
        """
        pass

    def _generate_payload(self, load):
        payload = {"enc": "aes"}
        crypticle = salt.crypt.Crypticle(
            self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
        )
        payload["load"] = crypticle.dumps(load)
        if self.opts["sign_pub_messages"]:
            master_pem_path = os.path.join(self.opts["pki_dir"], "master.pem")
            log.debug("Signing data packet")
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

            log.debug("Publish Side Match: %s", match_ids)
            # Send list of minions thru so zmq can target them
            int_payload["topic_lst"] = match_ids
        payload = self.serial.dumps(int_payload)
        return payload

    def publish(self, load):
        """
        Publish "load" to minions. This sends the load to the RMQ broker
        process which does the actual sending to minions.

        :param dict load: A load to be sent across the wire to minions
        """

        payload = self._generate_payload(load)

        log.debug(
            "Sending payload to rabbitmq publish daemon. jid=%s size=%d",
            load.get("jid", None),
            len(payload),
        )

        # send
        self._rmq_connection_wrapper.publish(payload)
        log.debug("Sent payload to rabbitmq publish daemon.")


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
        self._rmq_connection_wrapper = RMQBlockingConnectionWrapper(opts)

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

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    @salt.ext.tornado.gen.coroutine
    def _internal_send_recv(self):
        while len(self.send_queue) > 0:
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
            message_correlation_id = uuid4().hex # TODO: optimize this to use a combination of hostname/port
            self._rmq_connection_wrapper.publish(message, reply_queue_name=message_correlation_id)
            self._rmq_connection_wrapper.consume_reply(mark_future, reply_queue_name=message_correlation_id)

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
                log.debug(
                    "SaltReqTimeoutError, retrying. (%s/%s)",
                    future.attempts,
                    future.tries,
                )
                self.send(
                    message, timeout=future.timeout, tries=future.tries, future=future,
                )

            else:
                future.set_exception(SaltReqTimeoutError("Message timed out"))

    def send(self, message, timeout=None, tries=3, future=None, callback=None, raw=False):
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

        if len(self.send_queue) == 0:
            self.io_loop.spawn_callback(self._internal_send_recv)

        self.send_queue.append(message)

        return future

