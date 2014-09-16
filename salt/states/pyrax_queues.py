# -*- coding: utf-8 -*-
'''
Manage Rackspace Queues
=======================

.. versionadded:: XXXXXXXX

Create and destroy Rackspace queues. Be aware that this interacts with 
Rackspace's services, and so may incur charges.

This module uses ``pyrax``, which can be installed via package, or pip.
This module is greatly inspired by boto_* modules from SaltStack code source.

.. code-block:: yaml

    rsq.username: XXXXXXXXXXXXX
    rsq.apikey: YYYYYYYYYYYYY

It's also possible to specify ``username``, ``apikey`` and ``region`` via a profile, 
either passed in as a dict, or as a string to pull from pillars or minion 
config:

.. code-block:: yaml

    myprofile:
        username: XXXXXXXXXXXXX
        apikey: YYYYYYYYYYYYY
        region: DWS


.. code-block:: yaml

    myqueue:
        pyrax_queues.present:
            - region: DFW
            - username: XXXXXXXXXXXXX
            - apikey: YYYYYYYYYYYYY

    # Using a profile from pillars
    myqueue:
        pyrax_queues.present:
            - region: DFW
            - profile: my_rs_profile

    # Passing in a profile
    myqueue:
        pyrax_queues.present:
            - region: DFW
            - profile:
                username: XXXXXXXXXXXXX
                apikey: YYYYYYYYYYYYY
'''


def __virtual__():
    '''
    Only load if pyrax is available.
    '''
    return 'pyrax_queues' if 'pyrax_queues.exists' in __salt__ else False


def present(
        name,
        region=None,
        username=None,
        apikey=None,
        profile=None):
    '''
    Ensure the RackSpace queue exists.

    name
        Name of the Rackspace queue.

    region
        Region to connect to.

    username
        Rackspace username to be used.

    apikey
        APIkey to be used.

    profile
        A dict with region, username and APIkey.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = __salt__['pyrax_queues.exists'](name, region, username, apikey, profile)


    if not is_present:
        if __opts__['test']:
            msg = 'Rackspace queue {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        created = __salt__['pyrax_queues.create'](name, region, username, apikey,
                                              profile)
        if created:
            ret['changes']['old'] = None
            ret['changes']['new'] = {'queue': name}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} Rackspace queue.'.format(name)
            return ret
    else:
        ret['comment'] = '{0} present.'.format(name)

    return ret


def absent(
        name,
        region=None,
        username=None,
        apikey=None,
        profile=None):
    '''
    Ensure the named Rackspace queue is deleted.

    name
        Name of the Rackspace queue.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = __salt__['pyrax_queues.exists'](name, region, username, apikey, profile)

    if is_present:
        if __opts__['test']:
            ret['comment'] = 'Rackspace queue {0} is set to be removed.'.format(
                name)
            ret['result'] = None
            return ret
        deleted = __salt__['pyrax_queues.delete'](name, region, username, apikey,
                                              profile)
        if deleted:
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} Rackspace queue.'.format(name)
    else:
        ret['comment'] = '{0} does not exist in {1}.'.format(name, region)

    return ret
