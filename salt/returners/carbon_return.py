# -*- coding: utf-8 -*-
'''
Take data from salt and "return" it into a carbon receiver

Add the following configuration to your minion configuration files::

    carbon.host: <server ip address>
    carbon.port: 2003

If you wish to ignore errors when trying to convert data to numbers, you may
optionally specify in your minion configuration or the pillar::

    carbon.skip_on_error: True

'''

# Import python libs
import pickle
import socket
import logging
import time
import struct
import collections

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'carbon'


def __virtual__():
    return __virtualname__


def _send_picklemetrics(metrics, carbon_sock):
    ''' Uses pickle protocol to send data '''

    metrics = [(metric_name, (timestamp, value))
               for (metric_name, timestamp, value) in metrics]

    data = pickle.dumps(metrics, protocol=-1)
    struct_format = '!I'
    data = struct.pack(struct_format, len(data)) + data
    total_sent_bytes = 0
    while total_sent_bytes < len(data):
        sent_bytes = carbon_sock.send(data[total_sent_bytes:])
        if sent_bytes == 0:
            log.error('Bytes sent 0, Connection reset?')
            return
        total_sent_bytes += sent_bytes
        logging.debug('Sent {0} bytes to carbon'.format(sent_bytes))


def _walk(path, value, metrics, timestamp, skip):
    """
    Recursively include metrics from *value*.

    *path*
        The dot-separated path of the metric.
    *value*
        A dictionary or value from a dictionary. If a dictionary, ``_walk``
        will be called again with the each key/value pair as a new set of
        metrics.
    *metrics*
        The list of metrics that will be sent to carbon, formatted as::

            (path, value, timestamp)
    *skip*
        Whether or not to skip metrics when there's an error casting the value
        to a float. Defaults to `False`.

    """

    if isinstance(value, collections.Mapping):
        for key, val in value.items():
            _walk('{0}.{1}'.format(path, key), val, metrics, timestamp, skip)
    else:
        try:
            val = float(value)
            metrics.append((path, val, timestamp))
        except (TypeError, ValueError):
            log.error('Error in carbon returner, when trying to'
                      'convert metric:{0}, with val:{1}'.format(path, value))

            if not skip:
                raise


def returner(ret):
    '''
    Return data to a remote carbon server using the text metric protocol

    Each metric will look like::

        [module].[function].[minion_id].[metric path [...]].[metric name]

    '''

    host = __salt__['config.option']('carbon.host')
    port = __salt__['config.option']('carbon.port')
    skip = __salt__['config.option']('carbon.skip_on_error', False)

    log.debug('Carbon minion configured with host: {0}:{1}'.format(host, port))
    if not (host and port):
        log.error('Host or port not defined')
        return

    try:
        carbon_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        carbon_sock.connect((host, port))
    except socket.error as e:
        log.error('Error connecting to {0}:{1}, {2}'.format(host, port, e))
        return

    # TODO: possible to use time return from salt job to be slightly more precise?
    # convert the jid to unix timestamp?
    # {'fun': 'test.version', 'jid': '20130113193949451054', 'return': '0.11.0', 'id': 'salt'}
    timestamp = int(time.time())

    saltdata = ret['return']
    metric_base = ret['fun']

    # Strip the hostname from the carbon base if we are returning from virt
    # module since then we will get stable metric bases even if the VM is
    # migrate from host to host
    if not metric_base.startswith('virt.'):
        metric_base += '.' + ret['id'].replace('.', '_')
    metrics = []

    _walk(metric_base, saltdata, metrics, timestamp, skip)

    def _send_textmetrics(metrics):
        ''' Use text protorocol to send metric over socket '''
        data = []
        for metric in metrics:
            metric = '{0} {1} {2}'.format(metric[0], metric[1], metric[2])
            data.append(metric)
        data = '\n'.join(data) + '\n'
        total_sent_bytes = 0
        while total_sent_bytes < len(data):
            sent_bytes = carbon_sock.send(data[total_sent_bytes:])
            if sent_bytes == 0:
                log.error('Bytes sent 0, Connection reset?')
                return
            log.debug('Sent {0} bytes to carbon'.format(sent_bytes))

            total_sent_bytes += sent_bytes

    # Send metrics
    _send_textmetrics(metrics)

    # Shut down and close socket
    carbon_sock.shutdown(socket.SHUT_RDWR)
    carbon_sock.close()
