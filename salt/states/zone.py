# -*- coding: utf-8 -*-
'''
Management of Solaris Zones

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.modules.zoneadm, salt.modules.zonecfg
:platform:      solaris

.. versionadded:: 2017.7.0

Bellow are some examples of how to use this state.
Lets start with creating a zone and installing it.

.. code-block:: yaml

    omipkg1_configuration:
      zone.present:
        - name: omipkg1
        - brand: ipkg
        - zonepath: /zones/omipkg1
        - properties:
          - autoboot: true
          - ip-type: exclusive
          - cpu-shares: 50
        - resources:
          - attr:
            - name: owner
            - value: Jorge Schrauwen
            - type: string
          - attr:
            - name: description
            - value: OmniOS ipkg zone for testing
            - type: string
          - capped-memory:
            - physical: 64M
    omipkg1_installation:
      zone.installed:
        - name: omipkg1
        - require:
            - zone: omipkg1_configuration
    omipkg1_running:
      zone.booted:
        - name: omipkg1
        - require:
            - zone: omipkg1_installation

A zone without network access is not very useful. We could update
the zone.present state in the example above to add a network interface
or we could use a seperate state for this.

.. code-block:: yaml

    omipkg1_network:
      zone.resource_present:
        - name: omipkg1
        - resource_type: net
        - resource_selector_property: mac-addr
        - resource_selector_value: "02:08:20:a2:a3:10"
        - physical: znic1
        - require:
            - zone: omipkg1_configuration

Since this is a single tenant system having the owner attribute is pointless.
Let's remove that attribute.

.. note::
    The following state run the omipkg1_configuration state will add it again!
    If the entire configuration is managed it would be better to add resource_prune
    and optionally the resource_selector_property properties to the resource.

.. code-block:: yaml

    omipkg1_strip_owner:
      zone.resource_present:
        - name: omipkg1
        - resource_type: attr
        - resource_selector_property: name
        - resource_selector_value: owner
        - require:
            - zone: omipkg1_configuration

Let's bump the zone's CPU shares a bit.

.. note::
    The following state run the omipkg1_configuration state will set it to 50 again.
    Update the entire zone configuration is managed you should update it there instead.

.. code-block:: yaml

    omipkg1_more_cpu:
      zone.property_present:
        - name: omipkg1
        - property: cpu-shares
        - value: 100

Or we can remove the limit altogether!

.. note::
    The following state run the omipkg1_configuration state will set it to 50 again.
    Update the entire zone configuration is managed you should set the
    property to None (nothing after the :) instead.

.. code-block:: yaml

    omipkg1_no_cpu:
      zone.property_absent:
        - name: omipkg1
        - property: cpu-shares

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import Salt libs
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.files
from salt.modules.zonecfg import _parse_value, _zonecfg_resource_default_selectors
from salt.exceptions import CommandExecutionError
from salt.utils.odict import OrderedDict
from salt.utils.dictupdate import merge as merge_dict

log = logging.getLogger(__name__)

__func_alias__ = {
    'import_': 'import',
    'export_': 'export',
}

# Define the state's virtual name
__virtualname__ = 'zone'


def __virtual__():
    '''
    Provides zone state on Solaris
    '''
    if 'zonecfg.create' in __salt__ and 'zoneadm.install' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only be loaded on Solaris platforms'.format(
                __virtualname__
            )
        )


def property_present(name, property, value):
    '''
    Ensure property has a certain value

    name : string
        name of the zone
    property : string
        name of property
    value : string
        value of property

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    ## sanitize input
    value = _parse_value(value)

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)
        if property not in zonecfg or zonecfg[property] != _parse_value(value):
            if __opts__['test']:
                ret['result'] = True
            else:
                # update property
                zonecfg_res = __salt__['zonecfg.set_property'](name, property, value)
                ret['result'] = zonecfg_res['status']
                if 'messages' in zonecfg_res:
                    ret['comment'] = zonecfg_res['message']
            if ret['result']:
                ret['changes'][property] = _parse_value(value)
                if ret['comment'] == '':
                    ret['comment'] = 'The property {0} is was updated to {1}.'.format(property, value)
            elif ret['comment'] == '':
                if ret['comment'] == '':
                    ret['comment'] = 'The property {0} is was not updated to {1}!'.format(property, value)
        else:
            ret['result'] = True
            ret['comment'] = 'The property {0} is already set to {1}.'.format(property, value)
    else:
        ## zone does not exist
        ret['result'] = False
        ret['comment'] = 'The zone {0} is not in the configured, installed, or booted state.'.format(name)

    return ret


def property_absent(name, property):
    '''
    Ensure property is absent

    name : string
        name of the zone
    property : string
        name of property

    .. note::
        This does a zoneacfg clear call. So the property may be reset to a default value!
        Does has the side effect of always having to be called.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)
        if property in zonecfg:
            if __opts__['test']:
                ret['result'] = True
            else:
                # clear property
                zonecfg_res = __salt__['zonecfg.clear_property'](name, property)
                zonecfg_new = __salt__['zonecfg.info'](name, show_all=True)
                ret['result'] = zonecfg_res['status']
                if 'messages' in zonecfg_res:
                    ret['comment'] = zonecfg_res['message']
            if ret['result']:
                if property not in zonecfg_new:
                    ret['changes'][property] = None
                elif zonecfg[property] != zonecfg_new[property]:
                    ret['changes'][property] = zonecfg_new[property]
                if ret['comment'] == '':
                    ret['comment'] = 'The property {0} was cleared!'.format(property)
            elif ret['comment'] == '':
                if ret['comment'] == '':
                    ret['comment'] = 'The property {0} did not get cleared!'.format(property)
        else:
            ret['result'] = True
            ret['comment'] = 'The property {0} does not exist!'.format(property)
    else:
        ## zone does not exist
        ret['result'] = False
        ret['comment'] = 'The zone {0} is not in the configured, installed, or booted state.'.format(name)

    return ret


def resource_present(name, resource_type, resource_selector_property, resource_selector_value, **kwargs):
    '''
    Ensure resource exists with provided properties

    name : string
        name of the zone
    resource_type : string
        type of resource
    resource_selector_property : string
        unique resource identifier
    resource_selector_value : string
        value for resource selection
    **kwargs : string|int|...
        resource properties

    .. warning::
        Both resource_selector_property and resource_selector_value must be provided, some properties
        like ```name``` are already reserved by salt in there states.

    .. note::
        You can set both resource_selector_property and resource_selector_value to None for
        resources that do not require them.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # sanitize input
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    resource_selector_value = _parse_value(resource_selector_value)
    for k, v in kwargs.items():
        kwargs[k] = _parse_value(kwargs[k])

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)

        ## update kwargs
        zonecfg_kwargs = {}
        zonecfg_kwargs.update(kwargs)
        zonecfg_kwargs['zone'] = name
        zonecfg_kwargs['resource_type'] = resource_type
        zonecfg_kwargs['resource_selector'] = resource_selector_property
        if resource_selector_property:
            zonecfg_kwargs[resource_selector_property] = resource_selector_value

        ## check update or add
        if resource_type in zonecfg:
            for resource in zonecfg[resource_type]:
                if not resource_selector_property or resource[resource_selector_property] == resource_selector_value:
                    ret['result'] = True
                    if resource_selector_property:
                        ret['comment'] = 'the {0} resource {1} is up to date.'.format(
                            resource_type,
                            resource_selector_value,
                        )
                    else:
                        ret['comment'] = 'the {0} resource is up to date.'.format(
                            resource_type,
                        )

                    ## check if update reauired
                    for key in kwargs:
                        log.debug('zone.resource_preent - key=%s value=%s current_value=%s',
                            key,
                            resource[key] if key in resource else None,
                            _parse_value(kwargs[key]),
                        )
                        # note: something odd with ncpus property, we fix it here for now
                        if key == 'ncpus' and key in kwargs:
                            kwargs[key] = '{0:.2f}'.format(float(kwargs[key]))

                        if key not in resource:
                            ret['result'] = None
                        elif resource[key] != _parse_value(kwargs[key]):
                            ret['result'] = None

                    ## do update
                    if ret['result'] is None:
                        if __opts__['test']:
                            ret['result'] = True
                        else:
                            ## update resource
                            zonecfg_res = __salt__['zonecfg.update_resource'](**zonecfg_kwargs)
                            ret['result'] = zonecfg_res['status']
                            if 'message' in zonecfg_res:
                                ret['comment'] = zonecfg_res['message']

                        if ret['result']:
                            ret['changes'][resource_type] = {}
                            if resource_selector_property:
                                ret['changes'][resource_type][resource_selector_value] = {}
                            for key in kwargs if ret['result'] else []:
                                if resource_selector_property:
                                    ret['changes'][resource_type][resource_selector_value][key] = _parse_value(kwargs[key])
                                else:
                                    ret['changes'][resource_type][key] = _parse_value(kwargs[key])
                            if ret['comment'] == '':
                                if resource_selector_property:
                                    ret['comment'] = 'The {0} resource {1} was updated.'.format(
                                        resource_type,
                                        resource_selector_value,
                                    )
                                else:
                                    ret['comment'] = 'The {0} resource was updated.'.format(
                                        resource_type,
                                    )
                        elif ret['comment'] == '':
                            if resource_selector_property:
                                ret['comment'] = 'The {0} resource {1} was not updated.'.format(
                                    resource_type,
                                    resource_selector_value,
                                )
                            else:
                                ret['comment'] = 'The {0} resource was not updated.'.format(
                                    resource_type,
                                )
        if ret['result'] is None:
            ## add
            if __opts__['test']:
                ret['result'] = True
            else:
                ## add resource
                if 'resource_selector' in zonecfg_kwargs:
                    del zonecfg_kwargs['resource_selector']
                zonecfg_res = __salt__['zonecfg.add_resource'](**zonecfg_kwargs)
                ret['result'] = zonecfg_res['status']
                if 'message' in zonecfg_res:
                    ret['comment'] = zonecfg_res['message']

            if ret['result']:
                ret['changes'][resource_type] = {}
                if resource_selector_property:
                    ret['changes'][resource_type][resource_selector_value] = {}
                for key in kwargs if ret['result'] else []:
                    if resource_selector_property:
                        ret['changes'][resource_type][resource_selector_value][key] = _parse_value(kwargs[key])
                    else:
                        ret['changes'][resource_type][key] = _parse_value(kwargs[key])
                if ret['comment'] == '':
                    ret['comment'] = 'The {0} resource {1} was added.'.format(
                        resource_type,
                        resource_selector_value,
                    )
            elif ret['comment'] == '':
                ret['comment'] = 'The {0} resource {1} was not added.'.format(
                    resource_type,
                    resource_selector_value,
                )
    else:
        ## zone does not exist
        ret['result'] = False
        ret['comment'] = 'The zone {0} is not in the configured, installed, or booted state.'.format(name)

    return ret


def resource_absent(name, resource_type, resource_selector_property, resource_selector_value):
    '''
    Ensure resource is absent

    name : string
        name of the zone
    resource_type : string
        type of resource
    resource_selector_property : string
        unique resource identifier
    resource_selector_value : string
        value for resource selection

    .. warning::
        Both resource_selector_property and resource_selector_value must be provided, some properties
        like ```name``` are already reserved by salt in there states.

    .. note::
        You can set both resource_selector_property and resource_selector_value to None for
        resources that do not require them.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # sanitize input
    if resource_selector_property:
        resource_selector_value = _parse_value(resource_selector_value)
    else:
        resource_selector_value = None

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)
        if resource_type in zonecfg:
            for resource in zonecfg[resource_type]:
                if __opts__['test']:
                    ret['result'] = True
                elif not resource_selector_property:
                    zonecfg_res = __salt__['zonecfg.remove_resource'](
                        zone=name,
                        resource_type=resource_type,
                        resource_key=None,
                        resource_value=None,
                    )
                    ret['result'] = zonecfg_res['status']
                    if zonecfg_res['status']:
                        ret['changes'][resource_type] = 'removed'
                        if ret['comment'] == '':
                            ret['comment'] = 'The {0} resource was removed.'.format(
                                resource_type,
                            )
                    elif 'messages' in zonecfg_res:
                        ret['comment'] = zonecfg_res['message']
                    else:
                        ret['comment'] = 'The {0} resource was not removed.'.format(
                            resource_type,
                        )
                elif resource[resource_selector_property] == resource_selector_value:
                    zonecfg_res = __salt__['zonecfg.remove_resource'](
                        zone=name,
                        resource_type=resource_type,
                        resource_key=resource_selector_property,
                        resource_value=resource_selector_value,
                    )
                    ret['result'] = zonecfg_res['status']
                    if zonecfg_res['status']:
                        ret['changes'][resource_type] = {}
                        ret['changes'][resource_type][resource_selector_value] = 'removed'
                        if ret['comment'] == '':
                            ret['comment'] = 'The {0} resource {1} was removed.'.format(
                                resource_type,
                                resource_selector_value,
                            )
                    elif 'messages' in zonecfg_res:
                        ret['comment'] = zonecfg_res['message']
                    else:
                        ret['comment'] = 'The {0} resource {1} was not removed.'.format(
                            resource_type,
                            resource_selector_value,
                        )

        # resource already absent
        if ret['result'] is None:
            ret['result'] = True
            ret['comment'] = 'The {0} resource {1} was absent.'.format(
                resource_type,
                resource_selector_value,
            )
    else:
        ## zone does not exist
        ret['result'] = False
        ret['comment'] = 'The zone {0} is not in the configured, installed, or booted state.'.format(name)

    return ret


def booted(name, single=False):
    '''
    Ensure zone is booted

    name : string
        name of the zone
    single : boolean
        boot in single usermode

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True)
    if name in zones:
        ## zone exists
        if zones[name]['state'] == 'running':
            ## zone is running
            ret['result'] = True
            ret['comment'] = 'Zone {0} already booted'.format(name)
        else:
            ## try and boot the zone
            if not __opts__['test']:
                zoneadm_res = __salt__['zoneadm.boot'](name, single)
            if __opts__['test'] or zoneadm_res['status']:
                ret['result'] = True
                ret['changes'][name] = 'booted'
                ret['comment'] = 'Zone {0} booted'.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to boot {0}'.format(name)
    else:
        ## zone does not exist
        ret['comment'] = []
        ret['comment'].append(
            'The zone {0} is not in the installed or booted state.'.format(name)
        )
        for zone in zones:
            if zones[zone]['uuid'] == name:
                ret['comment'].append(
                    'The zone {0} has a uuid of {1}, please use the zone name instead!'.format(
                        zone,
                        name,
                    )
                )

        ret['result'] = False
        ret['comment'] = "\n".join(ret['comment'])

    return ret


def halted(name, graceful=True):
    '''
    Ensure zone is halted

    name : string
        name of the zone
    graceful : boolean
        use shutdown instead of halt if true

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True)
    if name in zones:
        ## zone exists
        if zones[name]['state'] != 'running':
            ## zone is not running
            ret['result'] = True
            ret['comment'] = 'Zone {0} already halted'.format(name)
        else:
            ## try and halt the zone
            if not __opts__['test']:
                zoneadm_res = __salt__['zoneadm.shutdown'](name) if graceful else __salt__['zoneadm.halt'](name)
            if __opts__['test'] or zoneadm_res['status']:
                ret['result'] = True
                ret['changes'][name] = 'halted'
                ret['comment'] = 'Zone {0} halted'.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to halt {0}'.format(name)
    else:
        ## zone does not exist
        ret['comment'] = []
        ret['comment'].append(
            'The zone {0} is not in the installed state.'.format(name)
        )
        for zone in zones:
            if zones[zone]['uuid'] == name:
                ret['comment'].append(
                    'The zone {0} has a uuid of {1}, please use the zone name instead!'.format(
                        zone,
                        name,
                    )
                )
        ## note: a non existing zone is not running, we do not consider this a failure
        ret['result'] = True
        ret['comment'] = "\n".join(ret['comment'])

    return ret


def export_(name, path, replace=False):
    '''
    Export a zones configuration

    name : string
        name of the zone
    path : string
        path of file to export too.
    replace : boolean
        replace the file if it exists

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        if __opts__['test']:
            ## pretend we did the correct thing
            ret['result'] = True
            ret['comment'] = 'Zone configartion for {0} exported to {1}'.format(
                name,
                path,
            )
            ret['changes'][name] = 'exported'
            if __salt__['file.file_exists'](path) and not replace:
                ret['result'] = False
                ret['changes'] = {}
                ret['comment'] = 'File {0} exists, zone configuration for {1} not exported.'.format(
                    path,
                    name,
                )
        else:
            ## export and update file
            cfg_tmp = salt.utils.files.mkstemp()
            __salt__['zonecfg.export'](name, cfg_tmp)
            if not __salt__['file.file_exists'](path):
                ## move cfg_tmp to path
                try:
                    __salt__['file.move'](cfg_tmp, path)
                except CommandExecutionError:
                    if __salt__['file.file_exists'](cfg_tmp):
                        __salt__['file.remove'](cfg_tmp)
                    ret['result'] = False
                    ret['comment'] = 'Unable to export zone configuration for {0} to {1}!'.format(
                        name,
                        path,
                    )
                else:
                    ret['result'] = True
                    ret['comment'] = 'Zone configuration for {0} was exported to {1}.'.format(
                        name,
                        path,
                    )
                    ret['changes'][name] = 'exported'
            else:
                cfg_diff = __salt__['file.get_diff'](path, cfg_tmp)
                if not cfg_diff:
                    ret['result'] = True
                    ret['comment'] = 'Zone configuration for {0} was already exported to {1}.'.format(
                        name,
                        path
                    )
                    if __salt__['file.file_exists'](cfg_tmp):
                        __salt__['file.remove'](cfg_tmp)
                else:
                    if replace:
                        try:
                            __salt__['file.move'](cfg_tmp, path)
                        except CommandExecutionError:
                            if __salt__['file.file_exists'](cfg_tmp):
                                __salt__['file.remove'](cfg_tmp)
                            ret['result'] = False
                            ret['comment'] = 'Unable to be re-export zone configuration for {0} to {1}!'.format(
                                name,
                                path,
                            )
                        else:
                            ret['result'] = True
                            ret['comment'] = 'Zone configuration for {0} was re-exported to {1}.'.format(
                                name,
                                path,
                            )
                            ret['changes'][name] = 'exported'
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Zone configuration for {0} is different from the one exported to {1}!'.format(
                            name,
                            path
                        )
                        if __salt__['file.file_exists'](cfg_tmp):
                            __salt__['file.remove'](cfg_tmp)
    else:
        ## zone does not exist
        ret['comment'] = []
        ret['comment'].append(
            'The zone {0} does not exist.'.format(name)
        )
        for zone in zones:
            if zones[zone]['uuid'] == name:
                ret['comment'].append(
                    'The zone {0} has a uuid of {1}, please use the zone name instead!'.format(
                        name,
                        path,
                    )
                )

        ret['result'] = False
        ret['comment'] = "\n".join(ret['comment'])

    return ret


def import_(name, path, mode='import', nodataset=False, brand_opts=None):
    '''
    Import a zones configuration

    name : string
        name of the zone
    path : string
        path of the configuration file to import
    mode : string
        either import, install, or attach
    nodataset : boolean
        do not create a ZFS file system
    brand_opts : boolean
        brand specific options to pass

    .. note::
        The mode argument can be set to ``import``, ``install``, or ``attach``.
        ``import``: will only import the configuration
        ``install``: will import and then try to install the zone
        ``attach``: will import and then try to attach of the zone

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name not in zones:
        if __opts__['test']:
            ret['result'] = True
            ret['comment'] = 'Zone {0} was imported from {1}.'.format(
                name,
                path,
            )
            ret['changes'][name] = 'imported'
        else:
            if __salt__['file.file_exists'](path):
                res_import = __salt__['zonecfg.import'](name, path)
                if not res_import['status']:
                    ret['result'] = False
                    ret['comment'] = 'Unable to import zone configuration for {0}!'.format(name)
                else:
                    ret['result'] = True
                    ret['changes'][name] = 'imported'
                    ret['comment'] = 'Zone {0} was imported from {1}.'.format(
                        name,
                        path,
                    )
                    if mode.lower() == 'attach':
                        res_attach = __salt__['zoneadm.attach'](name, False, brand_opts)
                        ret['result'] = res_attach['status']
                        if res_attach['status']:
                            ret['changes'][name] = 'attached'
                            ret['comment'] = 'Zone {0} was attached from {1}.'.format(
                                name,
                                path,
                            )
                        else:
                            ret['comment'] = []
                            ret['comment'].append('Failed to attach zone {0} from {1}!'.format(
                                name,
                                path,
                            ))
                            if 'message' in res_attach:
                                ret['comment'].append(res_attach['message'])
                            ret['comment'] = "\n".join(ret['comment'])
                    if mode.lower() == 'install':
                        res_install = __salt__['zoneadm.install'](name, nodataset, brand_opts)
                        ret['result'] = res_install['status']
                        if res_install['status']:
                            ret['changes'][name] = 'installed'
                            ret['comment'] = 'Zone {0} was installed from {1}.'.format(
                                name,
                                path,
                            )
                        else:
                            ret['comment'] = []
                            ret['comment'].append('Failed to install zone {0} from {1}!'.format(
                                name,
                                path,
                            ))
                            if 'message' in res_install:
                                ret['comment'].append(res_install['message'])
                            ret['comment'] = "\n".join(ret['comment'])
            else:
                ret['result'] = False
                ret['comment'] = 'The file {0} does not exists, unable to import!'.format(path)
    else:
        ## zone exist
        ret['result'] = True
        ret['comment'] = 'Zone {0} already exists, not importing configuration.'.format(name)

    return ret


def present(name, brand, zonepath, properties=None, resources=None):
    '''
    Ensure a zone with certain properties and resouces

    name : string
        name of the zone
    brand : string
        brand of the zone
    zonepath : string
        path of the zone
    properties : list of key-value pairs
        dict of properties
    resources : list of key-value pairs
        dict of resources

    .. note::
        If the zone does not exist it will not be installed.
        You can use the ```zone.installed``` state for this.

    .. note::
        Default resource selectors:
            - fs: dir
            - net: mac-addr
            - device: match
            - rctl: name
            - attr: name
            - dataset: name
            - admin: user

    .. warning::
        Properties and resource will not be removed when they
        are absent from the state!

        For properties, simple set them to ```None```.

        For resources, add the ```resource_prune``` property
        and set it to ```True```. Also specify the
        ```resource_selector_property``` if the default is not
        the one you want.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': []}

    ## sanitize defaults
    if not properties:
        properties = []
    if not resources:
        resources = []
    properties.append(OrderedDict({"brand": brand}))
    properties.append(OrderedDict({"zonepath": zonepath}))

    zones = __salt__['zoneadm.list'](installed=True, configured=True)

    ## test mode only has limited support
    if __opts__['test']:
        ret['result'] = None
        ret['comment'].append('Cannot determine of changes would happen to the zone {0}.'.format(name))

    ## create zone if needed
    if name not in zones:
        if __opts__['test']:
            ## we pretend we created the zone
            res_create = {'status': True}
            ret['comment'] = []
        else:
            ## create and install
            res_create = __salt__['zonecfg.create'](name, brand, zonepath)
        if res_create['status']:
            ret['result'] = True
            ret['changes'][name] = 'created'
            ret['comment'].append('The zone {0} was created.'.format(name))

    if not __opts__['test']:
        ret['result'] = True
        if isinstance(properties, list):
            for prop in properties:
                if not isinstance(prop, OrderedDict) or len(prop) != 1:
                    log.warning('zone.present - failed to parse property: %s', prop)
                    continue
                for key, value in prop.items():
                    res = None
                    if not value:
                        res = property_absent(name, key)
                    elif value:
                        res = property_present(name, key, value)
                    if res:
                        ret['result'] = ret['result'] if res['result'] else False
                        ret['comment'].append(res['comment'])
                        if len(res['changes']) > 0:
                            if 'property' not in ret['changes']:
                                ret['changes']['property'] = {}
                            ret['changes']['property'] = merge_dict(ret['changes']['property'], res['changes'])
        if isinstance(resources, list):
            for resource in resources:
                if not isinstance(prop, OrderedDict) or len(prop) != 1:
                    log.warning('zone.present - failed to parse resource: %s', resource)
                    continue
                for key, value in resource.items():
                    zonecfg = __salt__['zonecfg.info'](name, show_all=True)
                    resource_cfg = {}
                    resource_cfg['resource_type'] = key
                    if isinstance(value, list):
                        for respv in value:
                            resource_cfg.update(dict(respv))

                    resource_prune = False
                    resource_selector_property = None
                    if 'resource_prune' in resource_cfg:
                        resource_prune = resource_cfg['resource_prune']
                        del resource_cfg['resource_prune']
                    if 'resource_selector_property' in resource_cfg:
                        resource_selector_property = resource_cfg['resource_selector_property']
                        del resource_cfg['resource_selector_property']
                    if not resource_selector_property and key in _zonecfg_resource_default_selectors:
                        resource_selector_property = _zonecfg_resource_default_selectors[key]

                    res = None
                    if resource_prune:
                        res = resource_absent(
                            name,
                            resource_cfg['resource_type'],
                            resource_selector_property=resource_selector_property,
                            resource_selector_value=resource_cfg[resource_selector_property] if resource_selector_property else None,
                        )
                    else:
                        resource_cfg['resource_selector_property'] = resource_selector_property
                        if resource_selector_property in resource_cfg:
                            resource_cfg['resource_selector_value'] = resource_cfg[resource_selector_property]
                        else:
                            resource_cfg['resource_selector_value'] = None
                        resource_cfg['name'] = name  # we do this last because name can also be a attrib value
                        res = resource_present(**resource_cfg)
                    if res:
                        ret['result'] = ret['result'] if res['result'] else False
                        ret['comment'].append(res['comment'])
                        if len(res['changes']) > 0:
                            if 'resource' not in ret['changes']:
                                ret['changes']['resource'] = {}
                            ret['changes']['resource'] = merge_dict(ret['changes']['resource'], res['changes'])

    if isinstance(ret['comment'], list):
        ret['comment'] = "\n".join(ret['comment'])

    return ret


def absent(name, uninstall=False):
    '''
    Ensure a zone is absent

    name : string
        name of the zone
    uninstall : boolean
        when true, uninstall instead of detaching the zone first.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        if __opts__['test']:
            ret['result'] = True
            ret['changes'][name] = 'removed'
            ret['comment'] = 'Zone {0} was removed.'.format(name)
        else:
            ret['result'] = True
            if uninstall and zones[name]['state'] in ['running', 'installed']:
                res_halt = __salt__['zoneadm.halt'](name)
                res_uninstall = __salt__['zoneadm.uninstall'](name)
                ret['result'] = res_uninstall['status']
                if ret['result']:
                    ret['changes'][name] = 'uninstalled'
                    ret['comment'] = 'The zone {0} was uninstalled.'.format(name)
                else:
                    ret['comment'] = []
                    ret['comment'].append('Failed to uninstall zone {0}!'.format(name))
                    if 'message' in res_uninstall:
                        ret['comment'].append(res_uninstall['message'])
                    ret['comment'] = "\n".join(ret['comment'])
            elif zones[name]['state'] == 'installed':
                res_detach = __salt__['zoneadm.detach'](name)
                ret['result'] = res_detach['status']
                if ret['result']:
                    ret['changes'][name] = 'detached'
                    ret['comment'] = 'The zone {0} was detached.'.format(name)
                else:
                    ret['comment'] = []
                    ret['comment'].append('Failed to detach zone {0}!'.format(name))
                    if 'message' in res_detach:
                        ret['comment'].append(res_detach['message'])
                    ret['comment'] = "\n".join(ret['comment'])
            if ret['result']:
                res_delete = __salt__['zonecfg.delete'](name)
                ret['result'] = res_delete['status']
                if ret['result']:
                    ret['changes'][name] = 'deleted'
                    ret['comment'] = 'The zone {0} was delete.'.format(name)
                else:
                    ret['comment'] = []
                    ret['comment'].append('Failed to delete zone {0}!'.format(name))
                    if 'message' in res_delete:
                        ret['comment'].append(res_delete['message'])
                    ret['comment'] = "\n".join(ret['comment'])
    else:
        ret['result'] = True
        ret['comment'] = 'Zone {0} does not exist.'.format(name)

    return ret


def attached(name, force=False):
    '''
    Ensure zone is attached

    name : string
        name of the zone
    force : boolean
        force attach the zone

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        if zones[name]['state'] == 'configured':
            if __opts__['test']:
                res_attach = {'status': True}
            else:
                res_attach = __salt__['zoneadm.attach'](name, force)
            ret['result'] = res_attach['status']
            if ret['result']:
                ret['changes'][name] = 'attached'
                ret['comment'] = 'The zone {0} was attached.'.format(name)
            else:
                ret['comment'] = []
                ret['comment'].append('Failed to attach zone {0}!'.format(name))
                if 'message' in res_attach:
                    ret['comment'].append(res_attach['message'])
                ret['comment'] = "\n".join(ret['comment'])
        else:
            ret['result'] = True
            ret['comment'] = 'zone {0} already attached.'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'zone {0} is not configured!'.format(name)

    return ret


def detached(name):
    '''
    Ensure zone is detached

    name : string
        name of the zone

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        if zones[name]['state'] != 'configured':
            if __opts__['test']:
                res_detach = {'status': True}
            else:
                res_detach = __salt__['zoneadm.detach'](name)
            ret['result'] = res_detach['status']
            if ret['result']:
                ret['changes'][name] = 'detached'
                ret['comment'] = 'The zone {0} was detached.'.format(name)
            else:
                ret['comment'] = []
                ret['comment'].append('Failed to detach zone {0}!'.format(name))
                if 'message' in res_detach:
                    ret['comment'].append(res_detach['message'])
                ret['comment'] = "\n".join(ret['comment'])
        else:
            ret['result'] = True
            ret['comment'] = 'zone {0} already detached.'.format(name)
    else:
        ## note: a non existing zone is not attached, we do not consider this a failure
        ret['result'] = True
        ret['comment'] = 'zone {0} is not configured!'.format(name)

    return ret


def installed(name, nodataset=False, brand_opts=None):
    '''
    Ensure zone is installed

    name : string
        name of the zone
    nodataset : boolean
        do not create a ZFS file system
    brand_opts : boolean
        brand specific options to pass

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        if zones[name]['state'] == 'configured':
            if __opts__['test']:
                res_install = {'status': True}
            else:
                res_install = __salt__['zoneadm.install'](name, nodataset, brand_opts)
            ret['result'] = res_install['status']
            if ret['result']:
                ret['changes'][name] = 'installed'
                ret['comment'] = 'The zone {0} was installed.'.format(name)
            else:
                ret['comment'] = []
                ret['comment'].append('Failed to install zone {0}!'.format(name))
                if 'message' in res_install:
                    ret['comment'].append(res_install['message'])
                ret['comment'] = "\n".join(ret['comment'])
        else:
            ret['result'] = True
            ret['comment'] = 'zone {0} already installed.'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'zone {0} is not configured!'.format(name)

    return ret


def uninstalled(name):
    '''
    Ensure zone is uninstalled

    name : string
        name of the zone

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        if zones[name]['state'] != 'configured':
            if __opts__['test']:
                res_uninstall = {'status': True}
            else:
                res_uninstall = __salt__['zoneadm.uninstall'](name)
            ret['result'] = res_uninstall['status']
            if ret['result']:
                ret['changes'][name] = 'uninstalled'
                ret['comment'] = 'The zone {0} was uninstalled.'.format(name)
            else:
                ret['comment'] = []
                ret['comment'].append('Failed to uninstall zone {0}!'.format(name))
                if 'message' in res_uninstall:
                    ret['comment'].append(res_uninstall['message'])
                ret['comment'] = "\n".join(ret['comment'])
        else:
            ret['result'] = True
            ret['comment'] = 'zone {0} already uninstalled.'.format(name)
    else:
        ## note: a non existing zone is not installed, we do not consider this a failure
        ret['result'] = True
        ret['comment'] = 'zone {0} is not configured!'.format(name)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
