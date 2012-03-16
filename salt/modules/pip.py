'''
Install Python packages with pip to either the system or a virtualenv
'''
__opts__ = {
    'pip_bin': 'pip',
}

import os

def _get_pip_bin(pip, env):
    '''
    Return the pip command to call, either from a virtualenv, an argument
    passed in, or from the global modules options
    '''
    if env:
        return os.path.join(env, 'bin', 'pip')
    else:
        return pip if pip else __opts__['pip_bin']

def install(packages=None,
            requirements=None,
            bin_env=None,
            log=None,
            proxy=None,
            timeout=None,
            editable=None,
            find_links=None,
            index_url=None,
            extra_index_url=None,
            no_index=False,
            mirrors=None,
            build=None,
            target=None,
            download=None,
            download_cache=None,
            source=None,
            upgrade=False,
            force_reinstall=False,
            ignore_installed=False,
            no_deps=False,
            no_install=False,
            no_download=False,
            install_options=None):
    '''
    Install packages with pip

    Install packages individually or from a pip requirements file. Install
    packages globally or to a virtualenv.

    packages 
        package(s) or requirements file
    bin_env
        path to pip bin or path to virtualenv. If doing a system install,
        and want to use a specific pip bin (pip-2.7, pip-2.6, etc..) just
        specify the pip bin you want.
        If installing into a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)

    CLI Example::

        salt '*' pip.install <package name>,<package2 name>

        salt '*' pip.install requirements=/path/to/requirements.txt

        salt '*' pip.install <package name> bin_env=/path/to/virtualenv

        salt '*' pip.install <package name> bin_env=/path/to/pip_bin
        
        salt '*' pip.install markdown,django editable=git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed upgrade=True no_deps=True
    '''

    if not bin_env:
        pip_bin = 'pip'
    else:
        # try to get pip bin from env
        if os.path.exists(os.path.join(bin_env, 'bin', 'pip')):
            pip_bin = os.path.join(bin_env, 'bin', 'pip')
        else:
            pip_bin = bin_env        
            
    cmd = '{pip_bin} install'.format(pip_bin=pip_bin)
    print cmd
    if packages:
        pkg = packages.replace(",", " ")
        cmd = '{cmd} {pkg}'.format(
            cmd=cmd, pkg=pkg)
    print cmd
    if requirements:
        cmd = '{cmd} --requirements{requirements}'.format(
            cmd=cmd, requirements=requirements)
        

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError("'%s' is not writeable" % log)
        cmd = '{cmd} --{log}'.format(
            cmd=cmd, log=log)

    if proxy:
        cmd = '{cmd} --proxy={proxy}'.format(
            cmd=cmd, proxy=proxy)

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError("'%s' is not a valid integer base 10.")
        cmd = '{cmd} --timeout={timeout}'.format(
            cmd=cmd, timeout=timeout)

    if editable:
        if editable.find('egg') == -1:
            raise Exception('You must specify an egg for this editable')
        cmd = '{cmd} --editable={editable}'.format(
            cmd=cmd, editable=editable)

    if find_links:
        if not find_links.startswith("http://"):
            raise Exception("'%s' must be a valid url" % find_links)
        cmd = '{cmd} --find_links={find_links}'.format(
            cmd=cmd, find_links=find_links)

    if index_url:
        if not index_url.startswith("http://"):
            raise Exception("'%s' must be a valid url" % index_url)
        cmd = '{cmd} --index_url={index_url}'.format(
            cmd=cmd, index_url=index_url)

    if extra_index_url:
        if not extra_index_url.startswith("http://"):
            raise Exception("'%s' must be a valid url" % extra_index_url)
        cmd = '{cmd} --extra_index_url={extra_index_url}'.format(
            cmd=cmd, extra_index_url=extra_index_url)

    if no_index:
        cmd = '{cmd} --no-index'.format(cmd=cmd)

    if mirrors:
        if not mirrors.startswith("http://"):
            raise Exception("'%s' must be a valid url" % mirrors)
        cmd = '{cmd} --use-mirrors --mirrors={mirrors}'.format(
            cmd=cmd, mirrors=mirrors)

    if build:
        cmd = '{cmd} --build={build}'.format(
            cmd=cmd, build=build)

    if target:
        cmd = '{cmd} --target={target}'.format(
            cmd=cmd, target=target)

    if download:
        cmd = '{cmd} --download={download}'.format(
            cmd=cmd, download=download)

    if download_cache:
        cmd = '{cmd} --download_cache={download_cache}'.format(
            cmd=cmd, download_cache=download_cache)

    if source:
        cmd = '{cmd} --source={source}'.format(
            cmd=cmd, source=source)

    if upgrade:
        cmd = '{cmd} --upgrade'.format(cmd=cmd)

    if force_reinstall:
        cmd = '{cmd} --force-reinstall'.format(cmd=cmd)

    if ignore_installed:
        cmd = '{cmd} --ignore-installed'.format(cmd=cmd)

    if no_deps:
        cmd = '{cmd} --no-deps'.format(cmd=cmd)

    if no_install:
        cmd = '{cmd} --no-install'.format(cmd=cmd)

    if no_download:
        cmd = '{cmd} --no-download'.format(cmd=cmd)

    if install_options:
        cmd = '{cmd} --install-options={install_options}'.format(
            cmd=cmd, install_options=install_options)

    return __salt__['cmd.run'](cmd)

def freeze(env='', pip_bin=''):
    '''
    Return a list of installed packages either globally or in the specified
    virtualenv

    env : None
        The path to a virtualenv that pip should install to. This option takes
        precendence over the ``pip_bin`` argument.
    pip_bin : 'pip'
        The name (and optionally path) of the pip command to call. This option
        will be ignored if the ``env`` argument is given since it will default
        to the pip that is installed in the virtualenv. This option can also be
        set in the minion config file as ``pip.pip_bin``.
    '''
    cmd = '{0} freeze'.format(_get_pip_bin(pip_bin, env))

    return __salt__['cmd.run'](cmd).split('\n')
