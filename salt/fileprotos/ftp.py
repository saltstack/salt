# -*- coding: utf-8 -*-
'''
Ftp Client Module Directory
'''
from __future__ import unicode_literals, absolute_import

# Import Python Library
import ftplib


def needscache():
    '''
    Need cache setup for this driver
    '''
    return True


def get(url, dest, **kwargs):
    '''
    Get file from ftp
    '''
    url_data, _, _ = __salt__['cp.get_url_data'](url)
    ftp = ftplib.FTP()
    ftp.connect(url_data.hostname, url_data.port)
    ftp.login(url_data.username, url_data.password)
    remote_file_path = url_data.path.lstrip('/')
    with __utils__['files.fopen'](dest, 'wb') as fp_:
        ftp.retrbinary('RETR {0}'.format(remote_file_path), fp_.write)
    ftp.quit()
    return dest
