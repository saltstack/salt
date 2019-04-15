# -*- coding: utf-8 -*-
'''
Module for running imgadm command on SmartOS
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import logging

# Import Salt libs
import salt.utils.json
import salt.utils.path
import salt.utils.platform

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    'list_installed': 'list',
    'update_installed': 'update',
    'import_image': 'import'
}

# Define the module's virtual name
__virtualname__ = 'imgadm'


def _exit_status(retcode):
    '''
    Translate exit status of imgadm
    '''
    ret = {0: 'Successful completion.',
           1: 'An error occurred.',
           2: 'Usage error.',
           3: 'Image not installed.'}[retcode]
    return ret


def _parse_image_meta(image=None, detail=False):
    if not image:
        return {}

    if detail:
        return {
            'name': image['manifest']['name'],
            'version': image['manifest']['version'],
            'os': image['manifest']['os'],
            'description': image['manifest']['description'],
            'published': image['manifest']['published_at'],
            'source': image['source']
        }
    else:
        return '{name}@{version} [{date}]'.format(
                name=image['manifest']['name'],
                version=image['manifest']['version'],
                date=image['manifest']['published_at'],
            )


def __virtual__():
    '''
    Provides imgadm only on SmartOS
    '''
    if salt.utils.platform.is_smartos_globalzone() and \
            salt.utils.path.which('imgadm'):
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded on SmartOS compute nodes'.format(
            __virtualname__
        )
    )


def version():
    '''
    Return imgadm version

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.version
    '''
    ret = {}
    cmd = 'imgadm --version'
    res = __salt__['cmd.run'](cmd).splitlines()
    ret = res[0].split()
    return ret[-1]


def update_installed(uuid=''):
    '''
    Gather info on unknown image(s) (locally installed)

    uuid : string
        optional uuid of image

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.update [uuid]
    '''
    cmd = 'imgadm update {0}'.format(uuid).rstrip()
    __salt__['cmd.run'](cmd)
    return {}


def avail(search=None, verbose=False):
    '''
    Return a list of available images

    search : string
        search keyword
    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.avail [percona]
        salt '*' imgadm.avail verbose=True
    '''
    ret = {}
    cmd = 'imgadm avail -j'
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret

    for image in salt.utils.json.loads(res['stdout']):
        if image['manifest']['disabled'] or not image['manifest']['public']:
            continue
        if search and search not in image['manifest']['name']:
            # we skip if we are searching but don't have a match
            continue
        result[image['manifest']['uuid']] = _parse_image_meta(image, verbose)

    return result


def list_installed(verbose=False):
    '''
    Return a list of installed images

    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.list [verbose=True]
    '''
    ret = {}
    cmd = 'imgadm list -j'
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret

    for image in salt.utils.json.loads(res['stdout']):
        result[image['manifest']['uuid']] = _parse_image_meta(image, verbose)

    return result


def show(uuid):
    '''
    Show manifest of a given image

    uuid : string
        uuid of image

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.show e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    cmd = 'imgadm show {0}'.format(uuid)
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret = salt.utils.json.loads(res['stdout'])
    return ret


def get(uuid):
    '''
    Return info on an installed image

    uuid : string
        uuid of image

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.get e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    cmd = 'imgadm get {0}'.format(uuid)
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret = salt.utils.json.loads(res['stdout'])
    return ret


def import_image(uuid, verbose=False):
    '''
    Import an image from the repository

    uuid : string
        uuid to import
    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.import e42f8c84-bbea-11e2-b920-078fab2aab1f [verbose=True]
    '''
    ret = {}
    cmd = 'imgadm import {0}'.format(uuid)
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret

    return {uuid: _parse_image_meta(get(uuid), verbose)}


def delete(uuid):
    '''
    Remove an installed image

    uuid : string
        Specifies uuid to import

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.delete e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    cmd = 'imgadm delete {0}'.format(uuid)
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    # output: Deleted image d5b3865c-0804-11e5-be21-dbc4ce844ddc
    result = []
    for image in res['stdout'].splitlines():
        image = [var for var in image.split(" ") if var]
        result.append(image[2])

    return result


def vacuum(verbose=False):
    '''
    Remove unused images

    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.vacuum [verbose=True]
    '''
    ret = {}
    cmd = 'imgadm vacuum -f'
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    # output: Deleted image d5b3865c-0804-11e5-be21-dbc4ce844ddc (lx-centos-6@20150601)
    result = {}
    for image in res['stdout'].splitlines():
        image = [var for var in image.split(" ") if var]
        result[image[2]] = {
            'name': image[3][1:image[3].index('@')],
            'version': image[3][image[3].index('@')+1:-1]
        }
    if verbose:
        return result
    else:
        return list(result.keys())


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
