# -*- coding: utf-8 -*-
'''
Module providing a simple management interface to a chronos cluster.

Currently this only works when run through a proxy minion.

.. versionadded:: 2015.8.2
'''
from __future__ import absolute_import

import json
import logging
import salt.utils
import salt.utils.http
from salt.exceptions import get_error_message


__proxyenabled__ = ['chronos']
log = logging.getLogger(__file__)


def __virtual__():
    # only valid in proxy minions for now
    return salt.utils.is_proxy() and 'proxy' in __opts__


def _base_url():
    '''
    Return the proxy configured base url.
    '''
    base_url = "http://locahost:4400"
    if 'proxy' in __opts__:
        base_url = __opts__['proxy'].get('base_url', base_url)
    return base_url


def _jobs():
    '''
    Return the currently configured jobs.
    '''
    response = salt.utils.http.query(
        "{0}/scheduler/jobs".format(_base_url()),
        decode_type='json',
        decode=True,
    )
    jobs = {}
    for job in response['dict']:
        jobs[job.pop('name')] = job
    return jobs


def jobs():
    '''
    Return a list of the currently installed job names.

    CLI Example:
    .. code-block:: bash
        salt chronos-minion-id chronos.jobs
    '''
    job_names = _jobs().keys()
    job_names.sort()
    return {'jobs': job_names}


def has_job(name):
    '''
    Return whether the given job is currently configured.

    CLI Example:
    .. code-block:: bash
        salt chronos-minion-id chronos.has_job my-job
    '''
    return name in _jobs()


def job(name):
    '''
    Return the current server configuration for the specified job.

    CLI Example:
    .. code-block:: bash
        salt chronos-minion-id chronos.job my-job
    '''
    jobs = _jobs()
    if name in jobs:
        return {'job': jobs[name]}
    return None


def update_job(name, config):
    '''
    Update the specified job with the given configuration.

    CLI Example:
    .. code-block:: bash
        salt chronos-minion-id chronos.update_job my-job '<config yaml>'
    '''
    if 'name' not in config:
        config['name'] = name
    data = json.dumps(config)
    try:
        response = salt.utils.http.query(
            "{0}/scheduler/iso8601".format(_base_url()),
            method='POST',
            data=data,
            header_dict={
                'Content-Type': 'application/json',
            },
        )
        log.debug('update response: %s', response)
        return {'success': True}
    except Exception as ex:
        log.error('unable to update chronos job: %s', get_error_message(ex))
        return {
            'exception': {
                'message': get_error_message(ex),
            }
        }


def rm_job(name):
    '''
    Remove the specified job from the server.

    CLI Example:
    .. code-block:: bash
        salt chronos-minion-id chronos.rm_job my-job
    '''
    response = salt.utils.http.query(
        "{0}/scheduler/job/{1}".format(_base_url(), name),
        method='DELETE',
    )
    return True
