"""
SQS transport classes
"""
import base64
import hashlib
import json
import logging
import os
import signal
import sys
import threading
from typing import Any, Callable

# pylint: disable=3rd-party-module-not-gated
import boto3
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
from salt.exceptions import SaltReqTimeoutError

# pylint: enable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


class SQSWrapperBase:
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

        self._sqs_client = None
        self._sns_client = None
        self._consumer_queue_name_to_url_map = {}
        self._sns_publisher_topic = None

    def _get_queue_url_from_queue_name(self, queue_name=None):
        queue_url = self._consumer_queue_name_to_url_map.get(queue_name)
        if not queue_url:
            response = self._sqs_client.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]
            if not queue_url:
                raise ValueError("queue_url must be set")
            self._consumer_queue_name_to_url_map[queue_name] = queue_url

        return queue_url

    def _validate_set_broker_topology(self, opts, **kwargs):
        """
        Validate broker topology and set private variables. For example:
            {
                "transport: sqs",
                "transport_sqs_create_topology_ondemand": "True",
                "transport_sqs_publisher_exchange_name":" "exchange_to_publish_messages",
                "transport_sqs_consumer_exchange_name": "exchange_to_bind_queue_to_receive_messages_from",
                "transport_sqs_consumer_queue_name": "queue_to_consume_messages_from",

                "transport_sqs_consumer_queue_declare_arguments":  { "DelaySeconds": "0", "VisibilityTimeout": "60" },
                "transport_sqs_publisher_exchange_declare_arguments": ""
                "transport_sqs_consumer_exchange_declare_arguments": ""
            }
        """

        self._url = (
            opts["transport_sqs_url"]
            if "transport_sqs_url" in opts
            else "localhost:9092"  # FIXME; This is N/A for SQS
        )
        if not self._url:
            raise ValueError("SQS URL must be set")

        # optionally create the RMQ topology if instructed
        # some use cases require topology creation out-of-band with permissions
        # rmq consumer queue arguments
        create_topology_key = "transport_sqs_create_topology_ondemand"
        self._create_topology_ondemand = (
            kwargs.get(create_topology_key, False)
            if create_topology_key in kwargs
            else opts.get(create_topology_key, False)
        )

        # publisher exchange name
        publisher_exchange_name_key = "transport_sqs_publisher_exchange_name"
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
        consumer_exchange_name_key = "transport_sqs_consumer_exchange_name"
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
        consumer_queue_name_key = "transport_sqs_consumer_queue_name"
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
        self._consumer_queue_name = self._consumer_queue_name.replace(
            "-", "_"
        )  # PR - do this better
        self._consumer_queue_name = self._consumer_queue_name.replace(
            ".", "_"
        )  # PR - do this better
        # self._consumer_queue_name = self._consumer_queue_name[:74]
        self._consumer_queue_name_reply = self._consumer_queue_name + "_reply"
        if len(self._consumer_queue_name_reply) > 80:
            raise ValueError("Queue name too long")

        # rmq consumer exchange arguments when declaring exchanges
        consumer_exchange_declare_arguments_key = (
            "transport_sqs_consumer_exchange_declare_arguments"
        )
        self._consumer_exchange_declare_arguments = (
            kwargs.get(consumer_exchange_declare_arguments_key)
            if consumer_exchange_declare_arguments_key in kwargs
            else opts.get(consumer_exchange_declare_arguments_key, None)
        )

        # rmq consumer queue arguments when declaring queues
        consumer_queue_declare_arguments_key = (
            "transport_sqs_consumer_queue_declare_arguments"
        )
        self._consumer_queue_declare_arguments = (
            kwargs.get(consumer_queue_declare_arguments_key)
            if consumer_queue_declare_arguments_key in kwargs
            else opts.get(consumer_queue_declare_arguments_key, None)
        )

        # rmq publisher exchange arguments when declaring exchanges
        publisher_exchange_declare_arguments_key = (
            "transport_sqs_publisher_exchange_declare_arguments"
        )
        self._publisher_exchange_declare_arguments = (
            kwargs.get(publisher_exchange_declare_arguments_key)
            if publisher_exchange_declare_arguments_key in kwargs
            else opts.get(publisher_exchange_declare_arguments_key, None)
        )

    @property
    def queue_name(self):
        return self._consumer_queue_name

    def create_topology(self):
        """
        Create queues(s), topics, subscriptions
        :return:
        """
        if not self._sqs_client or not self._sns_client:
            self.log.debug("Creating topology...")
            self._sns_client = boto3.client("sns", region_name="us-east-2")  # FIXME: hard-coded region
            self._sqs_client = boto3.client("sqs", region_name="us-east-2")  # FIXME: hard-coded region

            # consumer queue
            response = self.sqs_create_consumer_queue(
                queue_name=self._consumer_queue_name
            )
            self._consumer_queue_name_to_url_map[self._consumer_queue_name] = response[
                "QueueUrl"
            ]
            self._sqs_client.set_queue_attributes(
                QueueUrl=self._consumer_queue_name_to_url_map[
                    self._consumer_queue_name
                ],
                Attributes={
                    "MessageRetentionPeriod": "60",
                    "ReceiveMessageWaitTimeSeconds": "20",
                },
            )
            consumer_queue_attrs = self._sqs_client.get_queue_attributes(
                QueueUrl=response["QueueUrl"], AttributeNames=["QueueArn"]
            )

            # reply queue
            response = self.sqs_create_consumer_queue(
                queue_name=self._consumer_queue_name_reply
            )
            self._consumer_queue_name_to_url_map[
                self._consumer_queue_name_reply
            ] = response["QueueUrl"]
            self._sqs_client.set_queue_attributes(
                QueueUrl=self._consumer_queue_name_to_url_map[
                    self._consumer_queue_name_reply
                ],
                Attributes={
                    "MessageRetentionPeriod": "60",
                    "ReceiveMessageWaitTimeSeconds": "20",
                },
            )

            self._sns_publisher_topic = self.sns_create_publisher_topic()
            self._sns_consumer_topic = self.sns_create_consumer_topic()

            if self._sns_consumer_topic:
                # create a subscription so that we can publish topic -> queue
                self._sns_subscriptionArn = self._sns_client.subscribe(
                    TopicArn=self._sns_consumer_topic["TopicArn"],
                    Protocol="sqs",
                    Endpoint=consumer_queue_attrs["Attributes"]["QueueArn"],
                    ReturnSubscriptionArn=True,
                )["SubscriptionArn"]

                # this is the policy that is auto-created when subscribing a queue to a topic via AWS console
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Sid": self._sns_subscriptionArn,
                            "Principal": {"AWS": "*"},
                            "Action": "SQS:SendMessage",
                            "Resource": consumer_queue_attrs["Attributes"]["QueueArn"],
                            "Condition": {
                                "ArnLike": {
                                    "aws:SourceArn": self._sns_consumer_topic[
                                        "TopicArn"
                                    ]
                                }
                            },
                        }
                    ],
                }

                self._sqs_client.set_queue_attributes(
                    QueueUrl=self._consumer_queue_name_to_url_map[
                        self._consumer_queue_name
                    ],
                    Attributes={
                        "Policy": json.dumps(policy),
                    },
                )

    def sqs_create_consumer_queue(self, queue_name=None):
        if not self._sqs_client:
            raise ValueError("SQS client must be set")
        self.log.debug(f"Creating queue with name {self.queue_name}")

        if not self._consumer_queue_declare_arguments:
            raise ValueError("consumer queue arguments must be set")

        response = self._sqs_client.create_queue(
            QueueName=queue_name
            if queue_name
            else self.queue_name,  # self._opts["id"].replace(".", "_"),  # PR - do this better
            Attributes=self._consumer_queue_declare_arguments,
        )
        return response

    def sns_create_consumer_topic(self):
        if not self._sns_client:
            raise ValueError("SNS client must be set")
        if self._consumer_exchange_name:
            topic = self._sns_client.create_topic(Name=self._consumer_exchange_name)
            log.debug(f"Created consumer topic {self._consumer_exchange_name}")
            return topic

    def sns_create_publisher_topic(self):
        if not self._sns_client:
            raise ValueError("SNS client must be set")
        if self._publisher_exchange_name:
            topic = self._sns_client.create_topic(Name=self._publisher_exchange_name)
            log.debug(f"Created publisher topic {self._publisher_exchange_name}")
            return topic

    def sns_publish(self, payload, optional_reply_queue_name=None, correlation_id=None):
        """
        publish to a topic
        :param payload:
        :param optional_reply_queue_name:
        :param correlation_id:
        :return:
        """
        if not self._sns_client:
            raise ValueError("SNS client must be set")
        utf8_message = base64.b64encode(payload).decode("UTF-8")
        self.log.debug(
            "SNS Publish: raw: [{}] - encoded as UTF-8: [{}]".format(
                payload, utf8_message
            )
        )
        attrs = (
            {
                "reply_queue_name": {
                    "DataType": "String",
                    "StringValue": optional_reply_queue_name,
                },
            }
            if optional_reply_queue_name
            else {}
        )

        if correlation_id:
            attrs["correlation_id"] = {
                "DataType": "String",
                "StringValue": correlation_id,
            }
        if not self._sns_publisher_topic:
            raise ValueError("SNS topic must be set")

        response = self._sns_client.publish(
            TopicArn=self._sns_publisher_topic["TopicArn"],
            Message=utf8_message,
            MessageAttributes=attrs,
        )
        message_id = response["MessageId"]
        return message_id

    def sqs_publish(
        self,
        payload,
        queue_name=None,
        optional_reply_queue_name=None,
        correlation_id=None,
    ):
        """
        publish to a queue
        :param payload:
        :param queue_name:
        :param optional_reply_queue_name:
        :param correlation_id:
        :return:
        """

        if not self._sqs_client:
            raise ValueError("SQS client must be set")

        queue_url = self._get_queue_url_from_queue_name(queue_name)
        if not queue_url:
            raise ValueError("queue URL must be set")

        utf8_message = base64.b64encode(payload).decode("UTF-8")
        self.log.debug(
            "SQS Publish: raw: [{}] - encoded as UTF-8: [{}]".format(
                payload, utf8_message
            )
        )
        attrs = (
            {
                "reply_queue_name": {
                    "DataType": "String",
                    "StringValue": optional_reply_queue_name,
                },
            }
            if optional_reply_queue_name
            else {}
        )

        if correlation_id:
            attrs["correlation_id"] = {
                "DataType": "String",
                "StringValue": correlation_id if correlation_id else "",
            }

        self.log.debug(f"SQS send_message: {utf8_message}")
        res = self._sqs_client.send_message(
            QueueUrl=queue_url, MessageBody=utf8_message, MessageAttributes=attrs
        )

    def sqs_consume(
        self, queue_name=None, on_message_callback=None, timeout=20, batch_size=10
    ):

        message_ids = []
        queue_url = self._get_queue_url_from_queue_name(queue_name)
        if not queue_url:
            raise ValueError("queue URL must be set")

        response = self._sqs_client.receive_message(
            QueueUrl=queue_url,
            AttributeNames=["SentTimestamp"],
            MaxNumberOfMessages=batch_size,
            MessageAttributeNames=["All"],
            VisibilityTimeout=60,
            WaitTimeSeconds=timeout,
        )

        if "Messages" in response:
            import json

            try:
                for i, msg in enumerate(response["Messages"]):
                    if "TopicArn" in response["Messages"][i]["Body"]:
                        # received via SNS
                        raw_message = json.loads(response["Messages"][i]["Body"])[
                            "Message"
                        ]
                    else:
                        # received via SQS
                        raw_message = response["Messages"][i]["Body"]
                    payload = base64.b64decode(raw_message.encode())
                    self.log.debug(
                        "SQS Receive: raw - [{}]; decoded as binary: [{}]".format(
                            raw_message, payload
                        )
                    )

                    on_message_callback(payload, response)
                    message_ids.append(
                        {
                            "Id": response["Messages"][i]["MessageId"],
                            "ReceiptHandle": response["Messages"][i]["ReceiptHandle"],
                        }
                    )
            finally:
                # ack the message by deleting them after processing
                self._sqs_client.delete_message_batch(
                    QueueUrl=queue_url, Entries=message_ids
                )

        return len(message_ids)

    def sqs_parse_message(self, response):
        payload = None
        attributes = None
        if response and "Messages" in response:
            if "TopicArn" in response["Messages"][0]["Body"]:
                import json

                json_response = json.loads(response["Messages"][0]["Body"])
                raw_message = json_response["Message"]
                attributes = json_response["MessageAttributes"]
            else:
                raw_message = response["Messages"][0]["Body"]
                attributes = response["Messages"][0]["MessageAttributes"]

            payload = base64.b64decode(raw_message.encode())
        return (payload, attributes)

    def _mark_future_complete(self, future, exception=None):
        if future and not future.done():
            if exception:
                future.set_exception(exception)
            else:
                future.set_result(self._connection)


class SQSNonBlockingChannelWrapper(SQSWrapperBase):
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
        self._channels = {}

    def _get_channel(self):
        chan = self._channels.get(threading.get_ident())
        return chan

    @salt.ext.tornado.gen.coroutine
    def connect(self, message_callback=None):

        if self._get_channel() and self._get_channel().is_open:
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
        self.log.debug("Establishing connection...")
        self.create_topology()
        self._mark_future_complete(self._connection_future)

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
    def start_consuming(self, callback: Callable[[Any], None], future=None):
        """
        Set up a consumer on configured queue with provided ```callback``` and return a future that is
        complete when consumer is set up
        :param future:
        :param callback: callback to call when message is received on queue
        :return: a future that is complete when consumer is set up
        """

        self._message_callback = callback

        def _on_message_callback_wrapper(payload, properties):
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

        while True:
            # this loop is blocking because we are using a sync/blocking boto3 library
            # we need to sleep to unblock the io_loop
            self.log.debug("Starting basic_consume on queue [%s]", self.queue_name)
            count = self.sqs_consume(
                queue_name=self.queue_name,
                on_message_callback=_on_message_callback_wrapper,
            )
            if count < 10:  # fixme, define constant
                yield salt.ext.tornado.gen.sleep(0.5)  #

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

        def _on_message_callback(body, properties):
            self.log.debug(
                "Received reply on queue [%s]: %s. Reply payload properties: %s",
                reply_queue_name,
                body,
                properties,
            )

            payload, attrs = self.sqs_parse_message(properties)
            corr_id = attrs["correlation_id"]["StringValue"]
            callback(payload, corr_id)  # correlation_id
            self.log.debug(
                "Processed callback for reply on queue [%s]", reply_queue_name
            )

        reply_queue_name = reply_queue_name or self._consumer_queue_name_reply
        self.log.debug("Starting basic_consume reply on queue [%s]", reply_queue_name)

        try:
            response = self.sqs_consume(
                queue_name=reply_queue_name,
                on_message_callback=_on_message_callback,
            )
            self._mark_future_complete(future)
        except ValueError as e:
            # this could happen when retrying to send the request multiple times and the retry loop will end up here
            # see ```timeout_message``` for reference
            future.set_exception(e)

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
            None,
        )

        try:
            if routing_key:
                self.sqs_publish(
                    payload,
                    queue_name=routing_key,
                    optional_reply_queue_name=reply_queue_name,
                    correlation_id=correlation_id,
                )
            else:
                self.sns_publish(
                    payload,
                    optional_reply_queue_name=reply_queue_name,
                    correlation_id=correlation_id,
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

        routing_key = None
        correlation_id = None
        if optional_transport_args:
            message_properties = optional_transport_args.get("message_properties", None)
            _, attrs = self.sqs_parse_message(message_properties)
            routing_key = attrs["reply_queue_name"]["Value"]
            correlation_id = attrs["correlation_id"]["Value"]

        if not routing_key:
            raise ValueError("reply_queue_name must be set")

        self.log.debug(
            "MESSAGE - Sending reply payload to direct exchange with routing key [%s]: %s. Payload properties: %s",
            routing_key,
            salt.payload.loads(payload),
            optional_transport_args,
        )

        # publish reply on a queue
        self.sqs_publish(payload, queue_name=routing_key, correlation_id=correlation_id)


class SQSRequestClient(salt.transport.base.RequestClient):
    ttype = "sqs"

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


class SQSPubClient(salt.transport.base.PublishClient):
    """
    A transport channel backed by AWS SQS for a Salt Publisher to use to
    publish commands to connected minions.
    Typically, this class is instantiated by a minion
    """

    def __init__(self, opts, io_loop, **kwargs):
        super().__init__(opts, io_loop, **kwargs)
        self.log = logging.getLogger(self.__class__.__name__)
        self.opts = opts
        self.ttype = "sqs"
        self.io_loop = io_loop
        if not self.io_loop:
            raise ValueError("self.io_loop must be set")

        self._closing = False

        self.hexid = hashlib.sha1(
            salt.utils.stringutils.to_bytes(self.opts["id"])
        ).hexdigest()
        self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)
        self.serial = salt.payload.Serial(self.opts)
        self._sqs_non_blocking_channel_wrapper = SQSNonBlockingChannelWrapper(
            self.opts,
            io_loop=self.io_loop,
            log=self.log,
        )

    def close(self):
        if self._closing is True:
            return
        self._closing = True
        self._sqs_non_blocking_channel_wrapper.close()

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
        yield self._sqs_non_blocking_channel_wrapper.connect()

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
                    "Invalid number of messages ({}) in sqs pub"
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

            self._sqs_non_blocking_channel_wrapper.start_consuming(wrap_callback)


class SQSReqServer(salt.transport.base.DaemonizedRequestServer):
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
        self._sqs_nonblocking_channel_wrapper = SQSNonBlockingChannelWrapper(
            self.opts, io_loop=io_loop, log=self.log
        )

        # PR - FIXME. Consider moving the connect() call into a coroutine to that we can yield it
        self._sqs_nonblocking_channel_wrapper.connect()
        self._sqs_nonblocking_channel_wrapper.start_consuming(self.handle_message)

    @salt.ext.tornado.gen.coroutine
    def handle_message(
        self, payload, **optional_transport_args
    ):  # message_properties: pika.BasicProperties
        payload = self.decode_payload(payload)
        reply = yield self.payload_handler(payload, **optional_transport_args)
        yield self._sqs_nonblocking_channel_wrapper.publish_reply(
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


class SQSPublishServer(salt.transport.base.DaemonizedPublishServer):
    """
    Encapsulate synchronous operations for a publisher channel.
    Typically, this class is instantiated by a master
    """

    def __init__(self, opts):
        super().__init__()
        self.log = logging.getLogger(self.__class__.__name__)
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?

        self._sqs_non_blocking_channel_wrapper = None
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
        **kwargs,
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
        self._sqs_non_blocking_channel_wrapper = SQSNonBlockingChannelWrapper(
            self.opts, log=self.log, io_loop=io_loop
        )

        self._sqs_non_blocking_channel_wrapper.connect()

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
            "Sending payload to sqs broker. jid=%s size=%d",
            payload.get("jid", None),
            len(payload_serialized),
        )

        ret = yield self._sqs_non_blocking_channel_wrapper.connect()
        self._sqs_non_blocking_channel_wrapper.publish(
            payload_serialized,
        )
        self.log.debug("Sent payload to sqs broker.")

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
        self._sqs_non_blocking_channel_wrapper.close()

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
            self._sqs_non_blocking_channel_wrapper = SQSNonBlockingChannelWrapper(
                self.opts,
                io_loop=self.io_loop,
                log=self.log,
                transport_sqs_publisher_exchange_name=self.opts[
                    "transport_sqs_consumer_exchange_name"
                ],
                transport_sqs_consumer_exchange_name=None,
            )
        else:
            self._sqs_non_blocking_channel_wrapper = SQSNonBlockingChannelWrapper(
                self.opts, io_loop=self.io_loop, log=self.log
            )

        self.serial = salt.payload.Serial(self.opts)

        # mapping of str(hash(message)) -> future
        self.send_future_map = {}

        self.send_timeout_map = {}  # message -> timeout
        self._closing = False

    # TODO: timeout all in-flight sessions, or error
    def close(self):
        try:
            if self._closing:
                return
            self._sqs_non_blocking_channel_wrapper.close()
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
        yield self._sqs_non_blocking_channel_wrapper.connect()

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

        yield self._sqs_non_blocking_channel_wrapper.connect()

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

        def mark_reply_future(reply_msg, corr_id):
            # reference the mutable map in this closure so that we complete the correct future,
            # as this callback can be called multiple times for multiple invocations of the outer send() function
            future = self.send_future_map.get(corr_id)
            if future and not future.done():
                # future may be None if there is a race condition between ```mark_reply_future`` and ```timeout_message```
                data = salt.payload.loads(reply_msg)
                future.set_result(data)
                self.send_future_map.pop(corr_id)

        yield self._sqs_non_blocking_channel_wrapper.publish(
            message,
            reply_queue_name=self._sqs_non_blocking_channel_wrapper.queue_name
            + "_reply",
            correlation_id=correlation_id,
        )

        consumer_tag = yield self._sqs_non_blocking_channel_wrapper.consume_reply(
            mark_reply_future
        )

        recv = yield reply_future
        raise salt.ext.tornado.gen.Return(recv)
