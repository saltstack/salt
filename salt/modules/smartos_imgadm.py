'''
Module for running imgadm command on SmartOS
'''

# Import Python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

@salt.utils.memoize
def _check_imgadm():
    '''
    Looks to see if imgadm is present on the system
    '''
    return salt.utils.which('imgadm')


def _exit_status(retcode):
    '''
    Translate exit status of imgadm
    '''
    ret = {0: 'Successful completion.',
           1: 'An error occurred.',
           2: 'Usage error.',
           3: 'Image not installed.'
          }[retcode]
    return ret


def __virtual__():
    '''
    Provides imgadm only on SmartOS
    '''
    if __grains__['os'] == "SmartOS" and _check_imgadm():
        return 'imgadm'
    return False


def version():
    '''
    Return imgadm version

    CLI Example::

        salt '*' imgadm.version
    '''
    ret = {}
    imgadm = _check_imgadm()
    cmd = '{0} --version'.format(imgadm)
    res = __salt__['cmd.run'](cmd).splitlines()
    ret = res[0].split()
    return ret[-1]


def update_installed():
    '''
    Gather info on unknown images (locally installed)

    CLI Example::

        salt '*' imgadm.update_installed()
    '''
    imgadm = _check_imgadm()
    if imgadm:
        cmd = '{0} update'.format(imgadm)
        __salt__['cmd.run'](cmd)
    return {}


def avail(search=None):
    '''
    Return a list of available images

    CLI Example::

        salt '*' imgadm.avail [percona]
    '''
    ret = {}
    imgadm = _check_imgadm()
    cmd = '{0} avail'.format(imgadm)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    if search:
        for line in res['stdout'].splitlines():
            if search in line:
                ret = line
    else:
        ret = res['stdout'].splitlines()
    return ret


def list_installed():
    '''
    Return a list of installed images

    CLI Example::

        salt '*' imgadm.list_installed
    '''
    ret = {}
    imgadm = _check_imgadm()
    cmd = '{0} list'.format(imgadm)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret = res['stdout'].splitlines()
    return ret


def show(uuid=None):
    '''
    Show manifest of a given image

    CLI Example::

        salt '*' imgadm.show e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    if not uuid:
        ret['Error'] = 'UUID parameter is mandatory'
        return ret
    imgadm = _check_imgadm()
    cmd = '{0} show {1}'.format(imgadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret[uuid] = res['stdout'].splitlines()
    return ret


def get(uuid=None):
    '''
    Return info on an installed image

    CLI Example::

        salt '*' imgadm.get e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    if not uuid:
        ret['Error'] = 'UUID parameter is mandatory'
        return ret
    imgadm = _check_imgadm()
    cmd = '{0} get {1}'.format(imgadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret[uuid] = res['stdout'].splitlines()
    return ret


def import_image(uuid=None):
    '''
    Import an image from the repository

    CLI Example::

        salt '*' imgadm.import_image e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    if not uuid:
        ret['Error'] = 'UUID parameter is mandatory'
        return ret
    imgadm = _check_imgadm()
    cmd = '{0} import {1}'.format(imgadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret[uuid] = res['stdout'].splitlines()
    return ret


def delete(uuid=None):
    '''
    Remove an installed image

    CLI Example::

        salt '*' imgadm.delete e42f8c84-bbea-11e2-b920-078fab2aab1f
    '''
    ret = {}
    if not uuid:
        ret['Error'] = 'UUID parameter is mandatory'
        return ret
    imgadm = _check_imgadm()
    cmd = '{0} delete {1}'.format(imgadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret[uuid] = res['stdout'].splitlines()
    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
