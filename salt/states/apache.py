# -*- coding: utf-8 -*-
'''
Apache state

.. versionadded:: 2014.7.0

Allows for inputting a yaml dictionary into a file for apache configuration
files.

The variable ``this`` is special and signifies what should be included with
the above word between angle brackets (<>).

.. code-block:: yaml

    /etc/httpd/conf.d/website.com.conf:
      apache.configfile:
        - config:
          - VirtualHost:
              this: '*:80'
              ServerName:
                - website.com
              ServerAlias:
                - www.website.com
                - dev.website.com
              ErrorLog: logs/website.com-error_log
              CustomLog: logs/website.com-access_log combined
              DocumentRoot: /var/www/vhosts/website.com
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
                AllowOverride: All
'''

from __future__ import with_statement, print_function
from __future__ import absolute_import

# Import python libs
import os.path

# Import Salt libs
import salt.utils


def __virtual__():
    return 'apache.config' in __salt__


def configfile(name, config):
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    configs = __salt__['apache.config'](name, config, edit=False)
    current_configs = ''
    if os.path.exists(name):
        with salt.utils.fopen(name) as config_file:
            current_configs = config_file.read()

    if configs == current_configs.strip():
        ret['result'] = True
        ret['comment'] = 'Configuration is up to date.'
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Configuration will update.'
        ret['changes'] = {
            'old': current_configs,
            'new': configs
        }
        ret['result'] = None
        return ret

    try:
        with salt.utils.fopen(name, 'w') as config_file:
            print(configs, file=config_file)
        ret['changes'] = {
            'old': current_configs,
            'new': configs
        }
        ret['result'] = True
        ret['comment'] = 'Successfully created configuration.'
    except Exception as exc:
        ret['result'] = False
        ret['comment'] = 'Failed to create apache configuration.'

    return ret
