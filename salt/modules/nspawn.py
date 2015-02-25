'''
Manage nspawn containers
'''
# Import python libs
import os
import shutil
# Import Salt libs
import salt.defaults.exitcodes

__virtualname__ = 'nspawn'


def __virtual__():
    '''
    Only work on systems that have been booted with systemd
    '''
    if __grains__['kernel'] == 'Linux' and _sd_booted(__context__):
        return __virtualname__
    return False


def _sd_booted(context):
    '''
    Return True if the system was booted with systemd, False otherwise.
    '''
    # We can cache this for as long as the minion runs.
    if "systemd.sd_booted" not in context:
        try:
            # This check does the same as sd_booted() from libsystemd-daemon:
            # http://www.freedesktop.org/software/systemd/man/sd_booted.html
            if os.stat('/run/systemd/system'):
                context['systemd.sd_booted'] = True
        except OSError:
            context['systemd.sd_booted'] = False

    return context['systemd.sd_booted']


def _arch_bootstrap(name, **kwargs):
    '''
    Bootstrap an Arch Linux container
    '''
    dst = os.path.join('/var/lib/container', name)
    if os.path.exists(dst):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        return {'err': 'Container {0} already exists'.format(name)}
    cmd = 'pacstrap -c -d {0} base'.format(dst)
    os.makedirs(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
        return {'err': 'Container {0} failed to build'.format(name)}
    return ret


def _debian_bootstrap(name, **kwargs):
    '''
    Bootstrap a Debian Linux container (only unstable is currently supported)
    '''
    dst = os.path.join('/var/lib/container', name)
    if os.path.exists(dst):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        return {'err': 'Container {0} already exists'.format(name)}
    cmd = 'debootstrap --arch=amd64 unstable {0}'.format(dst)
    os.makedirs(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
        return {'err': 'Container {0} failed to build'.format(name)}
    return ret


def _fedora_bootstrap(name, **kwargs):
    '''
    Bootstrap a Fedora container
    '''
    dst = os.path.join('/var/lib/container', name)
    if not kwargs.get('version', False):
        if __grains__['os'].lower() == 'fedora':
            version = __grains__['osrelease']
        else:
            version = '21'
    else:
        version = '21'
    if os.path.exists(dst):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        return {'err': 'Container {0} already exists'.format(name)}
    cmd = 'yum -y --releasever={0} --nogpg --installroot={0} --disablerepo="*" --enablerepo=fedora install systemd passwd yum fedora-release vim-minimal'.format(dst, version)
    os.makedirs(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
        return {'err': 'Container {0} failed to build'.format(name)}
    return ret


def bootstrap(name, dist=None, version=None):
    '''
    Bootstrap a container from package servers, if dist is None the os the
    minion is running as will be created, otherwise the needed bootstrapping
    tools will need to be available on the host.

    CLI Example::

        salt '*' nspawn.bootstrap arch1
    '''
    if not dist:
        dist = __grains__['os'].lower()
    return locals['_{0}_bootstrap'.format()]


def enable(name):
    '''
    Enable a specific container

    CLI Exmaple::

        salt '*' nspawn.enable <name>
    '''
    cmd = 'systemctl enable systemd-nspawn@{0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcode.EX_UNAVAILABLE
        return False
    return True


def start(name):
    '''
    Start the named container

    CLI Example::

        salt '*' nspawn.start <name>
    '''
    cmd = 'systemctl start systemd-nspawn@{0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcode.EX_UNAVAILABLE
        return False
    return True
