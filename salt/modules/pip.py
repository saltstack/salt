r"""
Install Python packages with pip to either the system or a virtualenv

Windows Support
===============

.. versionadded:: 2014.7.4

Salt now uses a portable python. As a result the entire pip module is now
functional on the salt installation itself. You can pip install dependencies
for your custom modules. You can even upgrade salt itself using pip. For this
to work properly, you must specify the Current Working Directory (``cwd``) and
the Pip Binary (``bin_env``) salt should use.  The variable ``pip_bin`` can be
either a virtualenv path or the path to the pip binary itself.

For example, the following command will list all software installed using pip
to your current salt environment:

.. code-block:: bat

   salt <minion> pip.list cwd='C:\salt\bin\Scripts' bin_env='C:\salt\bin\Scripts\pip.exe'

Specifying the ``cwd`` and ``bin_env`` options ensures you're modifying the
salt environment. If these are omitted, it will default to the local
installation of python. If python is not installed locally it will fail saying
it couldn't find pip.

State File Support
------------------

This functionality works in states as well. If you need to pip install colorama
with a state, for example, the following will work:

.. code-block:: yaml

   install_colorama:
     pip.installed:
       - name: colorama
       - cwd: 'C:\salt\bin\scripts'
       - bin_env: 'C:\salt\bin\scripts\pip.exe'
       - upgrade: True

Upgrading Salt using Pip
------------------------

You can now update salt using pip to any version from the 2014.7 branch
forward. Previous version require recompiling some of the dependencies which is
painful in windows.

To do this you just use pip with git to update to the version you want and then
restart the service. Here is a sample state file that upgrades salt to the head
of the 2015.5 branch:

.. code-block:: yaml

   install_salt:
     pip.installed:
       - cwd: 'C:\salt\bin\scripts'
       - bin_env: 'C:\salt\bin\scripts\pip.exe'
       - editable: git+https://github.com/saltstack/salt@2015.5#egg=salt
       - upgrade: True

   restart_service:
     service.running:
       - name: salt-minion
       - enable: True
       - watch:
         - pip: install_salt

.. note::
   If you're having problems, you might try doubling the back slashes. For
   example, cwd: 'C:\\salt\\bin\\scripts'. Sometimes python thinks the single
   back slash is an escape character.

   There is a known incompatibility between Python2 pip>=10.* and Salt <=2018.3.0.
   The issue is described here: https://github.com/saltstack/salt/issues/46163

"""

import logging
import os
import re
import shutil
import sys
import tempfile

import pkg_resources  # pylint: disable=3rd-party-module-not-gated

import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.locales
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.url
import salt.utils.versions
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# This needs to be named logger so we don't shadow it in pip.install
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Don't shadow built-in's.
__func_alias__ = {"list_": "list"}

VALID_PROTOS = ["http", "https", "ftp", "file"]

rex_pip_chain_read = re.compile(r"(?:-r\s|--requirement[=\s])(.*)\n?", re.MULTILINE)
rex_pip_reqs_comment = re.compile(r"(?:^|\s+)#.*$", re.MULTILINE)


def __virtual__():
    """
    There is no way to verify that pip is installed without inspecting the
    entire filesystem.  If it's not installed in a conventional location, the
    user is required to provide the location of pip each time it is used.
    """
    return "pip"


def _pip_bin_env(cwd, bin_env):
    """
    Binary builds need to have the 'cwd' set when using pip on Windows. This will
    set cwd if pip is being used in 'bin_env', 'cwd' is None and salt is on windows.
    """

    if salt.utils.platform.is_windows():
        if bin_env is not None and cwd is None and "pip" in os.path.basename(bin_env):
            cwd = os.path.dirname(bin_env)

    return cwd


def _clear_context(bin_env=None):
    """
    Remove the cached pip version
    """
    contextkey = "pip.version"
    if bin_env is not None:
        contextkey = "{}.{}".format(contextkey, bin_env)
    __context__.pop(contextkey, None)


def _check_bundled():
    """
    Gather run-time information to indicate if we are running from source or bundled.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return True
    return False


def _get_pip_bin(bin_env):
    """
    Locate the pip binary, either from `bin_env` as a virtualenv, as the
    executable itself, or from searching conventional filesystem locations
    """
    bundled = _check_bundled()

    if not bin_env:
        if bundled:
            logger.debug("pip: Using pip from bundled app")
            return [os.path.normpath(sys.executable), "pip"]
        else:
            logger.debug("pip: Using pip from currently-running Python")
            return [os.path.normpath(sys.executable), "-m", "pip"]

    python_bin = "python.exe" if salt.utils.platform.is_windows() else "python"

    def _search_paths(*basedirs):
        ret = []
        for path in basedirs:
            ret.extend(
                [
                    os.path.join(path, python_bin),
                    os.path.join(path, "bin", python_bin),
                    os.path.join(path, "Scripts", python_bin),
                ]
            )
        return ret

    # try to get python bin from virtualenv (i.e. bin_env)
    if os.path.isdir(bin_env):
        for bin_path in _search_paths(bin_env):
            if os.path.isfile(bin_path):
                if os.access(bin_path, os.X_OK):
                    logger.debug("pip: Found python binary: %s", bin_path)
                    return [os.path.normpath(bin_path), "-m", "pip"]
                else:
                    logger.debug(
                        "pip: Found python binary by name but it is not executable: %s",
                        bin_path,
                    )
        raise CommandNotFoundError(
            "Could not find a pip binary in virtualenv {}".format(bin_env)
        )

    # bin_env is the python or pip binary
    elif os.access(bin_env, os.X_OK):
        if os.path.isfile(bin_env):
            # If the python binary was passed, return it
            if "python" in os.path.basename(bin_env):
                return [os.path.normpath(bin_env), "-m", "pip"]
            # We have been passed a pip binary, use the pip binary.
            return [os.path.normpath(bin_env)]

        raise CommandExecutionError(
            "Could not find a pip binary within {}".format(bin_env)
        )
    else:
        raise CommandNotFoundError(
            "Access denied to {}, could not find a pip binary".format(bin_env)
        )


def _get_cached_requirements(requirements, saltenv):
    """
    Get the location of a cached requirements file; caching if necessary.
    """

    req_file, senv = salt.utils.url.parse(requirements)
    if senv:
        saltenv = senv

    if req_file not in __salt__["cp.list_master"](saltenv):
        # Requirements file does not exist in the given saltenv.
        return False

    cached_requirements = __salt__["cp.is_cached"](requirements, saltenv)
    if not cached_requirements:
        # It's not cached, let's cache it.
        cached_requirements = __salt__["cp.cache_file"](requirements, saltenv)
    # Check if the master version has changed.
    if __salt__["cp.hash_file"](requirements, saltenv) != __salt__["cp.hash_file"](
        cached_requirements, saltenv
    ):
        cached_requirements = __salt__["cp.cache_file"](requirements, saltenv)

    return cached_requirements


def _get_env_activate(bin_env):
    """
    Return the path to the activate binary
    """
    if not bin_env:
        raise CommandNotFoundError("Could not find a `activate` binary")

    if os.path.isdir(bin_env):
        if salt.utils.platform.is_windows():
            activate_bin = os.path.join(bin_env, "Scripts", "activate.bat")
        else:
            activate_bin = os.path.join(bin_env, "bin", "activate")
        if os.path.isfile(activate_bin):
            return activate_bin
    raise CommandNotFoundError("Could not find a `activate` binary")


def _find_req(link):

    logger.info("_find_req -- link = %s", link)

    with salt.utils.files.fopen(link) as fh_link:
        reqs_content = salt.utils.stringutils.to_unicode(fh_link.read())
    reqs_content = rex_pip_reqs_comment.sub("", reqs_content)  # remove comments
    child_links = rex_pip_chain_read.findall(reqs_content)

    base_path = os.path.dirname(link)
    child_links = [os.path.join(base_path, d) for d in child_links]

    return child_links


def _resolve_requirements_chain(requirements):
    """
    Return an array of requirements file paths that can be used to complete
    the no_chown==False && user != None conundrum
    """

    chain = []

    if isinstance(requirements, str):
        requirements = [requirements]

    for req_file in requirements:
        chain.append(req_file)
        chain.extend(_resolve_requirements_chain(_find_req(req_file)))

    return chain


def _process_requirements(requirements, cmd, cwd, saltenv, user):
    """
    Process the requirements argument
    """
    cleanup_requirements = []

    if requirements is not None:
        if isinstance(requirements, str):
            requirements = [r.strip() for r in requirements.split(",")]
        elif not isinstance(requirements, list):
            raise TypeError("requirements must be a string or list")

        treq = None

        for requirement in requirements:
            logger.debug("TREQ IS: %s", treq)
            if requirement.startswith("salt://"):
                cached_requirements = _get_cached_requirements(requirement, saltenv)
                if not cached_requirements:
                    ret = {
                        "result": False,
                        "comment": "pip requirements file '{}' not found".format(
                            requirement
                        ),
                    }
                    return None, ret
                requirement = cached_requirements

            if user:
                # Need to make a temporary copy since the user will, most
                # likely, not have the right permissions to read the file

                if not treq:
                    treq = tempfile.mkdtemp()

                __salt__["file.chown"](treq, user, None)
                # In Windows, just being owner of a file isn't enough. You also
                # need permissions
                if salt.utils.platform.is_windows():
                    __utils__["dacl.set_permissions"](
                        obj_name=treq, principal=user, permissions="read_execute"
                    )

                current_directory = None

                if not current_directory:
                    current_directory = os.path.abspath(os.curdir)

                logger.info(
                    "_process_requirements from directory, %s -- requirement: %s",
                    cwd,
                    requirement,
                )

                if cwd is None:
                    r = requirement
                    c = cwd

                    requirement_abspath = os.path.abspath(requirement)
                    cwd = os.path.dirname(requirement_abspath)
                    requirement = os.path.basename(requirement)

                    logger.debug(
                        "\n\tcwd: %s -> %s\n\trequirement: %s -> %s\n",
                        c,
                        cwd,
                        r,
                        requirement,
                    )

                os.chdir(cwd)

                reqs = _resolve_requirements_chain(requirement)

                os.chdir(current_directory)

                logger.info("request files: %s", reqs)

                for req_file in reqs:
                    if not os.path.isabs(req_file):
                        req_file = os.path.join(cwd, req_file)

                    logger.debug("TREQ N CWD: %s -- %s -- for %s", treq, cwd, req_file)
                    target_path = os.path.join(treq, os.path.basename(req_file))

                    logger.debug("S: %s", req_file)
                    logger.debug("T: %s", target_path)

                    target_base = os.path.dirname(target_path)

                    if not os.path.exists(target_base):
                        os.makedirs(target_base, mode=0o755)
                        __salt__["file.chown"](target_base, user, None)

                    if not os.path.exists(target_path):
                        logger.debug("Copying %s to %s", req_file, target_path)
                        __salt__["file.copy"](req_file, target_path)

                    logger.debug(
                        "Changing ownership of requirements file '%s' to user '%s'",
                        target_path,
                        user,
                    )

                    __salt__["file.chown"](target_path, user, None)

            req_args = os.path.join(treq, requirement) if treq else requirement
            cmd.extend(["--requirement", req_args])

        cleanup_requirements.append(treq)

    logger.debug("CLEANUP_REQUIREMENTS: %s", cleanup_requirements)
    return cleanup_requirements, None


def _format_env_vars(env_vars):
    ret = {}
    if env_vars:
        if isinstance(env_vars, dict):
            for key, val in env_vars.items():
                if not isinstance(key, str):
                    key = str(key)
                if not isinstance(val, str):
                    val = str(val)
                ret[key] = val
        else:
            raise CommandExecutionError(
                "env_vars {} is not a dictionary".format(env_vars)
            )
    return ret


def install(
    pkgs=None,  # pylint: disable=R0912,R0913,R0914
    requirements=None,
    bin_env=None,
    use_wheel=False,
    no_use_wheel=False,
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
    exists_action=None,
    no_deps=False,
    no_install=False,
    no_download=False,
    global_options=None,
    install_options=None,
    user=None,
    cwd=None,
    pre_releases=False,
    cert=None,
    allow_all_external=False,
    allow_external=None,
    allow_unverified=None,
    process_dependency_links=False,
    saltenv="base",
    env_vars=None,
    use_vt=False,
    trusted_host=None,
    no_cache_dir=False,
    extra_args=None,
    cache_dir=None,
    no_binary=None,
    disable_version_check=False,
    **kwargs
):
    """
    Install packages with pip

    Install packages individually or from a pip requirements file. Install
    packages globally or to a virtualenv.

    pkgs
        Comma separated list of packages to install

    requirements
        Path to requirements

    bin_env
        Path to pip (or to a virtualenv). This can be used to specify the path
        to the pip to use when more than one Python release is installed (e.g.
        ``/usr/bin/pip-2.7`` or ``/usr/bin/pip-2.6``. If a directory path is
        specified, it is assumed to be a virtualenv.

        .. note::

            For Windows, if the pip module is being used to upgrade the pip
            package, bin_env should be the path to the virtualenv or to the
            python binary that should be used.  The pip command is unable to
            upgrade itself in Windows.

    use_wheel
        Prefer wheel archives (requires pip>=1.4)

    no_use_wheel
        Force to not use wheel archives (requires pip>=1.4,<10.0.0)

    no_binary
        Force to not use binary packages (requires pip >= 7.0.0)
        Accepts either :all: to disable all binary packages, :none: to empty the set,
        or one or more package names with commas between them

    log
        Log file where a complete (maximum verbosity) record will be kept

    proxy
        Specify a proxy in the form ``user:passwd@proxy.server:port``. Note
        that the ``user:password@`` is optional and required only if you are
        behind an authenticated proxy. If you provide
        ``user@proxy.server:port`` then you will be prompted for a password.

        .. note::
            If the Minion has a globaly configured proxy - it will be used
            even if no proxy was set here. To explicitly disable proxy for pip
            you should pass ``False`` as a value.

    timeout
        Set the socket timeout (default 15 seconds)

    editable
        install something editable (e.g.
        ``git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed``)

    find_links
        URL to search for packages

    index_url
        Base URL of Python Package Index

    extra_index_url
        Extra URLs of package indexes to use in addition to ``index_url``

    no_index
        Ignore package index

    mirrors
        Specific mirror URL(s) to query (automatically adds --use-mirrors)

        .. warning::

            This option has been deprecated and removed in pip version 7.0.0.
            Please use ``index_url`` and/or ``extra_index_url`` instead.

    build
        Unpack packages into ``build`` dir

    target
        Install packages into ``target`` dir

    download
        Download packages into ``download`` instead of installing them

    download_cache | cache_dir
        Cache downloaded packages in ``download_cache`` or ``cache_dir`` dir

    source
        Check out ``editable`` packages into ``source`` dir

    upgrade
        Upgrade all packages to the newest available version

    force_reinstall
        When upgrading, reinstall all packages even if they are already
        up-to-date.

    ignore_installed
        Ignore the installed packages (reinstalling instead)

    exists_action
        Default action when a path already exists: (s)witch, (i)gnore, (w)ipe,
        (b)ackup

    no_deps
        Ignore package dependencies

    no_install
        Download and unpack all packages, but don't actually install them

    no_download
        Don't download any packages, just install the ones already downloaded
        (completes an install run with ``--no-install``)

    install_options
        Extra arguments to be supplied to the setup.py install command (e.g.
        like ``--install-option='--install-scripts=/usr/local/bin'``).  Use
        multiple --install-option options to pass multiple options to setup.py
        install. If you are using an option with a directory path, be sure to
        use absolute path.

    global_options
        Extra global options to be supplied to the setup.py call before the
        install command.

    user
        The user under which to run pip

    cwd
        Directory from which to run pip

    pre_releases
        Include pre-releases in the available versions

    cert
        Provide a path to an alternate CA bundle

    allow_all_external
        Allow the installation of all externally hosted files

    allow_external
        Allow the installation of externally hosted files (comma separated
        list)

    allow_unverified
        Allow the installation of insecure and unverifiable files (comma
        separated list)

    process_dependency_links
        Enable the processing of dependency links

    env_vars
        Set environment variables that some builds will depend on. For example,
        a Python C-module may have a Makefile that needs INCLUDE_PATH set to
        pick up a header file while compiling.  This must be in the form of a
        dictionary or a mapping.

        Example:

        .. code-block:: bash

            salt '*' pip.install django_app env_vars="{'CUSTOM_PATH': '/opt/django_app'}"

    trusted_host
        Mark this host as trusted, even though it does not have valid or any
        HTTPS.

    use_vt
        Use VT terminal emulation (see output while installing)

    no_cache_dir
        Disable the cache.

    extra_args
        pip keyword and positional arguments not yet implemented in salt

        .. code-block:: yaml

            salt '*' pip.install pandas extra_args="[{'--latest-pip-kwarg':'param'}, '--latest-pip-arg']"

        .. warning::

            If unsupported options are passed here that are not supported in a
            minion's version of pip, a `No such option error` will be thrown.

    Will be translated into the following pip command:

    .. code-block:: bash

        pip install pandas --latest-pip-kwarg param --latest-pip-arg

    disable_version_check
        Pip may periodically check PyPI to determine whether a new version of
        pip is available to download. Passing True for this option disables
        that check.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.install <package name>,<package2 name>
        salt '*' pip.install requirements=/path/to/requirements.txt
        salt '*' pip.install <package name> bin_env=/path/to/virtualenv
        salt '*' pip.install <package name> bin_env=/path/to/pip_bin

    Complicated CLI Example:

    .. code-block:: bash

        salt '*' pip.install markdown,django \
                editable=git+https://github.com/worldcompany/djangoembed.git#egg=djangoembed upgrade=True no_deps=True

    """

    cwd = _pip_bin_env(cwd, bin_env)
    cmd = _get_pip_bin(bin_env)
    cmd.append("install")

    cleanup_requirements, error = _process_requirements(
        requirements=requirements, cmd=cmd, cwd=cwd, saltenv=saltenv, user=user
    )

    if error:
        return error

    cur_version = version(bin_env, cwd, user=user)

    if use_wheel:
        min_version = "1.4"
        max_version = "9.0.3"
        too_low = salt.utils.versions.compare(
            ver1=cur_version, oper="<", ver2=min_version
        )
        too_high = salt.utils.versions.compare(
            ver1=cur_version, oper=">", ver2=max_version
        )
        if too_low or too_high:
            logger.error(
                "The --use-wheel option is only supported in pip between %s and "
                "%s. The version of pip detected is %s. This option "
                "will be ignored.",
                min_version,
                max_version,
                cur_version,
            )
        else:
            cmd.append("--use-wheel")

    if no_use_wheel:
        min_version = "1.4"
        max_version = "9.0.3"
        too_low = salt.utils.versions.compare(
            ver1=cur_version, oper="<", ver2=min_version
        )
        too_high = salt.utils.versions.compare(
            ver1=cur_version, oper=">", ver2=max_version
        )
        if too_low or too_high:
            logger.error(
                "The --no-use-wheel option is only supported in pip between %s and "
                "%s. The version of pip detected is %s. This option "
                "will be ignored.",
                min_version,
                max_version,
                cur_version,
            )
        else:
            cmd.append("--no-use-wheel")

    if no_binary:
        min_version = "7.0.0"
        too_low = salt.utils.versions.compare(
            ver1=cur_version, oper="<", ver2=min_version
        )
        if too_low:
            logger.error(
                "The --no-binary option is only supported in pip %s and "
                "newer. The version of pip detected is %s. This option "
                "will be ignored.",
                min_version,
                cur_version,
            )
        else:
            if isinstance(no_binary, list):
                no_binary = ",".join(no_binary)
            cmd.extend(["--no-binary", no_binary])

    if log:
        if os.path.isdir(log):
            raise OSError("'{}' is a directory. Use --log path_to_file".format(log))
        elif not os.access(log, os.W_OK):
            raise OSError("'{}' is not writeable".format(log))

        cmd.extend(["--log", log])

    config = __opts__
    if proxy:
        cmd.extend(["--proxy", proxy])
    # If proxy arg is set to False we won't use the global proxy even if it's set.
    elif proxy is not False and config.get("proxy_host") and config.get("proxy_port"):
        if config.get("proxy_username") and config.get("proxy_password"):
            http_proxy_url = "http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}".format(
                **config
            )
        else:
            http_proxy_url = "http://{proxy_host}:{proxy_port}".format(**config)
        cmd.extend(["--proxy", http_proxy_url])

    if timeout:
        try:
            if isinstance(timeout, float):
                # Catch floating point input, exception will be caught in
                # exception class below.
                raise ValueError("Timeout cannot be a float")
            int(timeout)
        except ValueError:
            raise ValueError(
                "'{}' is not a valid timeout, must be an integer".format(timeout)
            )
        cmd.extend(["--timeout", timeout])

    if find_links:
        if isinstance(find_links, str):
            find_links = [l.strip() for l in find_links.split(",")]

        for link in find_links:
            if not (
                salt.utils.url.validate(link, VALID_PROTOS) or os.path.exists(link)
            ):
                raise CommandExecutionError(
                    "'{}' is not a valid URL or path".format(link)
                )
            cmd.extend(["--find-links", link])

    if no_index and (index_url or extra_index_url):
        raise CommandExecutionError(
            "'no_index' and ('index_url' or 'extra_index_url') are mutually exclusive."
        )

    if index_url:
        if not salt.utils.url.validate(index_url, VALID_PROTOS):
            raise CommandExecutionError("'{}' is not a valid URL".format(index_url))
        cmd.extend(["--index-url", index_url])

    if extra_index_url:
        if not salt.utils.url.validate(extra_index_url, VALID_PROTOS):
            raise CommandExecutionError(
                "'{}' is not a valid URL".format(extra_index_url)
            )
        cmd.extend(["--extra-index-url", extra_index_url])

    if no_index:
        cmd.append("--no-index")

    if mirrors:
        # https://github.com/pypa/pip/pull/2641/files#diff-3ef137fb9ffdd400f117a565cd94c188L216
        if salt.utils.versions.compare(ver1=cur_version, oper=">=", ver2="7.0.0"):
            raise CommandExecutionError(
                "pip >= 7.0.0 does not support mirror argument:"
                " use index_url and/or extra_index_url instead"
            )

        if isinstance(mirrors, str):
            mirrors = [m.strip() for m in mirrors.split(",")]

        cmd.append("--use-mirrors")
        for mirror in mirrors:
            if not mirror.startswith("http://"):
                raise CommandExecutionError("'{}' is not a valid URL".format(mirror))
            cmd.extend(["--mirrors", mirror])

    if disable_version_check:
        cmd.extend(["--disable-pip-version-check"])

    if build:
        cmd.extend(["--build", build])

    if target:
        cmd.extend(["--target", target])

    if download:
        cmd.extend(["--download", download])

    if download_cache or cache_dir:
        cmd.extend(
            [
                "--cache-dir"
                if salt.utils.versions.compare(ver1=cur_version, oper=">=", ver2="6.0")
                else "--download-cache",
                download_cache or cache_dir,
            ]
        )

    if source:
        cmd.extend(["--source", source])

    if upgrade:
        cmd.append("--upgrade")

    if force_reinstall:
        cmd.append("--force-reinstall")

    if ignore_installed:
        cmd.append("--ignore-installed")

    if exists_action:
        if exists_action.lower() not in ("s", "i", "w", "b"):
            raise CommandExecutionError(
                "The exists_action pip option only supports the values "
                "s, i, w, and b. '{}' is not valid.".format(exists_action)
            )
        cmd.extend(["--exists-action", exists_action])

    if no_deps:
        cmd.append("--no-deps")

    if no_install:
        cmd.append("--no-install")

    if no_download:
        cmd.append("--no-download")

    if no_cache_dir:
        cmd.append("--no-cache-dir")

    if pre_releases:
        # Check the locally installed pip version
        pip_version = cur_version

        # From pip v1.4 the --pre flag is available
        if salt.utils.versions.compare(ver1=pip_version, oper=">=", ver2="1.4"):
            cmd.append("--pre")

    if cert:
        cmd.extend(["--cert", cert])

    if global_options:
        if isinstance(global_options, str):
            global_options = [go.strip() for go in global_options.split(",")]

        for opt in global_options:
            cmd.extend(["--global-option", opt])

    if install_options:
        if isinstance(install_options, str):
            install_options = [io.strip() for io in install_options.split(",")]

        for opt in install_options:
            cmd.extend(["--install-option", opt])

    if pkgs:
        if not isinstance(pkgs, list):
            try:
                pkgs = [p.strip() for p in pkgs.split(",")]
            except AttributeError:
                pkgs = [p.strip() for p in str(pkgs).split(",")]
        pkgs = salt.utils.data.stringify(salt.utils.data.decode_list(pkgs))

        # It's possible we replaced version-range commas with semicolons so
        # they would survive the previous line (in the pip.installed state).
        # Put the commas back in while making sure the names are contained in
        # quotes, this allows for proper version spec passing salt>=0.17.0
        cmd.extend([p.replace(";", ",") for p in pkgs])
    elif not any([requirements, editable]):
        # Starting with pip 10.0.0, if no packages are specified in the
        # command, it returns a retcode 1.  So instead of running the command,
        # just return the output without running pip.
        return {"retcode": 0, "stdout": "No packages to install."}

    if editable:
        egg_match = re.compile(r"(?:#|#.*?&)egg=([^&]*)")
        if isinstance(editable, str):
            editable = [e.strip() for e in editable.split(",")]

        for entry in editable:
            # Is the editable local?
            if not (entry == "." or entry.startswith(("file://", "/"))):
                match = egg_match.search(entry)

                if not match or not match.group(1):
                    # Missing #egg=theEggName
                    raise CommandExecutionError(
                        "You must specify an egg for this editable"
                    )
            cmd.extend(["--editable", entry])

    if allow_all_external:
        cmd.append("--allow-all-external")

    if allow_external:
        if isinstance(allow_external, str):
            allow_external = [p.strip() for p in allow_external.split(",")]

        for pkg in allow_external:
            cmd.extend(["--allow-external", pkg])

    if allow_unverified:
        if isinstance(allow_unverified, str):
            allow_unverified = [p.strip() for p in allow_unverified.split(",")]

        for pkg in allow_unverified:
            cmd.extend(["--allow-unverified", pkg])

    if process_dependency_links:
        cmd.append("--process-dependency-links")

    if trusted_host:
        cmd.extend(["--trusted-host", trusted_host])

    if extra_args:
        # These are arguments from the latest version of pip that
        # have not yet been implemented in salt
        for arg in extra_args:
            # It is a keyword argument
            if isinstance(arg, dict):
                # There will only ever be one item in this dictionary
                key, val = arg.popitem()
                # Don't allow any recursion into keyword arg definitions
                # Don't allow multiple definitions of a keyword
                if isinstance(val, (dict, list)):
                    raise TypeError("Too many levels in: {}".format(key))
                # This is a a normal one-to-one keyword argument
                cmd.extend([key, val])
            # It is a positional argument, append it to the list
            else:
                cmd.append(arg)

    cmd_kwargs = dict(saltenv=saltenv, use_vt=use_vt, runas=user)

    if kwargs:
        cmd_kwargs.update(kwargs)

    if env_vars:
        cmd_kwargs.setdefault("env", {}).update(_format_env_vars(env_vars))

    try:
        if cwd:
            cmd_kwargs["cwd"] = cwd

        if bin_env and os.path.isdir(bin_env):
            cmd_kwargs.setdefault("env", {})["VIRTUAL_ENV"] = bin_env

        logger.debug(
            "TRY BLOCK: end of pip.install -- cmd: %s, cmd_kwargs: %s", cmd, cmd_kwargs
        )

        return __salt__["cmd.run_all"](cmd, python_shell=False, **cmd_kwargs)
    finally:
        _clear_context(bin_env)
        for tempdir in [cr for cr in cleanup_requirements if cr is not None]:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)


def uninstall(
    pkgs=None,
    requirements=None,
    bin_env=None,
    log=None,
    proxy=None,
    timeout=None,
    user=None,
    cwd=None,
    saltenv="base",
    use_vt=False,
):
    """
    Uninstall packages individually or from a pip requirements file

    pkgs
        comma separated list of packages to install

    requirements
        Path to requirements file

    bin_env
        Path to pip (or to a virtualenv). This can be used to specify the path
        to the pip to use when more than one Python release is installed (e.g.
        ``/usr/bin/pip-2.7`` or ``/usr/bin/pip-2.6``. If a directory path is
        specified, it is assumed to be a virtualenv.

    log
        Log file where a complete (maximum verbosity) record will be kept

    proxy
        Specify a proxy in the format ``user:passwd@proxy.server:port``. Note
        that the ``user:password@`` is optional and required only if you are
        behind an authenticated proxy.  If you provide
        ``user@proxy.server:port`` then you will be prompted for a password.

        .. note::
            If the Minion has a globaly configured proxy - it will be used
            even if no proxy was set here. To explicitly disable proxy for pip
            you should pass ``False`` as a value.

    timeout
        Set the socket timeout (default 15 seconds)

    user
        The user under which to run pip

    cwd
        Directory from which to run pip

    use_vt
        Use VT terminal emulation (see output while installing)

    CLI Example:

    .. code-block:: bash

        salt '*' pip.uninstall <package name>,<package2 name>
        salt '*' pip.uninstall requirements=/path/to/requirements.txt
        salt '*' pip.uninstall <package name> bin_env=/path/to/virtualenv
        salt '*' pip.uninstall <package name> bin_env=/path/to/pip_bin
    """

    cwd = _pip_bin_env(cwd, bin_env)
    cmd = _get_pip_bin(bin_env)
    cmd.extend(["uninstall", "-y"])

    cleanup_requirements, error = _process_requirements(
        requirements=requirements, cmd=cmd, saltenv=saltenv, user=user, cwd=cwd
    )

    if error:
        return error

    if log:
        try:
            # TODO make this check if writeable
            os.path.exists(log)
        except OSError:
            raise OSError("'{}' is not writeable".format(log))

        cmd.extend(["--log", log])

    config = __opts__
    if proxy:
        cmd.extend(["--proxy", proxy])
    # If proxy arg is set to False we won't use the global proxy even if it's set.
    elif proxy is not False and config.get("proxy_host") and config.get("proxy_port"):
        if config.get("proxy_username") and config.get("proxy_password"):
            http_proxy_url = "http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}".format(
                **config
            )
        else:
            http_proxy_url = "http://{proxy_host}:{proxy_port}".format(**config)
        cmd.extend(["--proxy", http_proxy_url])

    if timeout:
        try:
            if isinstance(timeout, float):
                # Catch floating point input, exception will be caught in
                # exception class below.
                raise ValueError("Timeout cannot be a float")
            int(timeout)
        except ValueError:
            raise ValueError(
                "'{}' is not a valid timeout, must be an integer".format(timeout)
            )
        cmd.extend(["--timeout", timeout])

    if pkgs:
        if isinstance(pkgs, str):
            pkgs = [p.strip() for p in pkgs.split(",")]
        if requirements:
            for requirement in requirements:
                with salt.utils.files.fopen(requirement) as rq_:
                    for req in rq_:
                        req = salt.utils.stringutils.to_unicode(req)
                        try:
                            req_pkg, _ = req.split("==")
                            if req_pkg in pkgs:
                                pkgs.remove(req_pkg)
                        except ValueError:
                            pass
        cmd.extend(pkgs)

    cmd_kwargs = dict(
        python_shell=False, runas=user, cwd=cwd, saltenv=saltenv, use_vt=use_vt
    )
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs["env"] = {"VIRTUAL_ENV": bin_env}

    try:
        return __salt__["cmd.run_all"](cmd, **cmd_kwargs)
    finally:
        _clear_context(bin_env)
        for requirement in cleanup_requirements:
            if requirement:
                try:
                    os.remove(requirement)
                except OSError:
                    pass


def freeze(bin_env=None, user=None, cwd=None, use_vt=False, env_vars=None, **kwargs):
    """
    Return a list of installed packages either globally or in the specified
    virtualenv

    bin_env
        Path to pip (or to a virtualenv). This can be used to specify the path
        to the pip to use when more than one Python release is installed (e.g.
        ``/usr/bin/pip-2.7`` or ``/usr/bin/pip-2.6``. If a directory path is
        specified, it is assumed to be a virtualenv.

    user
        The user under which to run pip

    cwd
        Directory from which to run pip

    .. note::
        If the version of pip available is older than 8.0.3, the list will not
        include the packages ``pip``, ``wheel``, ``setuptools``, or
        ``distribute`` even if they are installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.freeze bin_env=/home/code/path/to/virtualenv
    """

    cwd = _pip_bin_env(cwd, bin_env)
    cmd = _get_pip_bin(bin_env)
    cmd.append("freeze")

    # Include pip, setuptools, distribute, wheel
    min_version = "8.0.3"
    cur_version = version(bin_env, cwd)
    if salt.utils.versions.compare(ver1=cur_version, oper="<", ver2=min_version):
        logger.warning(
            "The version of pip installed is %s, which is older than %s. "
            "The packages pip, wheel, setuptools, and distribute will not be "
            "included in the output of pip.freeze",
            cur_version,
            min_version,
        )
    else:
        cmd.append("--all")

    cmd_kwargs = dict(runas=user, cwd=cwd, use_vt=use_vt, python_shell=False)
    if kwargs:
        cmd_kwargs.update(**kwargs)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs["env"] = {"VIRTUAL_ENV": bin_env}
    if env_vars:
        cmd_kwargs.setdefault("env", {}).update(_format_env_vars(env_vars))
    result = __salt__["cmd.run_all"](cmd, **cmd_kwargs)

    if result["retcode"]:
        raise CommandExecutionError(result["stderr"], info=result)

    return result["stdout"].splitlines()


def list_(prefix=None, bin_env=None, user=None, cwd=None, env_vars=None, **kwargs):
    """
    Filter list of installed apps from ``freeze`` and check to see if
    ``prefix`` exists in the list of packages installed.

    .. note::

        If the version of pip available is older than 8.0.3, the packages
        ``wheel``, ``setuptools``, and ``distribute`` will not be reported by
        this function even if they are installed. Unlike :py:func:`pip.freeze
        <salt.modules.pip.freeze>`, this function always reports the version of
        pip which is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.list salt
    """

    cwd = _pip_bin_env(cwd, bin_env)
    packages = {}

    if prefix is None or "pip".startswith(prefix):
        packages["pip"] = version(bin_env, cwd)

    for line in freeze(
        bin_env=bin_env, user=user, cwd=cwd, env_vars=env_vars, **kwargs
    ):
        if line.startswith("-f") or line.startswith("#"):
            # ignore -f line as it contains --find-links directory
            # ignore comment lines
            continue
        elif line.startswith("-e hg+not trust"):
            # ignore hg + not trust problem
            continue
        elif line.startswith("-e"):
            line = line.split("-e ")[1]
            if "#egg=" in line:
                version_, name = line.split("#egg=")
            else:
                if len(line.split("===")) >= 2:
                    name = line.split("===")[0]
                    version_ = line.split("===")[1]
                elif len(line.split("==")) >= 2:
                    name = line.split("==")[0]
                    version_ = line.split("==")[1]
        elif len(line.split("===")) >= 2:
            name = line.split("===")[0]
            version_ = line.split("===")[1]
        elif len(line.split("==")) >= 2:
            name = line.split("==")[0]
            version_ = line.split("==")[1]
        else:
            logger.error("Can't parse line '%s'", line)
            continue

        if prefix:
            if name.lower().startswith(prefix.lower()):
                packages[name] = version_
        else:
            packages[name] = version_

    return packages


def version(bin_env=None, cwd=None, user=None):
    """
    .. versionadded:: 0.17.0

    Returns the version of pip. Use ``bin_env`` to specify the path to a
    virtualenv and get the version of pip in that virtualenv.

    If unable to detect the pip version, returns ``None``.

    .. versionchanged:: 3001.1
        The ``user`` parameter was added, to allow specifying the user who runs
        the version command.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.version

    """

    cwd = _pip_bin_env(cwd, bin_env)
    contextkey = "pip.version"
    if bin_env is not None:
        contextkey = "{}.{}".format(contextkey, bin_env)

    if contextkey in __context__:
        return __context__[contextkey]

    cmd = _get_pip_bin(bin_env)[:]
    cmd.append("--version")

    ret = __salt__["cmd.run_all"](cmd, cwd=cwd, runas=user, python_shell=False)
    if ret["retcode"]:
        raise CommandNotFoundError("Could not find a `pip` binary")

    try:
        pip_version = re.match(r"^pip (\S+)", ret["stdout"]).group(1)
    except AttributeError:
        pip_version = None

    __context__[contextkey] = pip_version
    return pip_version


def list_upgrades(bin_env=None, user=None, cwd=None):
    """
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pip.list_upgrades
    """

    cwd = _pip_bin_env(cwd, bin_env)
    cmd = _get_pip_bin(bin_env)
    cmd.extend(["list", "--outdated"])

    pip_version = version(bin_env, cwd, user=user)
    # Pip started supporting the ability to output json starting with 9.0.0
    min_version = "9.0"
    if salt.utils.versions.compare(ver1=pip_version, oper=">=", ver2=min_version):
        cmd.append("--format=json")

    cmd_kwargs = dict(cwd=cwd, runas=user)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs["env"] = {"VIRTUAL_ENV": bin_env}

    result = __salt__["cmd.run_all"](cmd, **cmd_kwargs)
    if result["retcode"]:
        raise CommandExecutionError(result["stderr"], info=result)

    packages = {}
    # Pip started supporting the ability to output json starting with 9.0.0
    # Older versions will have to parse stdout
    if salt.utils.versions.compare(ver1=pip_version, oper="<", ver2="9.0.0"):
        # Pip versions < 8.0.0 had a different output format
        # Sample data:
        # pip (Current: 7.1.2 Latest: 10.0.1 [wheel])
        # psutil (Current: 5.2.2 Latest: 5.4.5 [wheel])
        # pyasn1 (Current: 0.2.3 Latest: 0.4.2 [wheel])
        # pycparser (Current: 2.17 Latest: 2.18 [sdist])
        if salt.utils.versions.compare(ver1=pip_version, oper="<", ver2="8.0.0"):
            logger.debug("pip module: Old output format")
            pat = re.compile(r"(\S*)\s+\(.*Latest:\s+(.*)\)")

        # New output format for version 8.0.0+
        # Sample data:
        # pip (8.0.0) - Latest: 10.0.1 [wheel]
        # psutil (5.2.2) - Latest: 5.4.5 [wheel]
        # pyasn1 (0.2.3) - Latest: 0.4.2 [wheel]
        # pycparser (2.17) - Latest: 2.18 [sdist]
        else:
            logger.debug("pip module: New output format")
            pat = re.compile(r"(\S*)\s+\(.*\)\s+-\s+Latest:\s+(.*)")

        for line in result["stdout"].splitlines():
            match = pat.search(line)
            if match:
                name, version_ = match.groups()
            else:
                logger.error("Can't parse line %r", line)
                continue
            packages[name] = version_

    else:
        logger.debug("pip module: JSON output format")
        try:
            pkgs = salt.utils.json.loads(result["stdout"], strict=False)
        except ValueError:
            raise CommandExecutionError("Invalid JSON", info=result)

        for pkg in pkgs:
            packages[pkg["name"]] = "{} [{}]".format(
                pkg["latest_version"], pkg["latest_filetype"]
            )

    return packages


def is_installed(pkgname=None, bin_env=None, user=None, cwd=None):
    """
    .. versionadded:: 2018.3.0

    Filter list of installed apps from ``freeze`` and return True or False  if
    ``pkgname`` exists in the list of packages installed.

    .. note::
        If the version of pip available is older than 8.0.3, the packages
        wheel, setuptools, and distribute will not be reported by this function
        even if they are installed. Unlike :py:func:`pip.freeze
        <salt.modules.pip.freeze>`, this function always reports the version of
        pip which is installed.

    CLI Example:

    .. code-block:: bash

        salt '*' pip.is_installed salt
    """

    cwd = _pip_bin_env(cwd, bin_env)
    for line in freeze(bin_env=bin_env, user=user, cwd=cwd):
        if line.startswith("-f") or line.startswith("#"):
            # ignore -f line as it contains --find-links directory
            # ignore comment lines
            continue
        elif line.startswith("-e hg+not trust"):
            # ignore hg + not trust problem
            continue
        elif line.startswith("-e"):
            line = line.split("-e ")[1]
            version_, name = line.split("#egg=")
        elif len(line.split("===")) >= 2:
            name = line.split("===")[0]
            version_ = line.split("===")[1]
        elif len(line.split("==")) >= 2:
            name = line.split("==")[0]
            version_ = line.split("==")[1]
        else:
            logger.error("Can't parse line '%s'", line)
            continue

        if pkgname:
            if pkgname == name.lower():
                return True

    return False


def upgrade_available(pkg, bin_env=None, user=None, cwd=None):
    """
    .. versionadded:: 2015.5.0

    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pip.upgrade_available <package name>
    """

    cwd = _pip_bin_env(cwd, bin_env)
    return pkg in list_upgrades(bin_env=bin_env, user=user, cwd=cwd)


def upgrade(bin_env=None, user=None, cwd=None, use_vt=False):
    """
    .. versionadded:: 2015.5.0

    Upgrades outdated pip packages.

    .. note::
        On Windows you can't update salt from pip using salt, so salt will be
        skipped

    Returns a dict containing the changes.

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pip.upgrade
    """

    cwd = _pip_bin_env(cwd, bin_env)
    ret = {
        "changes": {},
        "result": True,
        "comment": "",
    }
    cmd = _get_pip_bin(bin_env)
    cmd.extend(["install", "-U"])

    old = list_(bin_env=bin_env, user=user, cwd=cwd)

    cmd_kwargs = dict(cwd=cwd, runas=user, use_vt=use_vt)
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs["env"] = {"VIRTUAL_ENV": bin_env}
    errors = False
    for pkg in list_upgrades(bin_env=bin_env, user=user, cwd=cwd):
        if pkg == "salt":
            if salt.utils.platform.is_windows():
                continue
        result = __salt__["cmd.run_all"](cmd + [pkg], **cmd_kwargs)
        if result["retcode"] != 0:
            errors = True
        if "stderr" in result:
            ret["comment"] += result["stderr"]
    if errors:
        ret["result"] = False

    _clear_context(bin_env)
    new = list_(bin_env=bin_env, user=user, cwd=cwd)

    ret["changes"] = salt.utils.data.compare_dicts(old, new)

    return ret


def list_all_versions(
    pkg,
    bin_env=None,
    include_alpha=False,
    include_beta=False,
    include_rc=False,
    user=None,
    cwd=None,
    index_url=None,
    extra_index_url=None,
):
    """
    .. versionadded:: 2017.7.3

    List all available versions of a pip package

    pkg
        The package to check

    bin_env
        Path to pip (or to a virtualenv). This can be used to specify the path
        to the pip to use when more than one Python release is installed (e.g.
        ``/usr/bin/pip-2.7`` or ``/usr/bin/pip-2.6``. If a directory path is
        specified, it is assumed to be a virtualenv.

    include_alpha
        Include alpha versions in the list

    include_beta
        Include beta versions in the list

    include_rc
        Include release candidates versions in the list

    user
        The user under which to run pip

    cwd
        Directory from which to run pip

    index_url
        Base URL of Python Package Index
        .. versionadded:: 2019.2.0

    extra_index_url
        Additional URL of Python Package Index
        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

       salt '*' pip.list_all_versions <package name>
    """
    cwd = _pip_bin_env(cwd, bin_env)
    cmd = _get_pip_bin(bin_env)

    if index_url:
        if not salt.utils.url.validate(index_url, VALID_PROTOS):
            raise CommandExecutionError("'{}' is not a valid URL".format(index_url))
        cmd.extend(["--index-url", index_url])

    if extra_index_url:
        if not salt.utils.url.validate(extra_index_url, VALID_PROTOS):
            raise CommandExecutionError(
                "'{}' is not a valid URL".format(extra_index_url)
            )
        cmd.extend(["--extra-index-url", extra_index_url])

    # Is the `pip index` command available
    pip_version = version(bin_env=bin_env, cwd=cwd, user=user)
    if salt.utils.versions.compare(ver1=pip_version, oper=">=", ver2="21.2"):
        regex = re.compile(r"\s*Available versions: (.*)")
        cmd.extend(["index", "versions", pkg])
    else:
        if salt.utils.versions.compare(ver1=pip_version, oper=">=", ver2="20.3"):
            cmd.append("--use-deprecated=legacy-resolver")
        regex = re.compile(r"\s*Could not find a version.* \(from versions: (.*)\)")
        cmd.extend(["install", "{}==versions".format(pkg)])

    cmd_kwargs = dict(
        cwd=cwd, runas=user, output_loglevel="quiet", redirect_stderr=True
    )
    if bin_env and os.path.isdir(bin_env):
        cmd_kwargs["env"] = {"VIRTUAL_ENV": bin_env}

    result = __salt__["cmd.run_all"](cmd, **cmd_kwargs)

    filtered = []
    if not include_alpha:
        filtered.append("a")
    if not include_beta:
        filtered.append("b")
    if not include_rc:
        filtered.append("rc")
    if filtered:
        excludes = re.compile(r"^((?!{}).)*$".format("|".join(filtered)))
    else:
        excludes = re.compile(r"")

    versions = []
    for line in result["stdout"].splitlines():
        match = regex.search(line)
        if match:
            versions = [
                v for v in match.group(1).split(", ") if v and excludes.match(v)
            ]
            versions.sort(key=pkg_resources.parse_version)
            break
    if not versions:
        return None

    return versions
