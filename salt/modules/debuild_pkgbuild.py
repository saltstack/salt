# -*- coding: utf-8 -*-
"""
Debian Package builder system

.. versionadded:: 2015.8.0

This system allows for all of the components to build debs safely in chrooted
environments. This also provides a function to generate debian repositories

This module implements the pkgbuild interface
"""

# import python libs
from __future__ import absolute_import, print_function, unicode_literals

import errno
import logging
import os
import re
import shutil
import tempfile
import time
import traceback

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.vt
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import third-party libs
from salt.ext import six
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse

HAS_LIBS = False

SIGN_PROMPT_RE = re.compile(r"Enter passphrase: ", re.M)
REPREPRO_SIGN_PROMPT_RE = re.compile(r"Passphrase: ", re.M)

try:
    import gnupg  # pylint: disable=unused-import
    import salt.modules.gpg

    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)


__virtualname__ = "pkgbuild"


def __virtual__():
    """
    Confirm this module is on a Debian-based system, and has required utilities
    """
    if __grains__.get("os_family", False) in ("Kali", "Debian"):
        missing_util = False
        utils_reqd = ["gpg", "debuild", "pbuilder", "reprepro"]
        for named_util in utils_reqd:
            if not salt.utils.path.which(named_util):
                missing_util = True
                break
        if HAS_LIBS and not missing_util:
            return __virtualname__
        else:
            return (
                False,
                (
                    "The debbuild module could not be loaded: requires python-gnupg, gpg, debuild, "
                    "pbuilder and reprepro utilities to be installed"
                ),
            )
    else:
        return (False, "The debbuild module could not be loaded: unsupported OS family")


def _check_repo_sign_utils_support(name):
    """
    Check for specified command name in search path
    """
    if salt.utils.path.which(name):
        return True
    else:
        raise CommandExecutionError(
            "utility '{0}' needs to be installed or made available in search path".format(
                name
            )
        )


def _check_repo_gpg_phrase_utils():
    """
    Check for /usr/lib/gnupg2/gpg-preset-passphrase is installed
    """
    util_name = "/usr/lib/gnupg2/gpg-preset-passphrase"
    if __salt__["file.file_exists"](util_name):
        return True
    else:
        raise CommandExecutionError(
            "utility '{0}' needs to be installed".format(util_name)
        )


def _get_build_env(env):
    """
    Get build environment overrides dictionary to use in build process
    """
    env_override = ""
    if env is None:
        return env_override
    if not isinstance(env, dict):
        raise SaltInvocationError("'env' must be a Python dictionary")
    for key, value in env.items():
        env_override += "{0}={1}\n".format(key, value)
        env_override += "export {0}\n".format(key)
    return env_override


def _get_repo_options_env(env):
    """
    Get repo environment overrides dictionary to use in repo options process

    env
        A dictionary of variables to define the repository options
        Example:

        .. code-block:: yaml

            - env:
                - OPTIONS : 'ask-passphrase'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

    """
    env_options = ""
    if env is None:
        return env_options
    if not isinstance(env, dict):
        raise SaltInvocationError("'env' must be a Python dictionary")
    for key, value in env.items():
        if key == "OPTIONS":
            env_options += "{0}\n".format(value)
    return env_options


def _get_repo_dists_env(env):
    """
    Get repo environment overrides dictionary to use in repo distributions process

    env
        A dictionary of variables to define the repository distributions
        Example:

        .. code-block:: yaml

            - env:
                - ORIGIN : 'jessie'
                - LABEL : 'salt debian'
                - SUITE : 'main'
                - VERSION : '8.1'
                - CODENAME : 'jessie'
                - ARCHS : 'amd64 i386 source'
                - COMPONENTS : 'main'
                - DESCRIPTION : 'SaltStack Debian package repo'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

    """
    # env key with tuple of control information for handling input env dictionary
    # 0 | M - Mandatory, O - Optional, I - Ignore
    # 1 | 'text string for repo field'
    # 2 | 'default value'
    dflts_dict = {
        "OPTIONS": ("I", "", "processed by _get_repo_options_env"),
        "ORIGIN": ("O", "Origin", "SaltStack"),
        "LABEL": ("O", "Label", "salt_debian"),
        "SUITE": ("O", "Suite", "stable"),
        "VERSION": ("O", "Version", "9.0"),
        "CODENAME": ("M", "Codename", "stretch"),
        "ARCHS": ("M", "Architectures", "i386 amd64 source"),
        "COMPONENTS": ("M", "Components", "main"),
        "DESCRIPTION": ("O", "Description", "SaltStack debian package repo"),
    }

    env_dists = ""
    codename = ""
    dflts_keys = list(dflts_dict.keys())
    if env is None:
        for key, value in dflts_dict.items():
            if dflts_dict[key][0] == "M":
                env_dists += "{0}: {1}\n".format(dflts_dict[key][1], dflts_dict[key][2])
                if key == "CODENAME":
                    codename = dflts_dict[key][2]
        return (codename, env_dists)

    if not isinstance(env, dict):
        raise SaltInvocationError("'env' must be a Python dictionary")

    env_man_seen = []
    for key, value in env.items():
        if key in dflts_keys:
            if dflts_dict[key][0] == "M":
                env_man_seen.append(key)
                if key == "CODENAME":
                    codename = value
            if dflts_dict[key][0] != "I":
                env_dists += "{0}: {1}\n".format(dflts_dict[key][1], value)
        else:
            env_dists += "{0}: {1}\n".format(key, value)

    # ensure mandatories are included
    env_keys = list(env.keys())
    for key in env_keys:
        if key in dflts_keys and dflts_dict[key][0] == "M" and key not in env_man_seen:
            env_dists += "{0}: {1}\n".format(dflts_dict[key][1], dflts_dict[key][2])
            if key == "CODENAME":
                codename = value

    return (codename, env_dists)


def _create_pbuilders(env, runas="root"):
    """
    Create the .pbuilder family of files in user's home directory

    env
        A list  or dictionary of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            - env:
                - DEB_BUILD_OPTIONS: 'nocheck'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

    runas : root
        .. versionadded:: 2019.2.1

        User to create the files and directories

        .. note::

            Ensure the user has correct permissions to any files and
            directories which are to be utilized.
    """
    home = os.path.expanduser("~{0}".format(runas))
    pbuilderrc = os.path.join(home, ".pbuilderrc")
    if not os.path.isfile(pbuilderrc):
        raise SaltInvocationError("pbuilderrc environment is incorrectly setup")

    env_overrides = _get_build_env(env)
    if env_overrides and not env_overrides.isspace():
        with salt.utils.files.fopen(pbuilderrc, "a") as fow:
            fow.write(salt.utils.stringutils.to_str(env_overrides))
    cmd = "chown {0}:{0} {1}".format(runas, pbuilderrc)
    retrc = __salt__["cmd.retcode"](cmd, runas="root")
    if retrc != 0:
        raise SaltInvocationError(
            "Create pbuilderrc in home directory failed with return error '{0}', "
            "check logs for further details".format(retrc)
        )


def _mk_tree():
    """
    Create the debian build area
    """
    basedir = tempfile.mkdtemp()
    return basedir


def _get_spec(tree_base, spec, saltenv="base"):
    """
    Get the spec file (tarball of the debian sub-dir to use)
    and place it in build area

    """
    spec_tgt = os.path.basename(spec)
    dest = os.path.join(tree_base, spec_tgt)
    return __salt__["cp.get_url"](spec, dest, saltenv=saltenv)


def _get_src(tree_base, source, saltenv="base"):
    """
    Get the named sources and place them into the tree_base
    """
    parsed = _urlparse(source)
    sbase = os.path.basename(source)
    dest = os.path.join(tree_base, sbase)
    if parsed.scheme:
        __salt__["cp.get_url"](source, dest, saltenv=saltenv)
    else:
        shutil.copy(source, dest)


def make_src_pkg(dest_dir, spec, sources, env=None, saltenv="base", runas="root"):
    """
    Create a platform specific source package from the given platform spec/control file and sources

    CLI Example:

    **Debian**

    .. code-block:: bash

        salt '*' pkgbuild.make_src_pkg /var/www/html/
                https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/deb/python-libnacl.control.tar.xz
                https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl SOURCE package and place it in
    /var/www/html/ on the minion

    dest_dir
        Absolute path for directory to write source package

    spec
        Absolute path to spec file or equivalent

    sources
        Absolute path to source files to build source package from

    env : None
        A list  or dictionary of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            - env:
                - DEB_BUILD_OPTIONS: 'nocheck'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

    saltenv: base

        Salt environment variables


    runas : root
        .. versionadded:: 2019.2.1

        User to create the files and directories

        .. note::

            Ensure the user has correct permissions to any files and
            directories which are to be utilized.
    """
    _create_pbuilders(env, runas)
    tree_base = _mk_tree()
    ret = []
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)

    # ensure directories are writable
    root_user = "root"
    retrc = 0
    cmd = "chown {0}:{0} {1}".format(runas, tree_base)
    retrc = __salt__["cmd.retcode"](cmd, runas="root")
    if retrc != 0:
        raise SaltInvocationError(
            "make_src_pkg ensuring tree_base '{0}' ownership failed with return error '{1}', "
            "check logs for further details".format(tree_base, retrc)
        )

    cmd = "chown {0}:{0} {1}".format(runas, dest_dir)
    retrc = __salt__["cmd.retcode"](cmd, runas=root_user)
    if retrc != 0:
        raise SaltInvocationError(
            "make_src_pkg ensuring dest_dir '{0}' ownership failed with return error '{1}', "
            "check logs for further details".format(dest_dir, retrc)
        )

    spec_pathfile = _get_spec(tree_base, spec, saltenv)

    # build salt equivalents from scratch
    if isinstance(sources, six.string_types):
        sources = sources.split(",")
    for src in sources:
        _get_src(tree_base, src, saltenv)

    # .dsc then assumes sources already build
    if spec_pathfile.endswith(".dsc"):
        for efile in os.listdir(tree_base):
            full = os.path.join(tree_base, efile)
            trgt = os.path.join(dest_dir, efile)
            shutil.copy(full, trgt)
            ret.append(trgt)

        return ret

    # obtain name of 'python setup.py sdist' generated tarball, extract the version
    # and manipulate the name for debian use (convert minix and add '+ds')
    salttarball = None
    for afile in os.listdir(tree_base):
        if afile.startswith("salt-") and afile.endswith(".tar.gz"):
            salttarball = afile
            break
    else:
        return ret

    frontname = salttarball.split(".tar.gz")
    salttar_name = frontname[0]
    k = salttar_name.rfind("-")
    debname = salttar_name[:k] + "_" + salttar_name[k + 1 :]
    debname += "+ds"
    debname_orig = debname + ".orig.tar.gz"
    abspath_debname = os.path.join(tree_base, debname)

    cmd = "tar -xvzf {0}".format(salttarball)
    retrc = __salt__["cmd.retcode"](cmd, cwd=tree_base, runas=root_user)
    cmd = "mv {0} {1}".format(salttar_name, debname)
    retrc |= __salt__["cmd.retcode"](cmd, cwd=tree_base, runas=root_user)
    cmd = "tar -cvzf {0} {1}".format(os.path.join(tree_base, debname_orig), debname)
    retrc |= __salt__["cmd.retcode"](cmd, cwd=tree_base, runas=root_user)
    cmd = "rm -f {0}".format(salttarball)
    retrc |= __salt__["cmd.retcode"](cmd, cwd=tree_base, runas=root_user, env=env)
    cmd = "cp {0}  {1}".format(spec_pathfile, abspath_debname)
    retrc |= __salt__["cmd.retcode"](cmd, cwd=abspath_debname, runas=root_user)
    cmd = "tar -xvJf {0}".format(spec_pathfile)
    retrc |= __salt__["cmd.retcode"](cmd, cwd=abspath_debname, runas=root_user, env=env)
    cmd = "rm -f {0}".format(os.path.basename(spec_pathfile))
    retrc |= __salt__["cmd.retcode"](cmd, cwd=abspath_debname, runas=root_user)
    cmd = "debuild -S -uc -us -sa"
    retrc |= __salt__["cmd.retcode"](
        cmd, cwd=abspath_debname, runas=root_user, python_shell=True, env=env
    )
    cmd = "rm -fR {0}".format(abspath_debname)
    retrc |= __salt__["cmd.retcode"](cmd, runas=root_user)
    if retrc != 0:
        raise SaltInvocationError(
            "Make source package for destination directory {0}, spec {1}, sources {2}, failed "
            "with return error {3}, check logs for further details".format(
                dest_dir, spec, sources, retrc
            )
        )

    for dfile in os.listdir(tree_base):
        if not dfile.endswith(".build"):
            full = os.path.join(tree_base, dfile)
            trgt = os.path.join(dest_dir, dfile)
            shutil.copy(full, trgt)
            ret.append(trgt)

    return ret


def build(
    runas,
    tgt,
    dest_dir,
    spec,
    sources,
    deps,
    env,
    template,
    saltenv="base",
    log_dir="/var/log/salt/pkgbuild",
):  # pylint: disable=unused-argument
    """
    Given the package destination directory, the tarball containing debian files (e.g. control)
    and package sources, use pbuilder to safely build the platform package

    CLI Example:

    **Debian**

    .. code-block:: bash

        salt '*' pkgbuild.make_src_pkg deb-8-x86_64 /var/www/html
                https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/deb/python-libnacl.control
                https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl package for Debian using pbuilder
    and place it in /var/www/html/ on the minion
    """
    ret = {}
    retrc = 0
    try:
        os.makedirs(dest_dir)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    dsc_dir = tempfile.mkdtemp()
    try:
        dscs = make_src_pkg(dsc_dir, spec, sources, env, saltenv, runas)
    except Exception as exc:  # pylint: disable=broad-except
        shutil.rmtree(dsc_dir)
        log.error("Failed to make src package, exception '{0}'".format(exc))
        return ret

    root_user = "root"

    # ensure pbuilder setup from runas if other than root
    if runas != root_user:
        user_home = os.path.expanduser("~{0}".format(runas))
        root_home = os.path.expanduser("~root")
        cmd = "cp {0}/.pbuilderrc {1}/".format(user_home, root_home)
        retrc = __salt__["cmd.retcode"](
            cmd, runas=root_user, python_shell=True, env=env
        )
        cmd = "cp -R {0}/.pbuilder-hooks {1}/".format(user_home, root_home)
        retrc = __salt__["cmd.retcode"](
            cmd, runas=root_user, python_shell=True, env=env
        )
        if retrc != 0:
            raise SaltInvocationError(
                "build copy pbuilder files from '{0}' to '{1}' returned error '{2}', "
                "check logs for further details".format(user_home, root_home, retrc)
            )

    cmd = "/usr/sbin/pbuilder --create"
    retrc = __salt__["cmd.retcode"](cmd, runas=root_user, python_shell=True, env=env)
    if retrc != 0:
        raise SaltInvocationError(
            "pbuilder create failed with return error '{0}', "
            "check logs for further details".format(retrc)
        )

    # use default /var/cache/pbuilder/result
    results_dir = "/var/cache/pbuilder/result"

    # ensure clean
    cmd = "rm -fR {0}".format(results_dir)
    retrc |= __salt__["cmd.retcode"](cmd, runas=root_user, python_shell=True, env=env)

    # dscs should only contain salt orig and debian tarballs and dsc file
    for dsc in dscs:
        afile = os.path.basename(dsc)
        os.path.join(dest_dir, afile)

        if dsc.endswith(".dsc"):
            dbase = os.path.dirname(dsc)
            try:
                cmd = "chown {0}:{0} -R {1}".format(runas, dbase)
                retrc |= __salt__["cmd.retcode"](
                    cmd, runas=root_user, python_shell=True, env=env
                )
                cmd = "/usr/sbin/pbuilder update --override-config"
                retrc |= __salt__["cmd.retcode"](
                    cmd, runas=root_user, python_shell=True, env=env
                )
                cmd = '/usr/sbin/pbuilder build --debbuildopts "-sa" {0}'.format(dsc)
                retrc |= __salt__["cmd.retcode"](
                    cmd, runas=root_user, python_shell=True, env=env
                )
                if retrc != 0:
                    raise SaltInvocationError(
                        "pbuilder build or update failed with return error {0}, "
                        "check logs for further details".format(retrc)
                    )

                # ignore local deps generated package file
                for bfile in os.listdir(results_dir):
                    if bfile != "Packages":
                        full = os.path.join(results_dir, bfile)
                        bdist = os.path.join(dest_dir, bfile)
                        shutil.copy(full, bdist)
                        ret.setdefault("Packages", []).append(bdist)

            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error building from '{0}', execption '{1}'".format(dsc, exc))

    # remove any Packages file created for local dependency processing
    for pkgzfile in os.listdir(dest_dir):
        if pkgzfile == "Packages":
            pkgzabsfile = os.path.join(dest_dir, pkgzfile)
            os.remove(pkgzabsfile)

    cmd = "chown {0}:{0} -R {1}".format(runas, dest_dir)
    __salt__["cmd.retcode"](cmd, runas=root_user, python_shell=True, env=env)

    shutil.rmtree(dsc_dir)
    return ret


def make_repo(
    repodir,
    keyid=None,
    env=None,
    use_passphrase=False,
    gnupghome="/etc/salt/gpgkeys",
    runas="root",
    timeout=15.0,
):
    """
    Make a package repository and optionally sign it and packages present

    Given the repodir (directory to create repository in), create a Debian
    repository and optionally sign it and packages present. This state is
    best used with onchanges linked to your package building states.

    repodir
        The directory to find packages that will be in the repository.

    keyid
        .. versionchanged:: 2016.3.0

        Optional Key ID to use in signing packages and repository.
        This consists of the last 8 hex digits of the GPG key ID.

        Utilizes Public and Private keys associated with keyid which have
        been loaded into the minion's Pillar data. Leverages gpg-agent and
        gpg-preset-passphrase for caching keys, etc.
        These pillar values are assumed to be filenames which are present
        in ``gnupghome``. The pillar keys shown below have to match exactly.

        For example, contents from a Pillar data file with named Public
        and Private keys as follows:

        .. code-block:: yaml

            gpg_pkg_priv_keyname: gpg_pkg_key.pem
            gpg_pkg_pub_keyname: gpg_pkg_key.pub

    env
        .. versionchanged:: 2016.3.0

        A dictionary of environment variables to be utilized in creating the
        repository.

    use_passphrase : False
        .. versionadded:: 2016.3.0

        Use a passphrase with the signing key presented in ``keyid``.
        Passphrase is received from Pillar data which could be passed on the
        command line with ``pillar`` parameter. For example:

        .. code-block:: bash

            pillar='{ "gpg_passphrase" : "my_passphrase" }'

    gnupghome : /etc/salt/gpgkeys
        .. versionadded:: 2016.3.0

        Location where GPG related files are stored, used with ``keyid``.

    runas : root
        .. versionadded:: 2016.3.0

        User to create the repository as, and optionally sign packages.

        .. note::

            Ensure the user has correct permissions to any files and
            directories which are to be utilized.

    timeout : 15.0
        .. versionadded:: 2016.3.4

        Timeout in seconds to wait for the prompt for inputting the passphrase.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgbuild.make_repo /var/www/html

    """
    res = {"retcode": 1, "stdout": "", "stderr": "initialization value"}

    retrc = 0

    if gnupghome and env is None:
        env = {}
        env["GNUPGHOME"] = gnupghome

    repoconf = os.path.join(repodir, "conf")
    if not os.path.isdir(repoconf):
        os.makedirs(repoconf)

    codename, repocfg_dists = _get_repo_dists_env(env)
    repoconfdist = os.path.join(repoconf, "distributions")
    with salt.utils.files.fopen(repoconfdist, "w") as fow:
        fow.write(salt.utils.stringutils.to_str(repocfg_dists))

    repocfg_opts = _get_repo_options_env(env)
    repoconfopts = os.path.join(repoconf, "options")
    with salt.utils.files.fopen(repoconfopts, "w") as fow:
        fow.write(salt.utils.stringutils.to_str(repocfg_opts))

    cmd = "chown {0}:{0} -R {1}".format(runas, repoconf)
    retrc = __salt__["cmd.retcode"](cmd, runas="root")
    if retrc != 0:
        raise SaltInvocationError(
            "failed to ensure rights to repoconf directory, error {0}, "
            "check logs for further details".format(retrc)
        )

    local_keygrip_to_use = None
    local_key_fingerprint = None
    local_keyid = None
    phrase = ""

    # preset passphase and interaction with gpg-agent
    gpg_info_file = "{0}/gpg-agent-info-salt".format(gnupghome)
    gpg_tty_info_file = "{0}/gpg-tty-info-salt".format(gnupghome)

    # if using older than gnupg 2.1, then env file exists
    older_gnupg = __salt__["file.file_exists"](gpg_info_file)

    if keyid is not None:
        with salt.utils.files.fopen(repoconfdist, "a") as fow:
            fow.write(salt.utils.stringutils.to_str("SignWith: {0}\n".format(keyid)))

        # import_keys
        pkg_pub_key_file = "{0}/{1}".format(
            gnupghome, __salt__["pillar.get"]("gpg_pkg_pub_keyname", None)
        )
        pkg_priv_key_file = "{0}/{1}".format(
            gnupghome, __salt__["pillar.get"]("gpg_pkg_priv_keyname", None)
        )

        if pkg_pub_key_file is None or pkg_priv_key_file is None:
            raise SaltInvocationError(
                "Pillar data should contain Public and Private keys associated with 'keyid'"
            )
        try:
            __salt__["gpg.import_key"](
                user=runas, filename=pkg_pub_key_file, gnupghome=gnupghome
            )
            __salt__["gpg.import_key"](
                user=runas, filename=pkg_priv_key_file, gnupghome=gnupghome
            )

        except SaltInvocationError:
            raise SaltInvocationError(
                "Public and Private key files associated with Pillar data and 'keyid' "
                "{0} could not be found".format(keyid)
            )

        # gpg keys should have been loaded as part of setup
        # retrieve specified key, obtain fingerprint and preset passphrase
        local_keys = __salt__["gpg.list_keys"](user=runas, gnupghome=gnupghome)
        for gpg_key in local_keys:
            if keyid == gpg_key["keyid"][8:]:
                local_keygrip_to_use = gpg_key["fingerprint"]
                local_key_fingerprint = gpg_key["fingerprint"]
                local_keyid = gpg_key["keyid"]
                break

        if not older_gnupg:
            try:
                _check_repo_sign_utils_support("gpg2")
                cmd = "gpg2 --with-keygrip --list-secret-keys"
            except CommandExecutionError:
                # later gpg versions have dispensed with gpg2 - Ubuntu 18.04
                cmd = "gpg --with-keygrip --list-secret-keys"
            local_keys2_keygrip = __salt__["cmd.run"](cmd, runas=runas, env=env)
            local_keys2 = iter(local_keys2_keygrip.splitlines())
            try:
                for line in local_keys2:
                    if line.startswith("sec"):
                        line_fingerprint = next(local_keys2).lstrip().rstrip()
                        if local_key_fingerprint == line_fingerprint:
                            lkeygrip = next(local_keys2).split("=")
                            local_keygrip_to_use = lkeygrip[1].lstrip().rstrip()
                            break
            except StopIteration:
                raise SaltInvocationError(
                    "unable to find keygrip associated with fingerprint '{0}' for keyid '{1}'".format(
                        local_key_fingerprint, local_keyid
                    )
                )

        if local_keyid is None:
            raise SaltInvocationError(
                "The key ID '{0}' was not found in GnuPG keyring at '{1}'".format(
                    keyid, gnupghome
                )
            )

        _check_repo_sign_utils_support("debsign")

        if older_gnupg:
            with salt.utils.files.fopen(gpg_info_file, "r") as fow:
                gpg_raw_info = fow.readlines()

            for gpg_info_line in gpg_raw_info:
                gpg_info_line = salt.utils.stringutils.to_unicode(gpg_info_line)
                gpg_info = gpg_info_line.split("=")
                env[gpg_info[0]] = gpg_info[1]
                break
        else:
            with salt.utils.files.fopen(gpg_tty_info_file, "r") as fow:
                gpg_raw_info = fow.readlines()

            for gpg_tty_info_line in gpg_raw_info:
                gpg_tty_info_line = salt.utils.stringutils.to_unicode(gpg_tty_info_line)
                gpg_tty_info = gpg_tty_info_line.split("=")
                env[gpg_tty_info[0]] = gpg_tty_info[1]
                break

        if use_passphrase:
            _check_repo_gpg_phrase_utils()
            phrase = __salt__["pillar.get"]("gpg_passphrase")
            cmd = '/usr/lib/gnupg2/gpg-preset-passphrase --verbose --preset --passphrase "{0}" {1}'.format(
                phrase, local_keygrip_to_use
            )
            retrc |= __salt__["cmd.retcode"](cmd, runas=runas, env=env)

    for debfile in os.listdir(repodir):
        abs_file = os.path.join(repodir, debfile)
        if debfile.endswith(".changes"):
            os.remove(abs_file)

        if debfile.endswith(".dsc"):
            # sign_it_here
            if older_gnupg:
                if local_keyid is not None:
                    cmd = "debsign --re-sign -k {0} {1}".format(keyid, abs_file)
                    retrc |= __salt__["cmd.retcode"](
                        cmd, runas=runas, cwd=repodir, use_vt=True, env=env
                    )

                cmd = "reprepro --ignore=wrongdistribution --component=main -Vb . includedsc {0} {1}".format(
                    codename, abs_file
                )
                retrc |= __salt__["cmd.retcode"](
                    cmd, runas=runas, cwd=repodir, use_vt=True, env=env
                )
            else:
                # interval of 0.125 is really too fast on some systems
                interval = 0.5
                if local_keyid is not None:
                    number_retries = timeout / interval
                    times_looped = 0
                    error_msg = "Failed to debsign file {0}".format(abs_file)
                    if (
                        __grains__["os"] in ["Ubuntu"]
                        and __grains__["osmajorrelease"] < 18
                    ) or (
                        __grains__["os"] in ["Debian"]
                        and __grains__["osmajorrelease"] <= 8
                    ):
                        cmd = "debsign --re-sign -k {0} {1}".format(keyid, abs_file)
                        try:
                            proc = salt.utils.vt.Terminal(
                                cmd,
                                env=env,
                                shell=True,
                                stream_stdout=True,
                                stream_stderr=True,
                            )
                            while proc.has_unread_data:
                                stdout, _ = proc.recv()
                                if stdout and SIGN_PROMPT_RE.search(stdout):
                                    # have the prompt for inputting the passphrase
                                    proc.sendline(phrase)
                                else:
                                    times_looped += 1

                                if times_looped > number_retries:
                                    raise SaltInvocationError(
                                        "Attempting to sign file {0} failed, timed out after {1} seconds".format(
                                            abs_file, int(times_looped * interval)
                                        )
                                    )
                                time.sleep(interval)

                            proc_exitstatus = proc.exitstatus
                            if proc_exitstatus != 0:
                                raise SaltInvocationError(
                                    "Signing file {0} failed with proc.status {1}".format(
                                        abs_file, proc_exitstatus
                                    )
                                )
                        except salt.utils.vt.TerminalException as err:
                            trace = traceback.format_exc()
                            log.error(error_msg, err, trace)
                            res = {"retcode": 1, "stdout": "", "stderr": trace}
                        finally:
                            proc.close(terminate=True, kill=True)
                    else:
                        cmd = "debsign --re-sign -k {0} {1}".format(
                            local_key_fingerprint, abs_file
                        )
                        retrc |= __salt__["cmd.retcode"](
                            cmd, runas=runas, cwd=repodir, use_vt=True, env=env
                        )

                number_retries = timeout / interval
                times_looped = 0
                error_msg = "Failed to reprepro includedsc file {0}".format(abs_file)
                cmd = "reprepro --ignore=wrongdistribution --component=main -Vb . includedsc {0} {1}".format(
                    codename, abs_file
                )
                if (
                    __grains__["os"] in ["Ubuntu"] and __grains__["osmajorrelease"] < 18
                ) or (
                    __grains__["os"] in ["Debian"] and __grains__["osmajorrelease"] <= 8
                ):
                    try:
                        proc = salt.utils.vt.Terminal(
                            cmd,
                            env=env,
                            shell=True,
                            cwd=repodir,
                            stream_stdout=True,
                            stream_stderr=True,
                        )
                        while proc.has_unread_data:
                            stdout, _ = proc.recv()
                            if stdout and REPREPRO_SIGN_PROMPT_RE.search(stdout):
                                # have the prompt for inputting the passphrase
                                proc.sendline(phrase)
                            else:
                                times_looped += 1

                            if times_looped > number_retries:
                                raise SaltInvocationError(
                                    "Attempting to reprepro includedsc for file {0} failed, timed out after {1} loops".format(
                                        abs_file, times_looped
                                    )
                                )
                            time.sleep(interval)

                        proc_exitstatus = proc.exitstatus
                        if proc_exitstatus != 0:
                            raise SaltInvocationError(
                                "Reprepro includedsc for codename {0} and file {1} failed with proc.status {2}".format(
                                    codename, abs_file, proc_exitstatus
                                )
                            )
                    except salt.utils.vt.TerminalException as err:
                        trace = traceback.format_exc()
                        log.error(error_msg, err, trace)
                        res = {"retcode": 1, "stdout": "", "stderr": trace}
                    finally:
                        proc.close(terminate=True, kill=True)
                else:
                    retrc |= __salt__["cmd.retcode"](
                        cmd, runas=runas, cwd=repodir, use_vt=True, env=env
                    )

        if retrc != 0:
            raise SaltInvocationError(
                "Making a repo encountered errors, return error {0}, check logs for further details".format(
                    retrc
                )
            )

        if debfile.endswith(".deb"):
            cmd = "reprepro --ignore=wrongdistribution --component=main -Vb . includedeb {0} {1}".format(
                codename, abs_file
            )
            res = __salt__["cmd.run_all"](
                cmd, runas=runas, cwd=repodir, use_vt=True, env=env
            )

    return res
