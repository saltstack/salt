# -*- coding: utf-8 -*-
'''
Salt returner to return highstate stats to librato

To enable this returner the minion will need the librato
client importable on the python path and the following
values configured in the minion or master config.

The librato python client can be found at:
https://github.com/librato/python-librato

.. code-block:: yaml

    librato.email: example@librato.com
    librato.api_token: abc12345def

This return supports multi-dimension metrics for librato. To enable
support for more metrics, the tags JSON object can be modified to include
other tags.

Adding EC2 Tags example:
If ec2_tags:region were desired within the tags for multi-dimension. The tags
could be modified to include the ec2 tags. Multiple dimensions are added simply
by adding more tags to the submission.

.. code-block:: python

    pillar_data = __salt__['pillar.raw']()
    q.add(metric.name, value, tags={'Name': ret['id'],'Region': pillar_data['ec2_tags']['Name']})

'''

# Import python libs
from __future__ import absolute_import, print_function
import logging

# Import Salt libs
import salt.utils
import salt.utils.jid
import salt.returners

# Import third party libs
try:
    import librato
    HAS_LIBRATO = True
except ImportError:
    HAS_LIBRATO = False

# Define the module's Virtual Name
__virtualname__ = 'librato'

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_LIBRATO:
        log.error("Could not import librato module.")
        return False, 'Could not import librato module; ' \
            'librato python client is not installed.'
    else:
        log.debug("Librato Module loaded.")
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the librato options from salt.
    '''
    attrs = {'email': 'email',
             'api_token': 'api_token',
             'api_url': 'api_url'
             }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)

    _options['api_url'] = _options.get('api_url', 'metrics-api.librato.com')

    log.debug("Retrieved Librato options: {0}".format(_options))
    return _options


def _get_librato(ret=None):
    '''
    Return a librato connection object.
    '''
    _options = _get_options(ret)

    conn = librato.connect(
        _options.get('email'),
        _options.get('api_token'),
        sanitizer=librato.sanitize_metric_name,
        hostname=_options.get('api_url'))
    log.info("Connected to librato.")
    return conn


def _calculate_runtimes(states):
    results = {
        'runtime': 0.00,
        'num_failed_states': 0,
        'num_passed_states': 0
    }

    for state, resultset in states.items():
        if isinstance(resultset, dict) and 'duration' in resultset:
            # Count the pass vs failures
            if resultset['result']:
                results['num_passed_states'] += 1
            else:
                results['num_failed_states'] += 1

            # Count durations
            results['runtime'] += resultset['duration']

    log.debug("Parsed state metrics: {0}".format(results))
    return results


def returner(ret):
    '''
    Parse the return data and return metrics to librato.
    '''
    librato_conn = _get_librato(ret)

    q = librato_conn.new_queue()

    if ret['fun'] == 'state.highstate':
        log.debug("Found returned Highstate data.")
        # Calculate the runtimes and number of failed states.
        stats = _calculate_runtimes(ret['return'])
        log.debug("Batching Metric retcode with {0}".format(ret['retcode']))
        q.add("saltstack.highstate.retcode", ret[
              'retcode'], tags={'Name': ret['id']})

        log.debug("Batching Metric num_failed_jobs with {0}".format(
            stats['num_failed_states']))
        q.add("saltstack.highstate.failed_states",
              stats['num_failed_states'], tags={'Name': ret['id']})

        log.debug("Batching Metric num_passed_states with {0}".format(
            stats['num_passed_states']))
        q.add("saltstack.highstate.passed_states",
              stats['num_passed_states'], tags={'Name': ret['id']})

        log.debug("Batching Metric runtime with {0}".format(stats['runtime']))
        q.add("saltstack.highstate.runtime",
              stats['runtime'], tags={'Name': ret['id']})

        log.debug("Batching Metric runtime with {0}".format(
            stats['num_failed_states'] + stats['num_passed_states']))
        q.add("saltstack.highstate.total_states", stats[
              'num_failed_states'] + stats['num_passed_states'], tags={'Name': ret['id']})

    log.info("Sending Metrics to librato.")
    q.submit()
