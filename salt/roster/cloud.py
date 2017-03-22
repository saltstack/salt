# -*- coding: utf-8 -*-
'''
Use the cloud cache on the master to derive IPv4 addresses based on minion ID.

This roster requires that the minion in question was created using at least the
2015.5.0 version of Salt Cloud. Starting with the 2015.5.0 release, Salt Cloud
maintains an index of minions that it creates and deletes. This index tracks the
provider and profile configuration used to provision the minion, including
authentication information. So long as this configuration remains current, it can
be used by Salt SSH to log into any minion in the index.

To connect as a user other than root, modify the cloud configuration file
usually located at /etc/salt/cloud. For example, add the following:

.. code-block:: yaml

    ssh_username: my_user
    sudo: True
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt libs
import salt.loader
import salt.utils
import salt.utils.cloud
import salt.utils.validate.net
import salt.config
from salt.ext.six import string_types


def targets(tgt, tgt_type='glob', **kwargs):  # pylint: disable=W0613
    '''
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    '''
    ret = {}

    cloud_opts = salt.config.cloud_config(
        os.path.join(os.path.dirname(__opts__['conf_file']), 'cloud')
    )

    minions = __runner__['cache.cloud'](tgt)
    for minion_id, full_info in minions.items():
        profile, provider = full_info.get('profile', None), full_info.get('provider', None)
        vm_ = {
            'driver': provider,
            'profile': profile,
        }
        public_ips = full_info.get('public_ips', [])
        private_ips = full_info.get('private_ips', [])
        ip_list = []
        for item in (public_ips, private_ips):
            if isinstance(item, list):
                ip_list = ip_list + item
            elif isinstance(item, string_types):
                ip_list.append(item)

        roster_order = __opts__.get('roster_order', (
            'public', 'private', 'local'
        ))
        preferred_ip = extract_ipv4(roster_order, ip_list)

        ret[minion_id] = __opts__.get('roster_defaults', {})
        ret[minion_id].update({'host': preferred_ip})

        ssh_username = salt.utils.cloud.ssh_usernames({}, cloud_opts)
        if isinstance(ssh_username, string_types):
            ret[minion_id]['user'] = ssh_username
        elif isinstance(ssh_username, list):
            if ssh_username[0] != 'root':
                ret[minion_id]['user'] = ssh_username[0]

        password = salt.config.get_cloud_config_value(
            'ssh_password', vm_, cloud_opts, search_global=False, default=None
        )
        if password:
            ret[minion_id]['password'] = password

        key_filename = salt.config.get_cloud_config_value(
            'private_key', vm_, cloud_opts, search_global=False, default=None
        )
        if key_filename:
            ret[minion_id]['priv'] = key_filename

        sudo = salt.config.get_cloud_config_value(
            'sudo', vm_, cloud_opts, search_global=False, default=None
        )
        if sudo:
            ret[minion_id]['sudo'] = sudo

    return ret


def extract_ipv4(roster_order, ipv4):
    '''
    Extract the preferred IP address from the ipv4 grain
    '''
    for ip_type in roster_order:
        for ip_ in ipv4:
            if ':' in ip_:
                continue
            if not salt.utils.validate.net.ipv4_addr(ip_):
                continue
            if ip_type == 'local' and ip_.startswith('127.'):
                return ip_
            elif ip_type == 'private' and not salt.utils.cloud.is_public_ip(ip_):
                return ip_
            elif ip_type == 'public' and salt.utils.cloud.is_public_ip(ip_):
                return ip_
    return None
