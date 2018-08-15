# -*- coding: utf-8 -*-
'''
Swift Client Module Directory
'''
from __future__ import unicode_literals, absolute_import

# import Salt Library
from salt.utils.openstack.swift import SaltSwift


def needscache():
    '''
    Need cache setup for this driver
    '''
    return True


def get(url, dest, **kwargs):
    '''
    Get file from Swift
    '''
    url_data, _, _ = __salt__['cp.get_url_data'](url)

    def swift_opt(key, default):
        '''
        Get value of <key> from Minion config or from Pillar
        '''
        if key in __opts__:
            return __opts__[key]
        try:
            return __opts__['pillar'][key]
        except (KeyError, TypeError):
            return default

    swift_conn = SaltSwift(swift_opt('keystone.user', None),
                           swift_opt('keystone.tenant', None),
                           swift_opt('keystone.auth_url', None),
                           swift_opt('keystone.password', None))

    swift_conn.get_object(url_data.netloc,
                          url_data.path[1:],
                          dest)
    return dest
