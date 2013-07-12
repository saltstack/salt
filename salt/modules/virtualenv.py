'''
Create virtualenv environments
'''

# Import python libs
import os.path
import shutil

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError


__opts__ = {
    'venv_bin': 'virtualenv'
}

__pillar__ = {}


def create(path,
        venv_bin=None,
        no_site_packages=False,
        system_site_packages=False,
        distribute=False,
        pip=False,
        clear=False,
        python='',
        extra_search_dir='',
        never_download=False,
        prompt='',
        symlinks=False,
        upgrade=False,
        runas=None):
    '''
    Create a virtualenv

    path
        The path to create the virtualenv
    venv_bin : 'virtualenv'
        The name (and optionally path) of the virtualenv command. This can also
        be set globally in the minion config file as ``virtualenv.venv_bin``.
    no_site_packages : False
        Passthrough argument given to virtualenv
    system_site_packages : False
        Passthrough argument given to virtualenv or pyvenv
    distribute : False
        Install distribute after createing a virtual environment
    pip : False
        Install pip after createing a virtual environment, implies distribute=True
    clear : False
        Passthrough argument given to virtualenv or pyvenv
    python : (default)
        Passthrough argument given to virtualenv
    extra_search_dir : (default)
        Passthrough argument given to virtualenv
    never_download : (default)
        Passthrough argument given to virtualenv
    prompt : (default)
        Passthrough argument given to virtualenv
    symlinks : False
        Passthrough argument given to pyvenv
    upgrade : False
        Passthrough argument given to pyvenv
    runas : None
        Set ownership for the virtualenv

    CLI Example::

        salt '*' virtualenv.create /path/to/new/virtualenv
    '''
    if venv_bin is None:
        venv_bin = __opts__.get('venv_bin') or __pillar__.get('venv_bin')
    # raise CommandNotFoundError if venv_bin is missing
    salt.utils.check_or_die(venv_bin)

    if 'pyvenv' not in venv_bin:
        if symlinks or upgrade:
            raise CommandExecutionError('The following parameters are unsupported by virtualenv: symlinks, upgrade')
        cmd = '{venv_bin} {args} {path}'.format(
                venv_bin=venv_bin,
                args=''.join([
                    ' --no-site-packages' if no_site_packages else '',
                    ' --system-site-packages' if system_site_packages else '',
                    ' --clear' if clear else '',
                    ' --python {0}'.format(python) if python else '',
                    ' --extra-search-dir {0}'.format(extra_search_dir
                        ) if extra_search_dir else '',
                    ' --never-download' if never_download else '',
                    ' --prompt {0}'.format(prompt) if prompt else '']),
                path=path)
    else:
        if no_site_packages or python or extra_search_dir or never_download or prompt:
            raise CommandExecutionError('The following parameters are unsupported by pyvenv: no_site_packages, python, extra_search_dir, never_download, prompt')
        cmd = '{venv_bin} {args} {path}'.format(
                venv_bin=venv_bin,
                args=''.join([
                    ' --system-site-packages' if system_site_packages else '',
                    ' --symlinks' if symlinks else '',
                    ' --clear' if clear else '',
                    ' --upgrade' if upgrade else '']),
                path=path)

    ret = __salt__['cmd.run_all'](cmd, runas=runas)
    if ret['retcode'] > 0:
        return ret

    # check if distribute and pip are already installed
    if salt.utils.is_windows():
        venv_python = os.path.join(path, 'Scripts', 'python.exe')
        venv_pip = os.path.join(path, 'Scripts', 'pip.exe')
        venv_distribute = os.path.join(path, 'Scripts', 'easy_install.exe')
    else:
        venv_python = os.path.join(path, 'bin', 'python')
        venv_pip = os.path.join(path, 'bin', 'pip')
        venv_distribute = os.path.join(path, 'bin', 'easy_install')

    # install setuptools
    if (pip or distribute) and not os.path.exists(venv_distribute):
        _install_script('https://bitbucket.org/pypa/setuptools/raw/default/ez_setup.py', path, venv_python, runas, ret)

        # clear up the distribute archive which gets downloaded
        pred = lambda o: o.startswith('distribute-') and o.endswith('.tar.gz')
        files = filter(pred, os.listdir(path))
        for f in files:
            f = os.path.join(path, f)
            os.unlink(f)

    if ret['retcode'] > 0:
        return ret

    # install pip
    if pip and not os.path.exists(venv_pip):
        _install_script('https://raw.github.com/pypa/pip/master/contrib/get-pip.py', path, venv_python, runas, ret)

    return ret

def _install_script(source, cwd, python, runas, ret):
    env = 'base'
    if not salt.utils.is_windows():
        tmppath = salt.utils.mkstemp(dir=cwd)
    else:
        tmppath = __salt__['cp.cache_file'](source, env)
    if not salt.utils.is_windows():
        fn_ = __salt__['cp.cache_file'](source, env)
        shutil.copyfile(fn_, tmppath)
    if not salt.utils.is_windows():
        os.chmod(tmppath, 320)
        os.chown(tmppath, __salt__['file.user_to_uid'](runas), -1)
    _ret = __salt__['cmd.run_all']('{0} {1}'.format(python, tmppath), runas=runas, cwd=cwd, env={'VIRTUAL_ENV': cwd})
    os.remove(tmppath)

    ret['retcode'] = _ret['retcode']
    ret['stdout'] = '{0}\n{1}'.format(ret['stdout'], _ret['stdout']).strip()
    ret['stderr'] = '{0}\n{1}'.format(ret['stderr'], _ret['stderr']).strip()
