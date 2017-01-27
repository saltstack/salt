# -*- coding: utf-8 -*-
'''
Management of Solaris Zones

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.modules.zoneadm, salt.modules.zonecfg
:platform:      solaris

.. versionadded:: nitrogen

.. code-block:: yaml

    FIXME: add good example

.. note::

    TODO:
    - zone.present (test mode)
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.files
import salt.utils.atomicfile
from salt.modules.zonecfg import _parse_value
from salt.exceptions import CommandExecutionError

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
        if property in zonecfg:
            if zonecfg[property] != _parse_value(value):
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
                        ret['comment'] = 'The property {0} is was updated to {1}!'.format(property, value)
                elif ret['comment'] == '':
                    if ret['comment'] == '':
                        ret['comment'] = 'The property {0} is was not updated to {1}!'.format(property, value)
            else:
                ret['result'] = True
                ret['comment'] = 'The property {0} is already set to {1}!'.format(property, value)
        else:
            ret['result'] = False
            ret['comment'] = 'The property {0} does not exist!'.format(property)
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
                if zonecfg[property] != zonecfg_new[property]:
                    ret['changes'][property] = zonecfg_new[property]
                if ret['comment'] == '':
                    ret['comment'] = 'The property {0} was cleared!'.format(property)
            elif ret['comment'] == '':
                if ret['comment'] == '':
                    ret['comment'] = 'The property {0} did not get cleared!'.format(property)
        else:
            ret['result'] = False
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

    .. note::
        both resource_selector_property and resource_selector_value must be provided, some properties
        like ```name``` are already reserved by salt in there states.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # sanitize input
    kwargs = salt.utils.clean_kwargs(**kwargs)
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
        zonecfg_kwargs[resource_selector_property] = resource_selector_value

        ## check update or add
        if resource_type in zonecfg:
            for resource in zonecfg[resource_type]:
                if resource[resource_selector_property] == resource_selector_value:
                    ret['result'] = True
                    ret['comment'] = 'The {0} resource {1} is up to date.'.format(
                        resource_type,
                        resource_selector_value,
                    )

                    ## check if update reauired
                    for key in kwargs:
                        log.debug('key={0} value={1} current_value={2}'.format(
                            key,
                            resource[key],
                            _parse_value(kwargs[key]),
                        ))
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
                            for key in kwargs if ret['result'] else []:
                                ret['changes'][key] = _parse_value(kwargs[key])
                            if ret['comment'] == '':
                                ret['comment'] = 'The {0} resource {1} was updated.'.format(
                                    resource_type,
                                    resource_selector_value,
                                )
                        elif ret['comment'] == '':
                            ret['comment'] = 'The {0} resource {1} was not updated.'.format(
                                resource_type,
                                resource_selector_value,
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
                for key in kwargs if ret['result'] else []:
                    ret['changes'][key] = _parse_value(kwargs[key])
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

    .. note::
        both resource_selector_property and resource_selector_value must be provided, some properties
        like ```name``` are already reserved by salt in there states.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # sanitize input
    resource_selector_value = _parse_value(resource_selector_value)

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)
        if resource_type in zonecfg:
            for resource in zonecfg[resource_type]:
                if resource[resource_selector_property] == resource_selector_value:
                    if __opts__['test']:
                        ret['result'] = True
                    else:
                        zonecfg_res = __salt__['zonecfg.remove_resource'](
                            zone=name,
                            resource_type=resource_type,
                            resource_key=resource_selector_property,
                            resource_value=resource_selector_value,
                        )
                        ret['result'] = zonecfg_res['status']
                        if 'messages' in zonecfg_res:
                            ret['comment'] = zonecfg_res['message']
                    if ret['result']:
                        ret['changes'][resource_type] = {}
                        ret['changes'][resource_type][resource_selector_value] = 'removed'
                        if ret['comment'] == '':
                            ret['comment'] = 'The {0} resource {1} was removed.'.format(
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


def booted(name):
    '''
    Ensure zone is booted

    name : string
        name of the zone

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
                zoneadm_res = __salt__['zoneadm.boot'](name)
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


def halted(name):
    '''
    Ensure zone is halted

    name : string
        name of the zone

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
                zoneadm_res = __salt__['zoneadm.halt'](name)
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

        ret['result'] = False
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
            if uninstall:
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
        ret['result'] = False
        ret['comment'] = 'zone {0} is not configured!'.format(name)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
