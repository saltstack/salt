# -*- coding: utf-8 -*-
'''
S3 Client Module Directory
'''
from __future__ import unicode_literals, absolute_import


def needscache():
    '''
    Need cache setup for this driver
    '''
    return True


def get(url, dest, **kwargs):
    '''
    Get file from s3
    '''
    url_data = __salt__['cp.get_url_data'](url)

    def s3_opt(key, default=None):
        '''
        Get value of s3.<key> from Minion config or from Pillar
        '''
        if 's3.' + key in __opts__:
            return __opts__['s3.' + key]
        try:
            return __opts__['pillar']['s3'][key]
        except (KeyError, TypeError):
            return default
    __utils__['s3.query'](method='GET',
                          bucket=url_data.netloc,
                          path=url_data.path[1:],
                          return_bin=False,
                          local_file=dest,
                          action=None,
                          key=s3_opt('key'),
                          keyid=s3_opt('keyid'),
                          service_url=s3_opt('service_url'),
                          verify_ssl=s3_opt('verify_ssl', True),
                          location=s3_opt('location'),
                          path_style=s3_opt('path_style', False),
                          https_enable=s3_opt('https_enable', True))
    return dest
