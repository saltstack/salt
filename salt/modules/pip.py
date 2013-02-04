'''
Install Python packages with pip to either the system or a virtualenv
'''

# Import python libs
import os
import logging
import shutil

# Import salt libs
import salt.utils
from salt._compat import string_types
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# It would be cool if we could use __virtual__() in this module, though, since
# pip can be installed on a virtualenv anywhere on the filesystem, there's no
# definite way to tell if pip is installed on not.

logger = logging.getLogger(__name__)  # pylint: disable-msg=C0103


def _get_pip_bin(bin_env):
    '''
    Return the pip command to call, either from a virtualenv, an argument
    passed in, or from the global modules options
    '''
    if not bin_env:
        which_result = __salt__['cmd.which_bin'](['pip2', 'pip', 'pip-python'])
        if which_result is None:
            raise CommandNotFoundError('Could not find a `pip` binary')
        return which_result

    # try to get pip bin from env
    if os.path.isdir(bin_env):
        pip_bin = os.path.join(bin_env, 'bin', 'pip')
        if os.path.isfile(pip_bin):
            return pip_bin
        raise CommandNotFoundError('Could not find a `pip` binary')

    return bin_env


def install(pkgs=None,
            requirements=None,
            env=None,
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
            install_options=None,
            runas=None,
            cwd=None,
            __env__='base'):
    '''
    Install packages with pip

    Install packages individually or from a pip requirements file. Install
    packages globally or to a virtualenv.

    pkgs
        comma separated list of packages to install
    requirements
        path to requirements
    bin_env
        path to pip bin or path to virtualenv. If doing a system install,
        and want to use a specific pip bin (pip-2.7, pip-2.6, etc..) just
        specify the pip bin you want.
        If installing into a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    env
        deprecated, use bin_env now
    log
        Log file where a complete (maximum verbosity) record will be kept
    proxy
        Specify a proxy in the form
        user:passwd@proxy.server:port. Note that the
        user:password@ is optional and required only if you
        are behind an authenticated proxy.  If you provide
        user@proxy.server:port then you will be prompted for a
        password.
    timeout
        Set the socket timeout (default 15 seconds)
    editable
        install something editable(ie git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed)
    find_links
        URL to look for packages at
    index_url
        Base URL of Python Package Index
    extra_index_url
        Extra URLs of package indexes to use in addition to ``index_url``
    no_index
        Ignore package index
    mirrors
        Specific mirror URLs to query (automatically adds --use-mirrors)
    build
        Unpack packages into ``build`` dir
    target
        Install packages into ``target`` dir
    download
        Download packages into ``download`` instead of installing them
    download_cache
        Cache downloaded packages in ``download_cache`` dir
    source
        Check out ``editable`` packages into ``source`` dir
    upgrade
        Upgrade all packages to the newest available version
    force_reinstall
        When upgrading, reinstall all packages even if they are already up-to-date.
    ignore_installed
        Ignore the installed packages (reinstalling instead)
    no_deps
        Ignore package dependencies
    no_install
        Download and unpack all packages, but don't actually install them
    no_download
        Don't download any packages, just install the ones
        already downloaded (completes an install run with
        --no-install)
    install_options
        Extra arguments to be supplied to the setup.py install
        command (use like --install-option="--install-
        scripts=/usr/local/bin").  Use multiple --install-
        option options to pass multiple options to setup.py
        install.  If you are using an option with a directory
        path, be sure to use absolute path.
    runas
        User to run pip as
    cwd
        Current working directory to run pip from


    CLI Example::

        salt '*' pip.install <package name>,<package2 name>

        salt '*' pip.install requirements=/path/to/requirements.txt

        salt '*' pip.install <package name> bin_env=/path/to/virtualenv

        salt '*' pip.install <package name> bin_env=/path/to/pip_bin

    Comlicated CLI example::

        salt '*' pip.install markdown,django editable=git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed upgrade=True no_deps=True

    '''
    # Switching from using `pip_bin` and `env` to just `bin_env`
    # cause using an env and a pip bin that's not in the env could
    # be problematic.
    # Still using the `env` variable, for backwards compatiblity sake
    # but going fwd you should specify either a pip bin or an env with
    # the `bin_env` argument and we'll take care of the rest.
    if env and not bin_env:
        bin_env = env

    cmd = '{0} install'.format(_get_pip_bin(bin_env))

    if pkgs:
        pkg = pkgs.replace(",", " ")
        cmd = '{cmd} {pkg} '.format(
            cmd=cmd, pkg=pkg)

    treq = None
    if requirements:
        if requirements.startswith('salt://'):
            # If being called from state.virtualenv, the requirements file
            # should already be cached, let's try to use that one
            req = __salt__['cp.is_cached'](requirements, __env__)
            if not req:
                # It's not cached, let's cache it.
                req = __salt__['cp.cache_file'](requirements, __env__)

            if not req:
                return {
                    'result': False,
                    'comment': (
                        'pip requirements file \'{0}\' not found'.format(
                            requirements
                        )
                    )
                }

            treq = salt.utils.mkstemp()
            shutil.copyfile(req, treq)
        else:
            treq = requirements
        cmd = '{cmd} --requirement "{requirements}" '.format(
            cmd=cmd, requirements=treq or requirements)

    if treq is not None and runas:
        logger.debug(
            'Changing ownership of requirements file \'{0}\' to '
            'user \'{1}\''.format(treq, runas)
        )
        __salt__['file.chown'](treq, runas, None)

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError('\'{0}\' is not writeable'.format(log))
        cmd = '{cmd} --log {log} '.format(
            cmd=cmd, log=log)

    if proxy:
        cmd = '{cmd} --proxy={proxy} '.format(
            cmd=cmd, proxy=proxy)

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError(
                '\'{0}\' is not a valid integer base 10.'.format(timeout)
            )
        cmd = '{cmd} --timeout={timeout} '.format(
            cmd=cmd, timeout=timeout)

    if editable:
        if editable.find('egg') == -1:
            raise Exception('You must specify an egg for this editable')
        cmd = '{0} install --editable={editable}'.format(
            _get_pip_bin(bin_env), editable=editable)

    if find_links:
        if not find_links.startswith("http://"):
            raise Exception('\'{0}\' must be a valid url'.format(find_links))
        cmd = '{cmd} --find-links={find_links}'.format(
            cmd=cmd, find_links=find_links)

    if index_url:
        if not index_url.startswith("http://"):
            raise Exception('\'{0}\' must be a valid url'.format(index_url))
        cmd = '{cmd} --index-url="{index_url}" '.format(
            cmd=cmd, index_url=index_url)

    if extra_index_url:
        if not extra_index_url.startswith("http://"):
            raise Exception(
                '\'{0}\' must be a valid url'.format(extra_index_url)
            )
        cmd = '{cmd} --extra-index-url="{extra_index_url}" '.format(
            cmd=cmd, extra_index_url=extra_index_url)

    if no_index:
        cmd = '{cmd} --no-index '.format(cmd=cmd)

    if mirrors:
        if not mirrors.startswith("http://"):
            raise Exception('\'{0}\' must be a valid url'.format(mirrors))
        cmd = '{cmd} --use-mirrors --mirrors={mirrors} '.format(
            cmd=cmd, mirrors=mirrors)

    if build:
        cmd = '{cmd} --build={build} '.format(
            cmd=cmd, build=build)

    if target:
        cmd = '{cmd} --target={target} '.format(
            cmd=cmd, target=target)

    if download:
        cmd = '{cmd} --download={download} '.format(
            cmd=cmd, download=download)

    if download_cache:
        cmd = '{cmd} --download-cache={download_cache} '.format(
            cmd=cmd, download_cache=download_cache)

    if source:
        cmd = '{cmd} --source={source} '.format(
            cmd=cmd, source=source)

    if upgrade:
        cmd = '{cmd} --upgrade '.format(cmd=cmd)

    if force_reinstall:
        cmd = '{cmd} --force-reinstall '.format(cmd=cmd)

    if ignore_installed:
        cmd = '{cmd} --ignore-installed '.format(cmd=cmd)

    if no_deps:
        cmd = '{cmd} --no-deps '.format(cmd=cmd)

    if no_install:
        cmd = '{cmd} --no-install '.format(cmd=cmd)

    if no_download:
        cmd = '{cmd} --no-download '.format(cmd=cmd)

    if install_options:
        opts = ''

        if isinstance(install_options, string_types):
            install_options = [install_options]

        for opt in install_options:
            opts += '--install-option={opt} '.format(opt=opt)

        cmd = '{cmd} {opts} '.format(cmd=cmd, opts=opts)

    try:
        result = __salt__['cmd.run_all'](cmd, runas=runas, cwd=cwd)
    finally:
        if treq and requirements.startswith('salt://'):
            try:
                os.remove(treq)
            except Exception:
                pass

    return result


def uninstall(pkgs=None,
              requirements=None,
              bin_env=None,
              log=None,
              proxy=None,
              timeout=None,
              runas=None,
              cwd=None,
              __env__='base'):
    '''
    Uninstall packages with pip

    Uninstall packages individually or from a pip requirements file. Uninstall
    packages globally or from a virtualenv.

    pkgs
        comma separated list of packages to install
    requirements
        path to requirements
    bin_env
        path to pip bin or path to virtualenv. If doing an uninstall from
        the system python and want to use a specific pip bin (pip-2.7,
        pip-2.6, etc..) just specify the pip bin you want.
        If uninstalling from a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    log
        Log file where a complete (maximum verbosity) record will be kept
    proxy
        Specify a proxy in the form
        user:passwd@proxy.server:port. Note that the
        user:password@ is optional and required only if you
        are behind an authenticated proxy.  If you provide
        user@proxy.server:port then you will be prompted for a
        password.
    timeout
        Set the socket timeout (default 15 seconds)
    runas
        User to run pip as
    cwd
        Current working directory to run pip from

    CLI Example::

        salt '*' pip.uninstall <package name>,<package2 name>

        salt '*' pip.uninstall requirements=/path/to/requirements.txt

        salt '*' pip.uninstall <package name> bin_env=/path/to/virtualenv

        salt '*' pip.uninstall <package name> bin_env=/path/to/pip_bin

    '''
    cmd = '{0} uninstall -y '.format(_get_pip_bin(bin_env))

    if pkgs:
        pkg = pkgs.replace(",", " ")
        cmd = '{cmd} {pkg} '.format(
            cmd=cmd, pkg=pkg)

    treq = None
    if requirements:
        if requirements.startswith('salt://'):
            req = __salt__['cp.cache_file'](requirements, __env__)
            treq = salt.utils.mkstemp()
            shutil.copyfile(req, treq)
        cmd = '{cmd} --requirements "{requirements}" '.format(
            cmd=cmd, requirements=treq or requirements)

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except IOError:
            raise IOError('\'{0}\' is not writeable'.format(log))
        cmd = '{cmd} --{log} '.format(
            cmd=cmd, log=log)

    if proxy:
        cmd = '{cmd} --proxy={proxy} '.format(
            cmd=cmd, proxy=proxy)

    if timeout:
        try:
            int(timeout)
        except ValueError:
            raise ValueError(
                '\'{0}\' is not a valid integer base 10.'.format(timeout)
            )
        cmd = '{cmd} --timeout={timeout} '.format(
            cmd=cmd, timeout=timeout)

    result = __salt__['cmd.run_all'](cmd, runas=runas, cwd=cwd)

    if treq and requirements.startswith('salt://'):
        try:
            os.remove(treq)
        except Exception:
            pass

    return result


def freeze(bin_env=None,
           runas=None,
           cwd=None):
    '''
    Return a list of installed packages either globally or in the specified
    virtualenv

    bin_env
        path to pip bin or path to virtualenv. If doing an uninstall from
        the system python and want to use a specific pip bin (pip-2.7,
        pip-2.6, etc..) just specify the pip bin you want.
        If uninstalling from a virtualenv, just use the path to the virtualenv
        (/home/code/path/to/virtualenv/)
    runas
        User to run pip as
    cwd
        Current working directory to run pip from

    CLI Example::

        salt '*' pip.freeze /home/code/path/to/virtualenv/
    '''

    pip_bin = _get_pip_bin(bin_env)

    activate = os.path.join(os.path.dirname(pip_bin), 'activate')
    if not os.path.isfile(activate):
        raise CommandExecutionError(
            "Could not find the path to the virtualenv's 'activate' binary"
        )

    # We use dot(.) instead of source because it's apparently the better and/or
    # more supported way to source files on the various "major" linux shells.
    cmd = '. {0}; {1} freeze'.format(activate, pip_bin)

    result = __salt__['cmd.run_all'](cmd, runas=runas, cwd=cwd)

    if result['retcode'] > 0:
        raise CommandExecutionError(result['stderr'])

    return result['stdout'].splitlines()


def list(prefix='',
         bin_env=None,
         runas=None,
         cwd=None):
    '''
    Filter list of installed apps from ``freeze`` and check to see if
    ``prefix`` exists in the list of packages installed.

    CLI Example::

        salt '*' pip.list salt
    '''
    packages = {}

    cmd = '{0} freeze'.format(_get_pip_bin(bin_env))

    result = __salt__['cmd.run_all'](cmd, runas=runas, cwd=cwd)
    if result['retcode'] > 0:
        raise CommandExecutionError(result['stderr'])

    for line in result['stdout'].splitlines():
        if line.startswith('-e'):
            line = line.split('-e ')[1]
            line, name = line.split('#egg=')
            packages[name] = line

        elif len(line.split("==")) >= 2:
            name = line.split("==")[0]
            version = line.split("==")[1]
            if prefix:
                if line.lower().startswith(prefix.lower()):
                    packages[name] = version
            else:
                packages[name] = version
    return packages
