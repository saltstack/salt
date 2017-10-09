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


def _build_members(members, anycheck=False):
    '''
    Builds a member formatted string for XML operation.

    '''
    if isinstance(members, list):

        # This check will strip down members to a single any statement
        if anycheck and 'any' in members:
            return "<member>any</member>"
        response = ""
        for m in members:
            response += "<member>{0}</member>".format(m)
        return response
    else:
        return "<member>{0}</member>".format(members)


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


def _edit_config(xpath, element):
    '''
    Sends an edit request to the device.

    '''
    query = {'type': 'config',
             'action': 'edit',
             'xpath': xpath,
              'element': element}

    response = __proxy__['panos.call'](query)

    return _validate_response(response)


def _get_config(xpath):
    '''
    Retrieves an xpath from the device.

    '''
    query = {'type': 'config',
             'action': 'get',
             'xpath': xpath}

    response = __proxy__['panos.call'](query)

    return response


def _move_after(xpath, target):
    '''
    Moves an xpath to the after of its section.

    '''
    query = {'type': 'config',
             'action': 'move',
             'xpath': xpath,
             'where': 'after',
             'dst': target}

    response = __proxy__['panos.call'](query)

    return _validate_response(response)


def _move_before(xpath, target):
    '''
    Moves an xpath to the bottom of its section.

    '''
    query = {'type': 'config',
             'action': 'move',
             'xpath': xpath,
             'where': 'before',
             'dst': target}

    response = __proxy__['panos.call'](query)

    return _validate_response(response)


def _move_bottom(xpath):
    '''
    Moves an xpath to the bottom of its section.

    '''
    query = {'type': 'config',
             'action': 'move',
             'xpath': xpath,
             'where': 'bottom'}

    response = __proxy__['panos.call'](query)

    return _validate_response(response)


def _move_top(xpath):
    '''
    Moves an xpath to the top of its section.

    '''
    query = {'type': 'config',
             'action': 'move',
             'xpath': xpath,
             'where': 'top'}

    response = __proxy__['panos.call'](query)

    return _validate_response(response)


def _set_config(xpath, element):
    '''
    Sends a set request to the device.

    '''
    query = {'type': 'config',
             'action': 'set',
             'xpath': xpath,
             'element': element}

    response = __proxy__['panos.call'](query)

    return _validate_response(response)


def _validate_response(response):
    '''
    Validates a response from a Palo Alto device. Used to verify success of commands.

    '''
    if not response:
        return False, "Error during move configuration. Verify connectivity to device."
    elif 'msg' in response:
        if response['msg'] == 'command succeeded':
            return True, response['msg']
        else:
            return False, response['msg']
    elif 'line' in response:
        if response['line'] == 'already at the top':
            return True, response['line']
        elif response['line'] == 'already at the bottom':
            return True, response['line']
        else:
            return False, response['line']
    else:
        return False, "Error during move configuration. Verify connectivity to device."


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


def commit_config(name):
    '''
    Commits the candidate configuration to the running configuration.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/commit:
            panos.commit_config

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

    This is the recommended state to enforce configurations on a xpath.

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

    result, msg = _edit_config(xpath, value)

    ret.update({
        'comment': msg,
        'result': result
    })

    # Ensure we do not commit after a failed action
    if not result:
        return ret

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

    commit(bool): If true the firewall will commit the changes, if false do not commit changes. If the operation is
    not successful, it will not commit.

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
        result, msg = _move_after(xpath, dst)
    elif where == 'before':
        result, msg = _move_before(xpath, dst)
    elif where == 'top':
        result, msg = _move_top(xpath)
    elif where == 'bottom':
        result, msg = _move_bottom(xpath)

    ret.update({
        'result': result
    })

    if not result:
        return ret

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


def security_rule_exists(name,
                         rulename=None,
                         vsys='1',
                         action=None,
                         disabled=None,
                         sourcezone=None,
                         destinationzone=None,
                         source=None,
                         destination=None,
                         application=None,
                         service=None,
                         description=None,
                         logsetting=None,
                         logstart=None,
                         logend=None,
                         negatesource=None,
                         negatedestination=None,
                         profilegroup=None,
                         datafilter=None,
                         fileblock=None,
                         spyware=None,
                         urlfilter=None,
                         virus=None,
                         vulnerability=None,
                         wildfire=None,
                         move=None,
                         movetarget=None,
                         commit=False):
    '''
    Ensures that a security rule exists on the device. Also, ensure that all configurations are set appropriately.

    This method will create the rule if it does not exist. If the rule does exist, it will ensure that the
    configurations are set appropriately.

    If the rule does not exist and is created, any value that is not provided will be provided as the default.
    The action, to, from, source, destination, application, and service fields are mandatory and must be provided.

    This will enforce the exact match of the rule. For example, if the rule is currently configured with the log-end
    option, but this option is not specified in the state method, it will be removed and reset to the system default.

    It is strongly recommended to specify all options to ensure proper operation.

    When defining the profile group settings, the device can only support either a profile group or individual settings.
    If both are specified, the profile group will be preferred and the individual settings are ignored. If neither are
    specified, the value will be set to system default of none.

    name: The name of the module function to execute.

    rulename(str): The name of the security rule.  The name is case-sensitive and can have up to 31 characters, which
    can be letters, numbers, spaces, hyphens, and underscores. The name must be unique on a firewall and, on Panorama,
    unique within its device group and any ancestor or descendant device groups.

    vsys(str): The string representation of the VSYS ID. Defaults to VSYS 1.

    action(str): The action that the security rule will enforce. Valid options are: allow, deny, drop, reset-client,
    reset-server, reset-both.

    disabled(bool): Controls if the rule is disabled. Set 'True' to disable and 'False' to enable.

    sourcezone(str, list): The source zone(s). The value 'any' will match all zones.

    destinationzone(str, list): The destination zone(s). The value 'any' will match all zones.

    source(str, list): The source address(es). The value 'any' will match all addresses.

    destination(str, list): The destination address(es). The value 'any' will match all addresses.

    application(str, list): The application(s) matched. The value 'any' will match all applications.

    service(str, list): The service(s) matched. The value 'any' will match all services. The value
    'application-default' will match based upon the application defined ports.

    description(str): A description for the policy (up to 255 characters).

    logsetting(str): The name of a valid log forwarding profile.

    logstart(bool): Generates a traffic log entry for the start of a session (disabled by default).

    logend(bool): Generates a traffic log entry for the end of a session (enabled by default).

    negatesource(bool): Match all but the specified source addresses.

    negatedestination(bool): Match all but the specified destination addresses.

    profilegroup(str): A valid profile group name.

    datafilter(str): A valid data filter profile name. Ignored with the profilegroup option set.

    fileblock(str): A valid file blocking profile name. Ignored with the profilegroup option set.

    spyware(str): A valid spyware profile name. Ignored with the profilegroup option set.

    urlfilter(str): A valid URL filtering profile name. Ignored with the profilegroup option set.

    virus(str): A valid virus profile name. Ignored with the profilegroup option set.

    vulnerability(str): A valid vulnerability profile name. Ignored with the profilegroup option set.

    wildfire(str): A valid vulnerability profile name. Ignored with the profilegroup option set.

    move(str): An optional argument that ensure the rule is moved to a specific location. Valid options are 'top',
    'bottom', 'before', or 'after'. The 'before' and 'after' options require the use of the 'movetarget' argument
    to define the location of the move request.

    movetarget(str): An optional argument that defines the target of the move operation if the move argument is
    set to 'before' or 'after'.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/rulebase/security/rule01:
            panos.security_rule_exists:
              - rulename: rule01
              - vsys: 1
              - action: allow
              - disabled: False
              - sourcezone: untrust
              - destinationzone: trust
              - source:
                - 10.10.10.0/24
                - 1.1.1.1
              - destination:
                - 2.2.2.2-2.2.2.4
              - application:
                - any
              - service:
                - tcp-25
              - description: My test security rule
              - logsetting: logprofile
              - logstart: False
              - logend: True
              - negatesource: False
              - negatedestination: False
              - profilegroup: myprofilegroup
              - move: top
              - commit: False

        panos/rulebase/security/rule01:
            panos.security_rule_exists:
              - rulename: rule01
              - vsys: 1
              - action: allow
              - disabled: False
              - sourcezone: untrust
              - destinationzone: trust
              - source:
                - 10.10.10.0/24
                - 1.1.1.1
              - destination:
                - 2.2.2.2-2.2.2.4
              - application:
                - any
              - service:
                - tcp-25
              - description: My test security rule
              - logsetting: logprofile
              - logstart: False
              - logend: False
              - datafilter: foobar
              - fileblock: foobar
              - spyware: foobar
              - urlfilter: foobar
              - virus: foobar
              - vulnerability: foobar
              - wildfire: foobar
              - move: after
              - movetarget: rule02
              - commit: False
    '''
    ret = _default_ret(name)

    if not rulename:
        return ret

    # Check if rule currently exists
    rule = __salt__['panos.get_security_rule'](rulename, vsys)

    # Build the rule element
    element = ""
    if sourcezone:
        element += "<from>{0}</from>".format(_build_members(sourcezone, True))
    else:
        ret.update({'comment': "The sourcezone field must be provided."})
        return ret

    if destinationzone:
        element += "<to>{0}</to>".format(_build_members(destinationzone, True))
    else:
        ret.update({'comment': "The destinationzone field must be provided."})
        return ret

    if source:
        element += "<source>{0}</source>".format(_build_members(source, True))
    else:
        ret.update({'comment': "The source field must be provided."})
        return

    if destination:
        element += "<destination>{0}</destination>".format(_build_members(destination, True))
    else:
        ret.update({'comment': "The destination field must be provided."})
        return ret

    if application:
        element += "<application>{0}</application>".format(_build_members(application, True))
    else:
        ret.update({'comment': "The application field must be provided."})
        return ret

    if service:
        element += "<service>{0}</service>".format(_build_members(service, True))
    else:
        ret.update({'comment': "The service field must be provided."})
        return ret

    if action:
        element += "<action>{0}</action>".format(action)
    else:
        ret.update({'comment': "The action field must be provided."})
        return ret

    if disabled is not None:
        if disabled:
            element += "<disabled>yes</disabled>"
        else:
            element += "<disabled>no</disabled>"

    if description:
        element += "<description>{0}</description>".format(description)

    if logsetting:
        element += "<log-setting>{0}</log-setting>".format(logsetting)

    if logstart is not None:
        if logstart:
            element += "<log-start>yes</log-start>"
        else:
            element += "<log-start>no</log-start>"

    if logend is not None:
        if logend:
            element += "<log-end>yes</log-end>"
        else:
            element += "<log-end>no</log-end>"

    if negatesource is not None:
        if negatesource:
            element += "<negate-source>yes</negate-source>"
        else:
            element += "<negate-source>no</negate-source>"

    if negatedestination is not None:
        if negatedestination:
            element += "<negate-destination>yes</negate-destination>"
        else:
            element += "<negate-destination>no</negate-destination>"

    # Build the profile settings
    profile_string = None
    if profilegroup:
        profile_string = "<group><member>{0}</member></group>".format(profilegroup)
    else:
        member_string = ""
        if datafilter:
            member_string += "<data-filtering><member>{0}</member></data-filtering>".format(datafilter)
        if fileblock:
            member_string += "<file-blocking><member>{0}</member></file-blocking>".format(fileblock)
        if spyware:
            member_string += "<spyware><member>{0}</member></spyware>".format(spyware)
        if urlfilter:
            member_string += "<url-filtering><member>{0}</member></url-filtering>".format(urlfilter)
        if virus:
            member_string += "<virus><member>{0}</member></virus>".format(virus)
        if vulnerability:
            member_string += "<vulnerability><member>{0}</member></vulnerability>".format(vulnerability)
        if wildfire:
            member_string += "<wildfire-analysis><member>{0}</member></wildfire-analysis>".format(wildfire)
        if member_string != "":
            profile_string = "<profiles>{0}</profiles>".format(member_string)

    if profile_string:
        element += "<profile-setting>{0}</profile-setting>".format(profile_string)

    full_element = "<entry name='{0}'>{1}</entry>".format(rulename, element)

    create_rule = False

    if 'result' in rule:
        if rule['result'] == "None":
            create_rule = True

    if create_rule:
        xpath = "/config/devices/entry[@name=\'localhost.localdomain\']/vsys/entry[@name=\'vsys{0}\']/rulebase/" \
                "security/rules".format(vsys)

        result, msg = _set_config(xpath, full_element)
        if not result:
            ret['changes']['set'] = msg
            return ret
    else:
        xpath = "/config/devices/entry[@name=\'localhost.localdomain\']/vsys/entry[@name=\'vsys{0}\']/rulebase/" \
                "security/rules/entry[@name=\'{1}\']".format(vsys, rulename)

        result, msg = _edit_config(xpath, full_element)
        if not result:
            ret['changes']['edit'] = msg
            return ret

    if move:
        movepath = "/config/devices/entry[@name=\'localhost.localdomain\']/vsys/entry[@name=\'vsys{0}\']/rulebase/" \
                   "security/rules/entry[@name=\'{1}\']".format(vsys, rulename)
        move_result = False
        move_msg = ''
        if move == "before" and movetarget:
            move_result, move_msg = _move_before(movepath, movetarget)
        elif move == "after":
            move_result, move_msg = _move_after(movepath, movetarget)
        elif move == "top":
            move_result, move_msg = _move_top(movepath)
        elif move == "bottom":
            move_result, move_msg = _move_bottom(movepath)

        if not move_result:
            ret['changes']['move'] = move_msg
            return ret

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'comment': 'Security rule verified successfully.',
            'result': True
        })
    else:
        ret.update({
            'comment': 'Security rule verified successfully.',
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

    result, msg = _set_config(xpath, value)

    ret.update({
        'comment': msg,
        'result': result
    })

    # Ensure we do not commit after a failed action
    if not result:
        return ret

    if commit is True:
        ret.update({
            'commit': __salt__['panos.commit'](),
            'result': True
        })

    return ret
