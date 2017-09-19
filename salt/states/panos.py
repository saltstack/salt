# -*- coding: utf-8 -*-
'''
A state module to manage Palo Alto network devices.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix


About
=====
This state module was designed to handle connections to a Palo Alto based
firewall. This module relies on the Palo Alto proxy module to interface with the devices.

This state module is designed to give extreme flexibility in the control over XPATH values on the PANOS device. It
exposes the core XML API commands and allows state modules to chain complex XPATH commands.

Below is an example of how to construct a security rule and move to the top of the policy. This will take a config
lock to prevent execution during the operation, then remove the lock. After the XPATH has been deployed, it will
commit to the device.

.. code-block:: yaml

    panos/takelock:
        panos.add_config_lock
    panos/service_tcp_22:
        panos.set_config:
            - xpath: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/service
            - value: <entry name='tcp-22'><protocol><tcp><port>22</port></tcp></protocol></entry>
            - commit: False
    panos/create_rule1:
        panos.set_config:
            - xpath: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules
            - value: '
              <entry name="rule1">
                <from><member>trust</member></from>
                <to><member>untrust</member></to>
                <source><member>10.0.0.1</member></source>
                <destination><member>10.0.1.1</member></destination>
                <service><member>tcp-22</member></service>
                <application><member>any</member></application>
                <action>allow</action>
                <disabled>no</disabled>
              </entry>'
            - commit: False
    panos/moveruletop:
        panos.move_config:
            - xpath: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
            - where: top
            - commit: False
    panos/removelock:
        panos.remove_config_lock
    panos/commit:
        panos.commit

Version Specific Configurations
===============================
Palo Alto devices running different versions will have different supported features and different command structures. In
order to account for this, the proxy module can be leveraged to check if the panos device is at a specific revision
level.

The proxy['panos.is_required_version'] method will check if a panos device is currently running a version equal or
greater than the passed version. For example, proxy['panos.is_required_version']('7.0.0') would match both 7.1.0 and
8.0.0.

.. code-block:: yaml

    {% if proxy['panos.is_required_version']('8.0.0') %}
    panos/deviceconfig/system/motd-and-banner:
      panos.set_config:
        - xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/motd-and-banner
        - value: |
          <banner-header>BANNER TEXT</banner-header>
          <banner-header-color>color2</banner-header-color>
          <banner-header-text-color>color18</banner-header-text-color>
          <banner-header-footer-match>yes</banner-header-footer-match>
        - commit: False
    {% endif %}

.. seealso::
    :prox:`Palo Alto Proxy Module <salt.proxy.panos>`

'''

# Import Python Libs
from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def __virtual__():
    return 'panos.commit' in __salt__


def _default_ret(name):
    '''
    Set the default response values.

    '''
    ret = {
        'name': name,
        'changes': {},
        'commit': None,
        'result': False,
        'comment': ''
    }
    return ret


def add_config_lock(name):
    '''
    Prevent other users from changing configuration until the lock is released.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/takelock:
            panos.add_config_lock

    '''
    ret = _default_ret(name)

    ret.update({
        'changes': __salt__['panos.add_config_lock'](),
        'result': True
    })

    return ret


def clone_config(name, xpath=None, newname=None, commit=False):
    '''
    Clone a specific XPATH and set it to a new name.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to clone.

    newname(str): The new name of the XPATH clone.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/clonerule:
            panos.clone_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/rulebase/security/rules&from=/config/devices/
              entry/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
              - value: rule2
              - commit: True

    '''
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not newname:
        return ret

    query = {'type': 'config',
             'action': 'clone',
             'xpath': xpath,
             'newname': newname}

    response = __proxy__['panos.call'](query)

    ret.update({
        'changes': response,
        'result': True
    })

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret


def commit(name):
    '''
    Commits the candidate configuration to the running configuration.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/commit:
            panos.commit

    '''
    ret = _default_ret(name)

    ret.update({
        'commit': __salt__['panos.commit'](),
        'result': True
    })

    return ret


def delete_config(name, xpath=None, commit=False):
    '''
    Deletes a Palo Alto XPATH to a specific value.

    Use the xpath parameter to specify the location of the object to be deleted.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/deletegroup:
            panos.delete_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/address-group/entry[@name='test']
              - commit: True

    '''
    ret = _default_ret(name)

    if not xpath:
        return ret

    query = {'type': 'config',
             'action': 'delete',
              'xpath': xpath}

    response = __proxy__['panos.call'](query)

    ret.update({
        'changes': response,
        'result': True
    })

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret


def download_software(name, version=None, synch=False, check=False):
    '''
    Ensures that a software version is downloaded.

    name: The name of the module function to execute.

    version(str): The software version to check. If this version is not already downloaded, it will attempt to download
    the file from Palo Alto.

    synch(bool): If true, after downloading the file it will be synched to its peer.

    check(bool): If true, the PANOS device will first attempt to pull the most recent software inventory list from Palo
    Alto.

    SLS Example:

    .. code-block:: yaml

        panos/version8.0.0:
            panos.download_software:
              - version: 8.0.0
              - synch: False
              - check: True

    '''
    ret = _default_ret(name)

    if check is True:
        __salt__['panos.check_software']()

    versions = __salt__['panos.get_software_info']()

    if 'sw-updates' not in versions \
        or 'versions' not in versions['sw-updates'] \
        or 'entry' not in versions['sw-updates']['versions']:
        ret.update({
            'comment': 'Software version is not found in the local software list.',
            'result': False
        })
        return ret

    for entry in versions['sw-updates']['versions']['entry']:
        if entry['version'] == version and entry['downloaded'] == "yes":
            ret.update({
                'comment': 'Software version is already downloaded.',
                'result': True
            })
        return ret

    ret.update({
        'changes': __salt__['panos.download_software_version'](version=version, synch=synch)
    })

    versions = __salt__['panos.get_software_info']()

    if 'sw-updates' not in versions \
        or 'versions' not in versions['sw-updates'] \
        or 'entry' not in versions['sw-updates']['versions']:
        ret.update({
            'result': False
        })
        return ret

    for entry in versions['sw-updates']['versions']['entry']:
        if entry['version'] == version and entry['downloaded'] == "yes":
            ret.update({
                'result': True
            })
        return ret

    return ret


def edit_config(name, xpath=None, value=None, commit=False):
    '''
    Edits a Palo Alto XPATH to a specific value. This will always overwrite the existing value, even if it is not
    changed.

    You can replace an existing object hierarchy at a specified location in the configuration with a new value. Use
    the xpath parameter to specify the location of the object, including the node to be replaced.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    value(str): The XML value to edit. This must be a child to the XPATH.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/addressgroup:
            panos.edit_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/address-group/entry[@name='test']
              - value: <static><entry name='test'><member>abc</member><member>xyz</member></entry></static>
              - commit: True

    '''
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not value:
        return ret

    query = {'type': 'config',
             'action': 'edit',
             'xpath': xpath,
              'element': value}

    response = __proxy__['panos.call'](query)

    ret.update({
        'changes': response,
        'result': True
    })

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret


def move_config(name, xpath=None, where=None, dst=None, commit=False):
    '''
    Moves a XPATH value to a new location.

    Use the xpath parameter to specify the location of the object to be moved, the where parameter to
    specify type of move, and dst parameter to specify the destination path.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to move.

    where(str): The type of move to execute. Valid options are after, before, top, bottom. The after and before
    options will require the dst option to specify the destination of the action. The top action will move the
    XPATH to the top of its structure. The botoom action will move the XPATH to the bottom of its structure.

    dst(str): Optional. Specifies the destination to utilize for a move action. This is ignored for the top
    or bottom action.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/moveruletop:
            panos.move_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
              - where: top
              - commit: True

        panos/moveruleafter:
            panos.move_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
              - where: after
              - dst: rule2
              - commit: True

    '''
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not where:
        return ret

    if where == 'after':
        query = {'type': 'config',
                 'action': 'move',
                 'xpath': xpath,
                 'where': 'after',
                 'dst': dst}
    elif where == 'before':
        query = {'type': 'config',
                 'action': 'move',
                 'xpath': xpath,
                 'where': 'before',
                 'dst': dst}
    elif where == 'top':
        query = {'type': 'config',
                 'action': 'move',
                 'xpath': xpath,
                 'where': 'top'}
    elif where == 'bottom':
        query = {'type': 'config',
                 'action': 'move',
                 'xpath': xpath,
                 'where': 'bottom'}

    response = __proxy__['panos.call'](query)

    ret.update({
        'changes': response,
        'result': True
    })

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret


def remove_config_lock(name):
    '''
    Release config lock previously held.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/takelock:
            panos.remove_config_lock

    '''
    ret = _default_ret(name)

    ret.update({
        'changes': __salt__['panos.remove_config_lock'](),
        'result': True
    })

    return ret


def rename_config(name, xpath=None, newname=None, commit=False):
    '''
    Rename a Palo Alto XPATH to a specific value. This will always rename the value even if a change is not needed.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    newname(str): The new name of the XPATH value.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/renamegroup:
            panos.rename_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/address/entry[@name='old_address']
              - value: new_address
              - commit: True

    '''
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not newname:
        return ret

    query = {'type': 'config',
             'action': 'rename',
             'xpath': xpath,
             'newname': newname}

    response = __proxy__['panos.call'](query)

    ret.update({
        'changes': response,
        'result': True
    })

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret


def set_config(name, xpath=None, value=None, commit=False):
    '''
    Sets a Palo Alto XPATH to a specific value. This will always overwrite the existing value, even if it is not
    changed.

    You can add or create a new object at a specified location in the configuration hierarchy. Use the xpath parameter
    to specify the location of the object in the configuration

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    value(str): The XML value to set. This must be a child to the XPATH.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/hostname:
            panos.set_config:
              - xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system
              - value: <hostname>foobar</hostname>
              - commit: True

    '''
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not value:
        return ret

    query = {'type': 'config',
             'action': 'set',
             'xpath': xpath,
             'element': value}

    response = __proxy__['panos.call'](query)

    ret.update({
        'changes': response,
        'result': True
    })

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret
