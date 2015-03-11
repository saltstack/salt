# -*- coding: utf-8 -*-
'''
Execute Chef client runs
=====================================================================

Run chef-client or chef-solo

.. code-block:: yaml

    my-chef-run:
      chef.client:
        - override-runlist: 'demo1,demo2'
        - server: 'https://chef.domain.com'

    default-chef-run:
      chef.client: []

    my-solo-run:
      chef.solo:
        - environment: dev
'''
from __future__ import absolute_import

# Import python libs
import re


def __virtual__():
    '''
    Only load if Chef execution module is available.
    '''
    return True if 'chef.client' in __salt__ else False


def client(name, **kwargs):
    '''
    name
        Unique identifier for the state. Does not affect the Chef run.

    server
        The chef server URL

    client_key
        Set the client key file location

    config
        The configuration file to use

    config-file-jail
        Directory under which config files are allowed to be loaded
        (no client.rb or knife.rb outside this path will be loaded).

    environment
        Set the Chef Environment on the node

    group
        Group to set privilege to

    json-attributes
        Load attributes from a JSON file or URL

    localmode
        Point chef-client at local repository if True

    log_level
        Set the log level (debug, info, warn, error, fatal)

    logfile
        Set the log file location

    node-name
        The node name for this client

    override-runlist
        Replace current run list with specified items for a single run

    pid
        Set the PID file location, defaults to /tmp/chef-client.pid

    run-lock-timeout
        Set maximum duration to wait for another client run to finish,
        default is indefinitely.

    runlist
        Permanently replace current run list with specified items

    user
        User to set privilege to

    validation_key
        Set the validation key file location, used for registering new clients
    '''
    return _run(name, 'chef.client', kwargs)


def solo(name, **kwargs):
    '''
    name
        Unique identifier for the state. Does not affect the Chef run.

    config
        The configuration file to use

    environment
        Set the Chef Environment on the node

    group
        Group to set privilege to

    json-attributes
        Load attributes from a JSON file or URL

    log_level
        Set the log level (debug, info, warn, error, fatal)

    logfile
        Set the log file location

    node-name
        The node name for this client

    override-runlist
        Replace current run list with specified items for a single run

    recipe-url
        Pull down a remote gzipped tarball of recipes and untar it to
        the cookbook cache

    run-lock-timeout
        Set maximum duration to wait for another client run to finish,
        default is indefinitely.

    user
        User to set privilege to

    '''
    return _run(name, 'chef.solo', kwargs)


def _run(name, mod, kwargs):
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    result = __salt__[mod](whyrun=__opts__['test'], **kwargs)
    if result['retcode'] == 0:

        if _has_changes(result['stdout']):
            # Populate the 'changes' dict if anything changed
            ret['changes']['summary'] = _summary(result['stdout'])
            ret['result'] = True if not __opts__['test'] else None
        else:
            ret['result'] = True
    else:
        ret['result'] = False

    ret['comment'] = '\n'.join([result['stdout'], result['stderr']])
    return ret


def _summary(stdout):
    return stdout.splitlines()[-1]


def _has_changes(stdout):
    regex = re.search(
        r'Chef Client finished, (\d+)',
        _summary(stdout),
        re.IGNORECASE
    )
    return int(regex.group(1)) > 0
