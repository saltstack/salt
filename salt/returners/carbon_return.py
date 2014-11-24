# -*- coding: utf-8 -*-
'''
Take data from salt and "return" it into a carbon receiver

Add the following configuration to the minion configuration files::

    carbon.host: <server ip address>
    carbon.port: 2003

Errors when trying to convert data to numbers may be ignored by setting
``carbon.skip_on_error`` to `True`::

    carbon.skip_on_error: True

By default, data will be sent to carbon using the plaintext protocol. To use
the pickle protocol, set ``carbon.mode`` to ``pickle``::

    carbon.mode: pickle

Carbon settings may also be configured as::

    carbon:
        host: <server IP or hostname>
        port: <carbon port>
        skip_on_error: True
        mode: (pickle|text)

  To use the carbon returner, append '--return carbon' to the salt command. ex:

    salt '*' test.ping --return carbon
'''


# Import python libs
from contextlib import contextmanager
import collections
import logging
import cPickle as pickle
import socket
import struct
import time

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'carbon'


def __virtual__():
    return __virtualname__


@contextmanager
def _carbon(host, port):
    '''
    Context manager to ensure the clean creation and destruction of a socket.

    host
        The IP or hostname of the carbon server
    port
        The port that carbon is listening on
    '''
    carbon_sock = None

    try:
        carbon_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM,
                                    socket.IPPROTO_TCP)

        carbon_sock.connect((host, port))
    except socket.error as err:
        log.error('Error connecting to {0}:{1}, {2}'.format(host, port, err))
        raise
    else:
        log.debug('Connected to carbon')
        yield carbon_sock
    finally:
        if carbon_sock is not None:
            # Shut down and close socket
            log.debug('Destroying carbon socket')

            carbon_sock.shutdown(socket.SHUT_RDWR)
            carbon_sock.close()


def _send_picklemetrics(metrics):
    '''
    Format metrics for the carbon pickle protocol
    '''

    metrics = [(metric_name, (timestamp, value))
               for (metric_name, value, timestamp) in metrics]

    data = pickle.dumps(metrics, -1)
    payload = struct.pack('!L', len(data)) + data

    return payload


def _send_textmetrics(metrics):
    '''
    Format metrics for the carbon plaintext protocol
    '''

    data = [' '.join(map(str, metric)) for metric in metrics] + ['']

    return '\n'.join(data)


def _walk(path, value, metrics, timestamp, skip):
    '''
    Recursively include metrics from *value*.

    path
        The dot-separated path of the metric.
    value
        A dictionary or value from a dictionary. If a dictionary, ``_walk``
        will be called again with the each key/value pair as a new set of
        metrics.
    metrics
        The list of metrics that will be sent to carbon, formatted as::

            (path, value, timestamp)
    skip
        Whether or not to skip metrics when there's an error casting the value
        to a float. Defaults to `False`.
    '''

    if isinstance(value, collections.Mapping):
        for key, val in value.items():
            _walk('{0}.{1}'.format(path, key), val, metrics, timestamp, skip)
    else:
        try:
            val = float(value)
            metrics.append((path, val, timestamp))
        except (TypeError, ValueError):
            msg = 'Error in carbon returner, when trying to convert metric: ' \
                  '{0}, with val: {1}'.format(path, value)
            if skip:
                log.debug(msg)
            else:
                log.info(msg)
                raise


def returner(ret):
    '''
    Return data to a remote carbon server using the text metric protocol

    Each metric will look like::

        [module].[function].[minion_id].[metric path [...]].[metric name]

    '''

    if 'config.option' in __salt__:
        cfg = __salt__['config.option']
        c_cfg = cfg('carbon', {})

        host = c_cfg.get('host', cfg('carbon.host', None))
        port = c_cfg.get('port', cfg('carbon.port', None))
        skip = c_cfg.get('skip_on_error', cfg('carbon.skip_on_error', False))
        mode = c_cfg.get('mode', cfg('carbon.mode', 'text')).lower()
    else:
        cfg = __opts__
        host = cfg.get('cabon.host', None)
        port = cfg.get('cabon.port', None)
        skip = cfg.get('carbon.skip_on_error', False)
        mode = cfg.get('carbon.mode', 'text').lower()

    log.debug('Carbon minion configured with host: {0}:{1}'.format(host, port))
    log.debug('Using carbon protocol: {0}'.format(mode))

    if not (host and port):
        log.error('Host or port not defined')
        return

    # TODO: possible to use time return from salt job to be slightly more precise?
    # convert the jid to unix timestamp?
    # {'fun': 'test.version', 'jid': '20130113193949451054', 'return': '0.11.0', 'id': 'salt'}
    timestamp = int(time.time())

    saltdata = ret['return']
    metric_base = ret['fun']
    handler = _send_picklemetrics if mode == 'pickle' else _send_textmetrics

    # Strip the hostname from the carbon base if we are returning from virt
    # module since then we will get stable metric bases even if the VM is
    # migrate from host to host
    if not metric_base.startswith('virt.'):
        metric_base += '.' + ret['id'].replace('.', '_')

    metrics = []
    _walk(metric_base, saltdata, metrics, timestamp, skip)
    data = handler(metrics)

    with _carbon(host, port) as sock:
        total_sent_bytes = 0
        while total_sent_bytes < len(data):
            sent_bytes = sock.send(data[total_sent_bytes:])
            if sent_bytes == 0:
                log.error('Bytes sent 0, Connection reset?')
                return

            log.debug('Sent {0} bytes to carbon'.format(sent_bytes))
            total_sent_bytes += sent_bytes


def prep_jid(nocache, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.gen_jid()
