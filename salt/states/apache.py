# -*- coding: utf-8 -*-
'''
Apache state

Allows for inputting a yaml dictionary into a file for apache configuration
files.

The variable 'this' is special and signifies what should be included with
the above word between angle brackets (<>).

/etc/httpd/conf.d/website.com.conf:
  apache.config:
    - config:
      - VirtualHost:
          this: '*:80'
          ServerName:
            -website.com
          ServerAlias:
            - www.website.com
            - dev.website.com
          ErrorLog: logs/website.com-error_log
          CustomLog: logs/website.com-access_log combinded
          Directory:
            this: /var/www/vhosts/website.com
            Order: Deny,Allow
            Deny from: all
            Allow from:
              - 127.0.0.1
              - 192.168.100.0/24
            Options:
              - +Indexes
              - FollowSymlinks
            AllowOverrides: All
'''

# Import python libs
import os.path

# Import salt libs
import salt.cloud.utils


def __virtual__():
    return 'apache.config' in __salt__


def _check_name(name):
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if suc.check_name(name, 'a-zA-Z0-9._-/<>'):
        ret['comment'] = 'Invalid characters in name.'
        ret['result'] = False
        return ret
    else:
        ret['result'] = True
        return ret


def config(name, config, force=False):
    ret = _check_name(str(config))

    if os.path.exists(name) and not force:
        ret['result'] = True
        ret['comment'] = 'Configuration file exists.'
    elif __opts__['test']:
        ret['comment'] = 'Configuration will update.'
        ret['result'] = None
        return ret

    try:
        ret['changes'] = {
            'old': None,
            'new': __salt__['apache.config'](name, config)
        }
        ret['result'] = True
        ret['comment'] = 'Successfully created configuration.'
    except Exception as exc:
        ret['result'] = False
        ret['comment'] = 'Failed to create apache configuration.'

    return ret
