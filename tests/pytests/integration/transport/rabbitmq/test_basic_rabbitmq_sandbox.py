"""
Integration tests for rabbitmq transport
"""

import logging

import pytest
import pika

from tests.support.helpers import runs_on

log = logging.getLogger(__name__)

pytestmark = [
    #TODO differentiate between OS flavours and instances of docker
    pytest.mark.skip_if_binaries_missing("docker"), # MacOS has "docker desktop" with the 'docker" as cli
]

@runs_on(kernel="Darwin")
@pytest.mark.skip_if_binaries_missing("docker")
@pytest.fixture(scope="module", autouse=True)
def rabbitmq_docker_container(salt_call_cli, rabbitmq_port, rabbitmq_management_port):
    container_started = False
    try:
        ret = salt_call_cli.run(
            "state.single", "docker_image.present", name="bitnami/rabbitmq", tag="latest"
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        ret = salt_call_cli.run(
            "state.single",
            "docker_container.running",
            name="rabbitmq",
            image="bitnami/rabbitmq:latest",
            port_bindings="{}:5672,{}:15672".format(rabbitmq_port, rabbitmq_management_port),
            cap_add="IPC_LOCK",
        )

        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        container_started = True
        yield
    finally:
        if container_started:
            ret = salt_call_cli.run(
                "state.single", "docker_container.stopped", name="rabbitmq"
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True
            ret = salt_call_cli.run(
                "state.single", "docker_container.absent", name="rabbitmq"
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True

@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_send_receive():
    queue_name = 'salt_test_queue'
    message_body = 'Test!'

    # TODO: deal with credentials better
    creds = pika.PlainCredentials("user", "bitnami")

    # send
    # RMQ service may not have started inside the container
    with pika.BlockingConnection(pika.ConnectionParameters("localhost", credentials=creds)) as connection_sender:
        with connection_sender.channel() as channel_sender:
            channel_sender.queue_declare(queue=queue_name)
            #default direct exchange. See https://www.rabbitmq.com/tutorials/amqp-concepts.html
            channel_sender.basic_publish(exchange='',
                                         routing_key="salt_test_queue",
                                         body=message_body)
            log.debug(" [x] Sent {}".format(message_body))
            channel_sender.close()

        connection_sender.close()

    # receive
    with pika.BlockingConnection(pika.ConnectionParameters(host="localhost",  credentials=creds)) as connection_receiver:
        with connection_receiver.channel() as channel_receiver:
            channel_receiver.queue_declare(queue=queue_name)

            def callback(ch, method, properties, body):
                print(" [x] Received {}".format(body))
                assert body == bytes(message_body, encoding='utf-8')
                channel_receiver.stop_consuming()

            channel_receiver.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

            channel_receiver.start_consuming()
            log.debug("Done consuming")
