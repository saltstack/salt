# -*- coding: utf-8 -*-
'''
Use Openstack Neutron data as a Pillar source. Will list all networks listed
inside of Neutron, to all minions.

.. versionadded:: 2015.5.1

:depends:  - python-neutronclient

A keystone profile must be used for the pillar to work (no generic keystone
configuration here). For example:

.. code-block:: yaml

    my openstack_config:
      keystone.user: 'admin'
      keystone.password: 'password'
      keystone.tenant: 'admin'
      keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
      keystone.region_name: 'RegionOne'
      keystone.service_type: 'network'

After the profile is created, configure the external pillar system to use it.

.. code-block:: yaml

    ext_pillar:
      - neutron: my_openstack_config

Using these configuration profiles, multiple neutron sources may also be used:

.. code-block:: yaml

    ext_pillar:
      - neutron: my_openstack_config
      - neutron: my_other_openstack_config

By default, these networks will be returned as a pillar item called
``networks``. In order to have them returned under a different name, add the
name after the Keystone profile name:

    ext_pillar:
      - neutron: my_openstack_config neutron_networks
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
try:
    import salt.utils.openstack.neutron as suoneu
    HAS_NEUTRON = True
except NameError as exc:
    HAS_NEUTRON = False

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only return if python-neutronclient is installed
    '''
    return HAS_NEUTRON


def _auth(profile=None):
    '''
    Set up neutron credentials
    '''
    credentials = __salt__['config.option'](profile)
    kwargs = {
        'username': credentials['keystone.user'],
        'password': credentials['keystone.password'],
        'tenant_name': credentials['keystone.tenant'],
        'auth_url': credentials['keystone.auth_url'],
        'region_name': credentials.get('keystone.region_name', None),
        'service_type': credentials['keystone.service_type'],
    }

    return suoneu.SaltNeutron(**kwargs)


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Check neutron for all data
    '''
    comps = conf.split()

    profile = None
    if comps[0]:
        profile = comps[0]

    conn = _auth(profile)
    ret = {}
    networks = conn.list_networks()
    for network in networks['networks']:
        ret[network['name']] = network

    if len(comps) < 2:
        comps.append('networks')
    return {comps[1]: ret}
