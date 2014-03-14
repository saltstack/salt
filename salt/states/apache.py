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

def __virtual__():
    return 'apache.config' in __salt__

def config(name, config):
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': 'Failed to setup configuration file.'}

    ret['changes'] = {
        'old': None,
        'new': __salt__['apache.config'](name, config)
    }

    ret['result'] = True
    ret['comment'] = 'Successfully created configuration.'

    return ret
