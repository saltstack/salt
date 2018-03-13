# -*- coding: utf-8 -*-
'''
A salt engine which retransmits the messages from salt event bus to another ZMQ channel.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import json
import logging

# Import salt libs
import re
import time
import zmq

import salt.utils.event
import salt.utils.json
from salt.performance.payloads import message_observed, job_results_end, job_return
from salt.performance.time_provider import TimestampProvider

log = logging.getLogger(__name__)


class JsonRenderer(object):
    def marshal(self, smth):
        return json.dumps(smth)


# FIXME [KN] refactor to use salt.transport.zmq instead
class ZmqSender(object):
    def __init__(self, json_renderer, zmq_host='localhost', zmq_port=9900):
        self.json_renderer = json_renderer
        log.debug("ZMQ version: {}".format(zmq.zmq_version()))

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.setsockopt(zmq.SNDBUF, 102400)
        self.socket.setsockopt(zmq.LINGER, 2000)

        self.socket.set_hwm(10240)

        zmq_address = "tcp://%s:%d" % (zmq_host, zmq_port)
        log.info("Connecting to ZMQ at address: %s" % zmq_address)

        self.socket.connect(zmq_address)
        time.sleep(2)

    def send(self, payload):
        out_str = self.json_renderer.marshal(payload)
        log.debug("Sent message: {}".format(out_str))
        self.socket.send_unicode("{} {}".format("topic", out_str))

    def close(self):
        self.socket.close()
        self.context.destroy(linger=3000)


def start(host='127.0.0.1',
          port=9900):
    '''
    Listen to events and resend the message queue throughput statistics to the Aggregator.
    '''

    if __opts__['__role'] == 'master':
        event_bus = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir'],
            listen=True)
    else:
        raise RuntimeError("Relay engine must run at master only")

    log.debug("Using host=%s and port=%d for ZMQ" % (host, port))
    sender = ZmqSender(JsonRenderer(), zmq_host=host, zmq_port=port)
    log.debug('ZMQ relay engine has started')

    try:
        while True:
            event = event_bus.get_event(full=True)
            if not event:
                continue

            jevent = salt.utils.json.dumps(event)
            sender.send(message_observed(msg_length=len(jevent), tag=event['tag'], ts=TimestampProvider.get_now()))

            if _is_jobcompletion(event):
                _process_job_completion(event, sender)

            if _is_job_return(event):
                _process_job_return(event, sender)

            if _is_performance(event):
                sender.send(_extract_data(event))

    finally:
        sender.close()
        log.debug("ZMQ relay engine has stopped")


def _is_performance(event):
    return event['tag'].startswith('perf/')


def _process_job_completion(event, sender):
    data = _extract_data(event)

    returned_count = len(data['returned'])
    silent_count = len(data['missing'])

    jid = _extract_jid_completion(event)
    sender.send(job_results_end(jid,
                                _get_master_id(),
                                TimestampProvider.get_now(),
                                returned_count,
                                returned_count + silent_count
                                ))


def _extract_jid_completion(event):
    return re.match(_get_completion_tag_regex(), event['tag']).group(1)


def _get_master_id():
    return __opts__['id']


def _is_jobcompletion(event):
    tag = event['tag']
    return re.match(_get_completion_tag_regex(), tag)


def _get_completion_tag_regex():
    return r'^salt/job/([^/]*)/complete'


def _extract_data(event):
    # [KN] Don't know exactly why the payload can have nested 'data' envelopes.
    # Since we know the structure of performance-related messages, the following algorithm is quite safe.
    e = event
    while 'data' in e:
        e = e['data']
    e.pop('_stamp', None)
    return e


def _is_job_return(event):
    tag = event['tag']
    return re.match(_get_return_tag_regex(), tag)


def _get_return_tag_regex():
    return r'^salt/job/(.*)/ret/.*$'


def _extract_jid_return(event):
    return re.match(_get_return_tag_regex(), event['tag']).group(1)


def _process_job_return(event, sender):
    data = _extract_data(event)
    jid = _extract_jid_return(event)
    minion_id = data['id']
    master_id = _get_master_id()
    sender.send(job_return(jid, master_id, minion_id, TimestampProvider.get_now()))

