"""
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
                  - Indexes
                  - FollowSymlinks
                AllowOverride: All

.. versionchanged:: 2018.3.0

Allows having the same section container multiple times (e.g. <Directory /path/to/dir>).

YAML structure stays the same only replace dictionary with a list.

When a section container does not have mandatory attribute, such as <Else>,
it still needs keyword ``this`` with empty string (or "\b" if nicer output is required - without space).

.. code-block:: yaml

    /etc/httpd/conf.d/website.com.conf:
      apache.configfile:
        - config:
          - VirtualHost:
              - this: '*:80'
              - ServerName:
                - website.com
              - DocumentRoot: /var/www/vhosts/website.com
              - Directory:
                  this: /var/www/vhosts/website.com
                  Order: Deny,Allow
                  Deny from: all
                  Allow from:
                    - 127.0.0.1
                    - 192.168.100.0/24
                  Options:
                    - Indexes
                    - FollowSymlinks
                  AllowOverride: All
              - Directory:
                - this: /var/www/vhosts/website.com/private
                - Order: Deny,Allow
                - Deny from: all
                - Allow from:
                  - 127.0.0.1
                  - 192.168.100.0/24
                - If:
                    this: some condition
                    do: something
                - Else:
                    this:
                    do: something else
                - Else:
                    this: "\b"
                    do: another thing
"""

import os

import salt.utils.files
import salt.utils.stringutils


def __virtual__():
    if "apache.config" in __salt__:
        return True
    return (False, "apache module could not be loaded")


def configfile(name, config):
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    configs = __salt__["apache.config"](name, config, edit=False)
    current_configs = ""
    if os.path.exists(name):
        with salt.utils.files.fopen(name) as config_file:
            current_configs = salt.utils.stringutils.to_unicode(config_file.read())

    if configs.strip() == current_configs.strip():
        ret["result"] = True
        ret["comment"] = "Configuration is up to date."
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Configuration will update."
        ret["changes"] = {"old": current_configs, "new": configs}
        ret["result"] = None
        return ret

    try:
        with salt.utils.files.fopen(name, "w") as config_file:
            print(salt.utils.stringutils.to_str(configs), file=config_file)
        ret["changes"] = {"old": current_configs, "new": configs}
        ret["result"] = True
        ret["comment"] = "Successfully created configuration."
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = "Failed to create apache configuration."

    return ret
