# -*- coding: utf-8 -*-
'''
Return data to an etcd server or cluster

:depends: - python-etcd

In order to return to an etcd server, a profile should be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 4001

Additionally, two more options must be specified in the top-level configuration
in order to use the etcd returner:

.. code-block:: yaml

    etcd.returner: my_etcd_config
    etcd.returner_root: /salt/return

The ``etcd.returner`` option specifies which configuration profile to use. The
``etcd.returner_root`` option specifies the path inside etcd to use as the root
of the returner system.

Once the etcd options are configured, the returner may be used:

CLI Example:

    salt '*' test.ping --return etcd
'''
from __future__ import absolute_import

# Import python libs
import json
import logging

# Import salt libs
try:
    import salt.utils.etcd_util
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

import salt.utils
import salt.utils.jid

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'etcd'


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    return __virtualname__ if HAS_LIBS else False


def _get_conn(opts):
    '''
    Establish a connection to etcd
    '''
    profile = opts.get('etcd.returner', None)
    path = opts.get('etcd.returner_root', '/salt/return')
    return salt.utils.etcd_util.get_conn(opts, profile), path


def returner(ret):
    '''
    Return data to an etcd server or cluster
    '''
    client, path = _get_conn(__opts__)

    # Make a note of this minion for the external job cache
    client.write(
        '/'.join((path, 'minions', ret['id'])),
        ret['jid'],
    )

    for field in ret:
        # Not using os.path.join because we're not dealing with file paths
        dest = '/'.join((
            path,
            'jobs',
            ret['jid'],
            ret['id'],
            field
        ))
        client.write(dest, json.dumps(ret[field]))


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    client, path = _get_conn(__opts__)
    client.write(
        '/'.join((path, 'jobs', jid, '.load.p')),
        json.dumps(load)
    )


def save_minions(jid, minions):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    client, path = _get_conn(__opts__)
    return json.loads(client.get('/'.join((path, 'jobs', jid, '.load.p'))))


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    client, path = _get_conn(__opts__)
    jid_path = '/'.join((path, 'jobs', jid))
    return salt.utils.etcd_util.tree(client, jid_path)


def get_fun():
    '''
    Return a dict of the last function called for all minions
    '''
    ret = {}
    client, path = _get_conn(__opts__)
    items = client.get('/'.join((path, 'minions')))
    for item in items.children:
        comps = str(item.key).split('/')
        ret[comps[-1]] = item.value
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    ret = []
    client, path = _get_conn(__opts__)
    items = client.get('/'.join((path, 'jobs')))
    for item in items.children:
        if item.dir is True:
            comps = str(item.key).split('/')
            ret.append(comps[-1])
    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    ret = []
    client, path = _get_conn(__opts__)
    items = client.get('/'.join((path, 'minions')))
    for item in items.children:
        comps = str(item.key).split('/')
        ret.append(comps[-1])
    return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
