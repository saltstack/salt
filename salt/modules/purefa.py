# -*- coding: utf-8 -*-

##
# Copyright 2017 Pure Storage Inc
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''

Management of Pure Storage FlashArray

Installation Prerequisites
--------------------------
- You will need the ``purestorage`` python package in your python installation
  path that is running salt.

  .. code-block:: bash

      pip install purestorage

- Configure Pure Storage FlashArray authentication. Use one of the following
  three methods.

  1) From the minion config

  .. code-block:: yaml

        pure_tags:
          fa:
            san_ip: management vip or hostname for the FlashArray
            api_token: A valid api token for the FlashArray being managed

  2) From environment (PUREFA_IP and PUREFA_API)
  3) From the pillar (PUREFA_IP and PUREFA_API)

:maintainer: Simon Dodsley (simon@purestorage.com)
:maturity: new
:requires: purestorage
:platform: all

.. versionadded:: 2018.3.0

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import platform
from datetime import datetime

# Import Salt libs
from salt.ext import six
from salt.exceptions import CommandExecutionError

# Import 3rd party modules
try:
    import purestorage
    HAS_PURESTORAGE = True
except ImportError:
    HAS_PURESTORAGE = False

__docformat__ = 'restructuredtext en'

VERSION = '1.0.0'
USER_AGENT_BASE = 'Salt'

__virtualname__ = 'purefa'

# Default symbols to use for passwords. Avoids visually confusing characters.
# ~6 bits per symbol
DEFAULT_PASSWORD_SYMBOLS = ('23456789',  # Removed: 0,1
                            'ABCDEFGHJKLMNPQRSTUVWXYZ',   # Removed: I, O
                            'abcdefghijkmnopqrstuvwxyz')  # Removed: l


def __virtual__():
    '''
    Determine whether or not to load this module
    '''
    if HAS_PURESTORAGE:
        return __virtualname__
    return (False, 'purefa execution module not loaded: purestorage python library not available.')


def _get_system():
    '''
    Get Pure Storage FlashArray configuration

    1) From the minion config
        pure_tags:
          fa:
            san_ip: management vip or hostname for the FlashArray
            api_token: A valid api token for the FlashArray being managed
    2) From environment (PUREFA_IP and PUREFA_API)
    3) From the pillar (PUREFA_IP and PUREFA_API)

  '''
    agent = {'base': USER_AGENT_BASE,
             'class': __name__,
             'version': VERSION,
             'platform': platform.platform()
             }

    user_agent = '{base} {class}/{version} ({platform})'.format(**agent)

    try:
        array = __opts__['pure_tags']['fa'].get('san_ip')
        api = __opts__['pure_tags']['fa'].get('api_token')
        if array and api:
            system = purestorage.FlashArray(array, api_token=api, user_agent=user_agent)
    except (KeyError, NameError, TypeError):
        try:
            san_ip = os.environ.get('PUREFA_IP')
            api_token = os.environ.get('PUREFA_API')
            system = purestorage.FlashArray(san_ip,
                                            api_token=api_token,
                                            user_agent=user_agent)
        except (ValueError, KeyError, NameError):
            try:
                system = purestorage.FlashArray(__pillar__['PUREFA_IP'],
                                                api_token=__pillar__['PUREFA_API'],
                                                user_agent=user_agent)
            except (KeyError, NameError):
                raise CommandExecutionError('No Pure Storage FlashArray credentials found.')

    try:
        system.get()
    except Exception:
        raise CommandExecutionError('Pure Storage FlashArray authentication failed.')
    return system


def _get_volume(name, array):
    '''Private function to check volume'''
    try:
        return array.get_volume(name)
    except purestorage.PureError:
        return None


def _get_snapshot(name, suffix, array):
    '''Private function to check snapshot'''
    snapshot = name + '.' + suffix
    try:
        for snap in array.get_volume(name, snap=True):
            if snap['name'] == snapshot:
                return snapshot
    except purestorage.PureError:
        return None


def _get_deleted_volume(name, array):
    '''Private function to check deleted volume'''
    try:
        return array.get_volume(name, pending='true')
    except purestorage.PureError:
        return None


def _get_pgroup(name, array):
    '''Private function to check protection group'''
    pgroup = None
    for temp in array.list_pgroups():
        if temp['name'] == name:
            pgroup = temp
            break
    return pgroup


def _get_deleted_pgroup(name, array):
    '''Private function to check deleted protection group'''
    try:
        return array.get_pgroup(name, pending='true')
    except purestorage.PureError:
        return None


def _get_hgroup(name, array):
    '''Private function to check hostgroup'''
    hostgroup = None
    for temp in array.list_hgroups():
        if temp['name'] == name:
            hostgroup = temp
            break
    return hostgroup


def _get_host(name, array):
    '''Private function to check host'''
    host = None
    for temp in array.list_hosts():
        if temp['name'] == name:
            host = temp
            break
    return host


def snap_create(name, suffix=None):
    '''

    Create a volume snapshot on a Pure Storage FlashArray.

    Will return False is volume selected to snap does not exist.

    .. versionadded:: 2018.3.0

    name : string
        name of volume to snapshot
    suffix : string
        if specificed forces snapshot name suffix. If not specified defaults to timestamp.

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.snap_create foo
        salt '*' purefa.snap_create foo suffix=bar

    '''
    array = _get_system()
    if suffix is None:
        suffix = 'snap-' + six.text_type((datetime.utcnow() - datetime(1970, 1, 1, 0, 0, 0, 0)).total_seconds())
        suffix = suffix.replace('.', '')
    if _get_volume(name, array) is not None:
        try:
            array.create_snapshot(name, suffix=suffix)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def snap_delete(name, suffix=None, eradicate=False):
    '''

    Delete a volume snapshot on a Pure Storage FlashArray.

    Will return False if selected snapshot does not exist.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    suffix : string
        name of snapshot
    eradicate : boolean
        Eradicate snapshot after deletion if True. Default is False

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.snap_delete foo suffix=snap eradicate=True

    '''
    array = _get_system()
    if _get_snapshot(name, suffix, array) is not None:
        try:
            snapname = name + '.' + suffix
            array.destroy_volume(snapname)
        except purestorage.PureError:
            return False
        if eradicate is True:
            try:
                array.eradicate_volume(snapname)
                return True
            except purestorage.PureError:
                return False
        else:
            return True
    else:
        return False


def snap_eradicate(name, suffix=None):
    '''

    Eradicate a deleted volume snapshot on a Pure Storage FlashArray.

    Will return False if snapshot is not in a deleted state.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    suffix : string
        name of snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.snap_eradicate foo suffix=snap

    '''
    array = _get_system()
    if _get_snapshot(name, suffix, array) is not None:
        snapname = name + '.' + suffix
        try:
            array.eradicate_volume(snapname)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def volume_create(name, size=None):
    '''

    Create a volume on a Pure Storage FlashArray.

    Will return False if volume already exists.

    .. versionadded:: 2018.3.0

    name : string
        name of volume (truncated to 63 characters)
    size : string
        if specificed capacity of volume. If not specified default to 1G.
        Refer to Pure Storage documentation for formatting rules.

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_create foo
        salt '*' purefa.volume_create foo size=10T

    '''
    if len(name) > 63:
        name = name[0:63]
    array = _get_system()
    if _get_volume(name, array) is None:
        if size is None:
            size = '1G'
        try:
            array.create_volume(name, size)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def volume_delete(name, eradicate=False):
    '''

    Delete a volume on a Pure Storage FlashArray.

    Will return False if volume doesn't exist is already in a deleted state.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    eradicate : boolean
        Eradicate volume after deletion if True. Default is False

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_delete foo eradicate=True

    '''
    array = _get_system()
    if _get_volume(name, array) is not None:
        try:
            array.destroy_volume(name)
        except purestorage.PureError:
            return False
        if eradicate is True:
            try:
                array.eradicate_volume(name)
                return True
            except purestorage.PureError:
                return False
        else:
            return True
    else:
        return False


def volume_eradicate(name):
    '''

    Eradicate a deleted volume on a Pure Storage FlashArray.

    Will return False is volume is not in a deleted state.

    .. versionadded:: 2018.3.0

    name : string
        name of volume

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_eradicate foo

    '''
    array = _get_system()
    if _get_deleted_volume(name, array) is not None:
        try:
            array.eradicate_volume(name)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def volume_extend(name, size):
    '''

    Extend an existing volume on a Pure Storage FlashArray.

    Will return False if new size is less than or equal to existing size.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    size : string
        New capacity of volume.
        Refer to Pure Storage documentation for formatting rules.

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_extend foo 10T

    '''
    array = _get_system()
    vol = _get_volume(name, array)
    if vol is not None:
        if __utils__['stringutils.human_to_bytes'](size) > vol['size']:
            try:
                array.extend_volume(name, size)
                return True
            except purestorage.PureError:
                return False
        else:
            return False
    else:
        return False


def snap_volume_create(name, target, overwrite=False):
    '''

    Create R/W volume from snapshot on a Pure Storage FlashArray.

    Will return False if target volume already exists and
    overwrite is not specified, or selected snapshot doesn't exist.

    .. versionadded:: 2018.3.0

    name : string
        name of volume snapshot
    target : string
        name of clone volume
    overwrite : boolean
        overwrite clone if already exists (default: False)

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.snap_volume_create foo.bar clone overwrite=True

    '''
    array = _get_system()
    source, suffix = name.split('.')
    if _get_snapshot(source, suffix, array) is not None:
        if _get_volume(target, array) is None:
            try:
                array.copy_volume(name, target)
                return True
            except purestorage.PureError:
                return False
        else:
            if overwrite:
                try:
                    array.copy_volume(name, target, overwrite=overwrite)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
    else:
        return False


def volume_clone(name, target, overwrite=False):
    '''

    Clone an existing volume on a Pure Storage FlashArray.

    Will return False if source volume doesn't exist, or
    target volume already exists and overwrite not specified.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    target : string
        name of clone volume
    overwrite : boolean
        overwrite clone if already exists (default: False)

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_clone foo bar overwrite=True

    '''
    array = _get_system()
    if _get_volume(name, array) is not None:
        if _get_volume(target, array) is None:
            try:
                array.copy_volume(name, target)
                return True
            except purestorage.PureError:
                return False
        else:
            if overwrite:
                try:
                    array.copy_volume(name, target, overwrite=overwrite)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
    else:
        return False


def volume_attach(name, host):
    '''

    Attach a volume to a host on a Pure Storage FlashArray.

    Host and volume must exist or else will return False.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    host : string
        name of host

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_attach foo bar

    '''
    array = _get_system()
    if _get_volume(name, array) is not None and _get_host(host, array) is not None:
        try:
            array.connect_host(host, name)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def volume_detach(name, host):
    '''

    Detach a volume from a host on a Pure Storage FlashArray.

    Will return False if either host or volume do not exist, or
    if selected volume isn't already connected to the host.

    .. versionadded:: 2018.3.0

    name : string
        name of volume
    host : string
        name of host

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.volume_detach foo bar

    '''
    array = _get_system()
    if _get_volume(name, array) is None or _get_host(host, array) is None:
        return False
    elif _get_volume(name, array) is not None and _get_host(host, array) is not None:
        try:
            array.disconnect_host(host, name)
            return True
        except purestorage.PureError:
            return False


def host_create(name, iqn=None, wwn=None):
    '''

    Add a host on a Pure Storage FlashArray.

    Will return False if host already exists, or the iSCSI or
    Fibre Channel parameters are not in a valid format.
    See Pure Storage FlashArray documentation.

    .. versionadded:: 2018.3.0

    name : string
        name of host (truncated to 63 characters)
    iqn : string
        iSCSI IQN of host
    wwn : string
        Fibre Channel WWN of host

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.host_create foo iqn='<Valid iSCSI IQN>' wwn='<Valid WWN>'

    '''
    array = _get_system()
    if len(name) > 63:
        name = name[0:63]
    if _get_host(name, array) is None:
        try:
            array.create_host(name)
        except purestorage.PureError:
            return False
        if iqn is not None:
            try:
                array.set_host(name, addiqnlist=[iqn])
            except purestorage.PureError:
                array.delete_host(name)
                return False
        if wwn is not None:
            try:
                array.set_host(name, addwwnlist=[wwn])
            except purestorage.PureError:
                array.delete_host(name)
                return False
    else:
        return False

    return True


def host_update(name, iqn=None, wwn=None):
    '''

    Update a hosts port definitions on a Pure Storage FlashArray.

    Will return False if new port definitions are already in use
    by another host, or are not in a valid format.
    See Pure Storage FlashArray documentation.

    .. versionadded:: 2018.3.0

    name : string
        name of host
    iqn : string
        Additional iSCSI IQN of host
    wwn : string
        Additional Fibre Channel WWN of host

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.host_update foo iqn='<Valid iSCSI IQN>' wwn='<Valid WWN>'

    '''
    array = _get_system()
    if _get_host(name, array) is not None:
        if iqn is not None:
            try:
                array.set_host(name, addiqnlist=[iqn])
            except purestorage.PureError:
                return False
        if wwn is not None:
            try:
                array.set_host(name, addwwnlist=[wwn])
            except purestorage.PureError:
                return False
        return True
    else:
        return False


def host_delete(name):
    '''

    Delete a host on a Pure Storage FlashArray (detaches all volumes).

    Will return False if the host doesn't exist.

    .. versionadded:: 2018.3.0

    name : string
        name of host

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.host_delete foo

    '''
    array = _get_system()
    if _get_host(name, array) is not None:
        for vol in array.list_host_connections(name):
            try:
                array.disconnect_host(name, vol['vol'])
            except purestorage.PureError:
                return False
        try:
            array.delete_host(name)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def hg_create(name, host=None, volume=None):
    '''

    Create a hostgroup on a Pure Storage FlashArray.

    Will return False if hostgroup already exists, or if
    named host or volume do not exist.

    .. versionadded:: 2018.3.0

    name : string
        name of hostgroup (truncated to 63 characters)
    host  : string
         name of host to add to hostgroup
    volume : string
         name of volume to add to hostgroup

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.hg_create foo host=bar volume=vol

    '''
    array = _get_system()
    if len(name) > 63:
        name = name[0:63]
    if _get_hgroup(name, array) is None:
        try:
            array.create_hgroup(name)
        except purestorage.PureError:
            return False
        if host is not None:
            if _get_host(host, array):
                try:
                    array.set_hgroup(name, addhostlist=[host])
                except purestorage.PureError:
                    return False
            else:
                hg_delete(name)
                return False
        if volume is not None:
            if _get_volume(volume, array):
                try:
                    array.connect_hgroup(name, volume)
                except purestorage.PureError:
                    hg_delete(name)
                    return False
            else:
                hg_delete(name)
                return False
        return True
    else:
        return False


def hg_update(name, host=None, volume=None):
    '''

    Adds entries to a hostgroup on a Pure Storage FlashArray.

    Will return False is hostgroup doesn't exist, or host
    or volume do not exist.

    .. versionadded:: 2018.3.0

    name : string
        name of hostgroup
    host  : string
         name of host to add to hostgroup
    volume : string
         name of volume to add to hostgroup

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.hg_update foo host=bar volume=vol

    '''
    array = _get_system()
    if _get_hgroup(name, array) is not None:
        if host is not None:
            if _get_host(host, array):
                try:
                    array.set_hgroup(name, addhostlist=[host])
                except purestorage.PureError:
                    return False
            else:
                return False
        if volume is not None:
            if _get_volume(volume, array):
                try:
                    array.connect_hgroup(name, volume)
                except purestorage.PureError:
                    return False
            else:
                return False
        return True
    else:
        return False


def hg_delete(name):
    '''

    Delete a hostgroup on a Pure Storage FlashArray (removes all volumes and hosts).

    Will return False is hostgroup is already in a deleted state.

    .. versionadded:: 2018.3.0

    name : string
        name of hostgroup

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.hg_delete foo

    '''
    array = _get_system()
    if _get_hgroup(name, array) is not None:
        for vol in array.list_hgroup_connections(name):
            try:
                array.disconnect_hgroup(name, vol['vol'])
            except purestorage.PureError:
                return False
        host = array.get_hgroup(name)
        try:
            array.set_hgroup(name, remhostlist=host['hosts'])
            array.delete_hgroup(name)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def hg_remove(name, volume=None, host=None):
    '''

    Remove a host and/or volume from a hostgroup on a Pure Storage FlashArray.

    Will return False is hostgroup does not exist, or named host or volume are
    not in the hostgroup.

    .. versionadded:: 2018.3.0

    name : string
        name of hostgroup
    volume : string
       name of volume to remove from hostgroup
    host : string
       name of host to remove from hostgroup

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.hg_remove foo volume=test host=bar

    '''
    array = _get_system()
    if _get_hgroup(name, array) is not None:
        if volume is not None:
            if _get_volume(volume, array):
                for temp in array.list_hgroup_connections(name):
                    if temp['vol'] == volume:
                        try:
                            array.disconnect_hgroup(name, volume)
                            return True
                        except purestorage.PureError:
                            return False
                return False
            else:
                return False
        if host is not None:
            if _get_host(host, array):
                temp = _get_host(host, array)
                if temp['hgroup'] == name:
                    try:
                        array.set_hgroup(name, remhostlist=[host])
                        return True
                    except purestorage.PureError:
                        return False
                else:
                    return False
            else:
                return False
        if host is None and volume is None:
            return False
    else:
        return False


def pg_create(name, hostgroup=None, host=None, volume=None, enabled=True):
    '''

    Create a protection group on a Pure Storage FlashArray.

    Will return False is the following cases:
       * Protection Grop already exists
       * Protection Group in a deleted state
       * More than one type is specified - protection groups are for only
         hostgroups, hosts or volumes
       * Named type for protection group does not exist

    .. versionadded:: 2018.3.0

    name : string
        name of protection group
    hostgroup  : string
         name of hostgroup to add to protection group
    host  : string
         name of host to add to protection group
    volume : string
         name of volume to add to protection group

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.pg_create foo [hostgroup=foo | host=bar | volume=vol] enabled=[true | false]

    '''
    array = _get_system()
    if hostgroup is None and host is None and volume is None:
        if _get_pgroup(name, array) is None:
            try:
                array.create_pgroup(name)
            except purestorage.PureError:
                return False
            try:
                array.set_pgroup(name, snap_enabled=enabled)
                return True
            except purestorage.PureError:
                pg_delete(name)
                return False
        else:
            return False
    elif __utils__['value.xor'](hostgroup, host, volume):
        if _get_pgroup(name, array) is None:
            try:
                array.create_pgroup(name)
            except purestorage.PureError:
                return False
            try:
                array.set_pgroup(name, snap_enabled=enabled)
            except purestorage.PureError:
                pg_delete(name)
                return False
            if hostgroup is not None:
                if _get_hgroup(hostgroup, array) is not None:
                    try:
                        array.set_pgroup(name, addhgrouplist=[hostgroup])
                        return True
                    except purestorage.PureError:
                        pg_delete(name)
                        return False
                else:
                    pg_delete(name)
                    return False
            elif host is not None:
                if _get_host(host, array) is not None:
                    try:
                        array.set_pgroup(name, addhostlist=[host])
                        return True
                    except purestorage.PureError:
                        pg_delete(name)
                        return False
                else:
                    pg_delete(name)
                    return False
            elif volume is not None:
                if _get_volume(volume, array) is not None:
                    try:
                        array.set_pgroup(name, addvollist=[volume])
                        return True
                    except purestorage.PureError:
                        pg_delete(name)
                        return False
                else:
                    pg_delete(name)
                    return False
        else:
            return False
    else:
        return False


def pg_update(name, hostgroup=None, host=None, volume=None):
    '''

    Update a protection group on a Pure Storage FlashArray.

    Will return False in the following cases:
      * Protection group does not exist
      * Incorrect type selected for current protection group type
      * Specified type does not exist

    .. versionadded:: 2018.3.0

    name : string
        name of protection group
    hostgroup  : string
         name of hostgroup to add to protection group
    host  : string
         name of host to add to protection group
    volume : string
         name of volume to add to protection group

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.pg_update foo [hostgroup=foo | host=bar | volume=vol]

    '''
    array = _get_system()
    pgroup = _get_pgroup(name, array)
    if pgroup is not None:
        if hostgroup is not None and pgroup['hgroups'] is not None:
            if _get_hgroup(hostgroup, array) is not None:
                try:
                    array.add_hgroup(hostgroup, name)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
        elif host is not None and pgroup['hosts'] is not None:
            if _get_host(host, array) is not None:
                try:
                    array.add_host(host, name)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
        elif volume is not None and pgroup['volumes'] is not None:
            if _get_volume(volume, array) is not None:
                try:
                    array.add_volume(volume, name)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
        else:
            if pgroup['hgroups'] is None and pgroup['hosts'] is None and pgroup['volumes'] is None:
                if hostgroup is not None:
                    if _get_hgroup(hostgroup, array) is not None:
                        try:
                            array.set_pgroup(name, addhgrouplist=[hostgroup])
                            return True
                        except purestorage.PureError:
                            return False
                    else:
                        return False
                elif host is not None:
                    if _get_host(host, array) is not None:
                        try:
                            array.set_pgroup(name, addhostlist=[host])
                            return True
                        except purestorage.PureError:
                            return False
                    else:
                        return False
                elif volume is not None:
                    if _get_volume(volume, array) is not None:
                        try:
                            array.set_pgroup(name, addvollist=[volume])
                            return True
                        except purestorage.PureError:
                            return False
                    else:
                        return False
            else:
                return False
    else:
        return False


def pg_delete(name, eradicate=False):
    '''

    Delete a protecton group on a Pure Storage FlashArray.

    Will return False if protection group is already in a deleted state.

    .. versionadded:: 2018.3.0

    name : string
        name of protection group

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.pg_delete foo

    '''
    array = _get_system()
    if _get_pgroup(name, array) is not None:
        try:
            array.destroy_pgroup(name)
        except purestorage.PureError:
            return False
        if eradicate is True:
            try:
                array.eradicate_pgroup(name)
                return True
            except purestorage.PureError:
                return False
        else:
            return True
    else:
        return False


def pg_eradicate(name):
    '''

    Eradicate a deleted protecton group on a Pure Storage FlashArray.

    Will return False if protection group is not in a deleted state.

    .. versionadded:: 2018.3.0

    name : string
        name of protection group

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.pg_eradicate foo

    '''
    array = _get_system()
    if _get_deleted_pgroup(name, array) is not None:
        try:
            array.eradicate_pgroup(name)
            return True
        except purestorage.PureError:
            return False
    else:
        return False


def pg_remove(name, hostgroup=None, host=None, volume=None):
    '''

    Remove a hostgroup, host or volume from a protection group on a Pure Storage FlashArray.

    Will return False in the following cases:
      * Protection group does not exist
      * Specified type is not currently associated with the protection group

    .. versionadded:: 2018.3.0

    name : string
        name of hostgroup
    hostgroup  : string
         name of hostgroup to remove from protection group
    host  : string
         name of host to remove from hostgroup
    volume : string
         name of volume to remove from hostgroup

    CLI Example:

    .. code-block:: bash

        salt '*' purefa.pg_remove foo [hostgroup=bar | host=test | volume=bar]

    '''
    array = _get_system()
    pgroup = _get_pgroup(name, array)
    if pgroup is not None:
        if hostgroup is not None and pgroup['hgroups'] is not None:
            if _get_hgroup(hostgroup, array) is not None:
                try:
                    array.remove_hgroup(hostgroup, name)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
        elif host is not None and pgroup['hosts'] is not None:
            if _get_host(host, array) is not None:
                try:
                    array.remove_host(host, name)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
        elif volume is not None and pgroup['volumes'] is not None:
            if _get_volume(volume, array) is not None:
                try:
                    array.remove_volume(volume, name)
                    return True
                except purestorage.PureError:
                    return False
            else:
                return False
        else:
            return False
    else:
        return False
