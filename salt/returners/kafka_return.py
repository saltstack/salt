# -*- coding: utf-8 -*-

'''
Return data to a Kafka topic

:maintainer: Christer Edwards (christer.edwards@gmail.com)
:maturity: 0.1
:depends: kafka-python
:platform: all

To enable this returner install kafka-python and enable the following settings
in the minion config:

    returner.kafka.hostnames:
      - "server1"
      - "server2"
      - "server3"

    returner.kafka.topic: 'topic'

To use the kafka returner, append '--return kafka' to the Salt command, eg;

    salt '*' test.ping --return kafka

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import salt.utils.json

# Import third-party libs
try:
    from kafka import KafkaClient, SimpleProducer
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False

log = logging.getLogger(__name__)

__virtualname__ = 'kafka'


def __virtual__():
    if not HAS_KAFKA:
        return False, 'Could not import kafka returner; kafka-python is not installed.'
    return __virtualname__


def _get_conn(ret=None):
    '''
    Return a kafka connection
    '''
    if __salt__['config.option']('returner.kafka.hostnames'):
        hostnames = __salt__['config.option']('returner.kafka.hostnames')
        return KafkaClient(hostnames)
    else:
        log.error('Unable to find kafka returner config option: hostnames')


def _close_conn(conn):
    '''
    Close the kafka connection
    '''
    conn.close()


def returner(ret):
    '''
    Return information to a Kafka server
    '''
    if __salt__['config.option']('returner.kafka.topic'):
        topic = __salt__['config.option']('returner.kafka.topic')

        conn = _get_conn(ret)
        producer = SimpleProducer(conn)
        producer.send_messages(topic, salt.utils.json.dumps(ret))

        _close_conn(conn)
    else:
        log.error('Unable to find kafka returner config option: topic')
