# -*- coding: utf-8 -*-
'''
A salt engine which retransmits the messages from salt event bus to another ZMQ channel.
'''

from __future__ import absolute_import, print_function, unicode_literals

import logging

import re

import salt.utils.event
import salt.utils.json
from salt.performance.payloads import message_observed, job_results_end, job_return
from salt.performance.sender import ZmqSender, JsonRenderer
from salt.performance.time_provider import TimestampProvider

log = logging.getLogger(__name__)


def start(host='127.0.0.1',
          port=9900):
    '''
    Listen to events and resend the message queue throughput statistics to the Aggregator.
    '''

    event_bus = _get_event_bus()

    log.debug("Using host=%s and port=%d for ZMQ" % (host, port))
    sender = ZmqSender(JsonRenderer(), zmq_host=host, zmq_port=port)
    processor = MessageProcessor(sender, _get_master_id())

    log.debug('ZMQ relay engine has started')

    try:
        while True:
            event = event_bus.get_event(full=True)
            if not event:
                continue

            processor.process(event)

    finally:
        sender.close()
        log.debug("ZMQ relay engine has stopped")


def _get_event_bus():
    if __opts__['__role'] == 'master':
        event_bus = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir'],
            listen=True)
    else:
        raise RuntimeError("Relay engine must run at master only")
    return event_bus


def _get_master_id():
    return __opts__['id']


class MessageProcessor(object):
    """
    The actual message processor for Relay engine
    """

    def __init__(self, sender, master_id):
        assert isinstance(sender, ZmqSender)
        self.sender = sender
        self.master_id = master_id
        super(MessageProcessor, self).__init__()

    def process(self, event):
        self._notify_message_observed(event)
        if self._is_jobcompletion(event):
            self._process_job_completion(event)
        if self._is_job_return(event):
            self._process_job_return(event)
        if self._is_performance(event):
            self._recend_performance_data(event)

    def _notify_message_observed(self, event):
        json_str = salt.utils.json.dumps(event)
        msg_length = len(json_str)

        self.sender.send(message_observed(master_id=self.master_id,
                                          msg_length=msg_length,
                                          tag=event['tag'],
                                          ts=TimestampProvider.get_now()))

    def _recend_performance_data(self, event):
        data = self._extract_data(event)
        # [KN] Let's forcibly add the current master_id (given that in raas environment there can be a number of them).
        data['meta']['master_id'] = self.master_id
        self.sender.send(data)

    def _is_performance(self, event):
        return event['tag'].startswith('perf/')

    def _process_job_completion(self, event):
        data = self._extract_data(event)

        returned_count = len(data['returned'])
        silent_count = len(data['missing'])

        jid = self._extract_jid_completion(event)
        self.sender.send(job_results_end(jid,
                                         self.master_id,
                                         TimestampProvider.get_now(),
                                         returned_count,
                                         returned_count + silent_count
                                         ))

    def _extract_jid_completion(self, event):
        tag = event['tag']
        return self._extract(tag, self._get_completion_tag_regex)

    def _is_jobcompletion(self, event):
        tag = event['tag']
        return self._match(tag, self._get_completion_tag_regex)

    def _get_completion_tag_regex(self):
        return r'^salt/job/([^/]*)/complete'

    def _extract_data(self, event):
        # [KN] Don't know exactly why the payload can have nested 'data' envelopes.
        # Since we know the structure of performance-related messages, the following algorithm is quite safe.
        e = event
        while 'data' in e:
            e = e['data']
        e.pop('_stamp', None)
        return e

    def _is_job_return(self, event):
        tag = event['tag']
        return self._match(tag, self._get_return_tag_regex)

    def _get_return_tag_regex(self):
        return r'^salt/job/(.*)/ret/.*$'

    def _extract_jid_return(self, event):
        return self._extract(event['tag'], self._get_return_tag_regex)

    def _process_job_return(self, event):
        data = self._extract_data(event)
        jid = self._extract_jid_return(event)
        minion_id = data['id']
        self.sender.send(job_return(jid, self.master_id, minion_id, TimestampProvider.get_now()))

    def _extract(self, tag, fn):
        """
        :param tag: The tag to match against the regex
        :param fn: Provides a regex which has at least 1 group
        :return: Extracted value
        """
        return self._match(tag, fn).group(1)


    def _match(self, tag, fn):
        regex = fn()
        return re.match(regex, tag)
