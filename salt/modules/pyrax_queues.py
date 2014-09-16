# -*- coding: utf-8 -*-
'''
Connection module for Rackspace Queues

.. versionadded:: Hydrogen

:configuration: 

:depends: pyrax
'''

# Import Python libs
import logging
import json
import uuid

client_uuid = str(uuid.uuid4())

log = logging.getLogger(__name__)

# Import pyrax (SDK for Rackspace cloud) third party libs
try:
    import pyrax
    import pyrax.exceptions as exc
    logging.getLogger('pyrax').setLevel(logging.CRITICAL)
    HAS_PYRAX = True
except ImportError:
    HAS_PYRAX = False

from salt._compat import string_types

def __virtual__():
    '''
    Only load if pyrax libraries exist.
    '''
    if not HAS_PYRAX:
        return False
    return True

def create(qname, region=None, username=None, apikey=None, profile=None):
    '''
    Create RackSpace Queue.
    
    CLI Example::
        salt myminion pyraxqueues.create myqueue

    '''
    conn = _get_conn(region, username, apikey, profile)
    if conn:
        try:
            if exists(qname, region, username, apikey, profile):
                log.error('Queues "%s" already exists. Nothing done.' % qname)
                print "Allready exists"
                return True

            pyrax.queues.create(qname)

            return True
        except exc, err_msg:
            log.error('RackSpace API got some problems during creation: %s' % err_msg)

    return False

def delete(qname, region=None, username=None, apikey=None, profile=None):
    '''
    Delete an existings RackSpace Queue.

    CLI Example::
        salt myminion pyrax_queues.delete myqueue
    '''

    conn = _get_conn(region, username, apikey, profile)
    if not conn:
        return False

    try:
        q = exists(qname, region, username, apikey, profile)
        if not q:
            return False
        q.delete()

    except exc, err_msg:
        log.error('RackSpace API got some problems during deletion: %s' % err_msg)
        return False

    return True
    
def exists(qname, region=None, username=None, apikey=None, profile=None):
    '''
    Check to see if a Queue exists.

    CLI example::

        salt myminion pyrax_queues.exists myqueue
    '''
    conn = _get_conn(region, username, apikey, profile)
    if not conn:
        return False

    try:
# First if not exists() -> exit
        if not pyrax.queues.queue_exists(qname):
            return False
# If exist, search the queue to return the Queue Object
        for queue in pyrax.queues.list():
            if queue.name == qname:
                return queue
    except exc, err_msg:
        log.error('RackSpace API got some problems during existing queue check: %s' % err_msg)
    return False

def _get_conn(region=None, username=None, password=None, profile=None):
    '''
    Get a pyrax connection to RackSpace Cloud.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        username = _profile.get('username', None)
        apikey = _profile.get('apikey', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('rsq.region'):
        region = __salt__['config.option']('rsq.region')

    if not region:
        region = 'DFW'

    if not username and __salt__['config.option']('rsq.username'):
        username = __salt__['config.option']('rsq.username')
    if not apikey and __salt__['config.option']('rsq.apikey'):
        password = __salt__['config.option']('rsq.apikey')

    if not username or not apikey:
        log.error('No username and/or password in profile'
                  ' configuration.')
        return None

    try:
        pyrax.set_setting("identity_type", "rackspace")
        pyrax.set_credentials(username, apikey, None, region)

    except exc, err_msg:
        log.error('RackSpace API got some problems during connection: %s' % err_msg)
        return None

    pyrax.queues.client_id = client_uuid

    return pyrax.identity.authenticated
