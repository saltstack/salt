"""
RPM Package builder system

.. versionadded:: 2015.8.0

This system allows for all of the components to build rpms safely in chrooted
environments. This also provides a function to generate yum repositories

This module implements the pkgbuild interface
"""


import errno
import functools
import logging
import os
import re
import shutil
import tempfile
import time
import traceback
import urllib.parse

import salt.utils.files
import salt.utils.path
import salt.utils.user
import salt.utils.vt
from salt.exceptions import CommandExecutionError, SaltInvocationError

HAS_LIBS = False

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
    Confirm this module is on a RPM based system, and has required utilities
    """
    missing_util = False
    utils_reqd = ["gpg", "rpm", "rpmbuild", "mock", "createrepo"]
    for named_util in utils_reqd:
        if not salt.utils.path.which(named_util):
            missing_util = True
            break

    if HAS_LIBS and not missing_util:
        if __grains__.get("os_family", False) in ("RedHat", "Suse"):
            return __virtualname__
        else:
            # The module will be exposed as `rpmbuild` on non-RPM based systems
            return "rpmbuild"
    else:
        return (
            False,
            "The rpmbuild module could not be loaded: requires python-gnupg, "
            "gpg, rpm, rpmbuild, mock and createrepo utilities to be installed",
        )


def _create_rpmmacros(runas="root"):
    """
    Create the .rpmmacros file in user's home directory
    """
    home = os.path.expanduser("~" + runas)
    rpmbuilddir = os.path.join(home, "rpmbuild")
    if not os.path.isdir(rpmbuilddir):
        __salt__["file.makedirs_perms"](name=rpmbuilddir, user=runas, group="mock")

    mockdir = os.path.join(home, "mock")
    if not os.path.isdir(mockdir):
        __salt__["file.makedirs_perms"](name=mockdir, user=runas, group="mock")

    rpmmacros = os.path.join(home, ".rpmmacros")
    with salt.utils.files.fopen(rpmmacros, "w") as afile:
        afile.write(salt.utils.stringutils.to_str("%_topdir {}\n".format(rpmbuilddir)))
        afile.write("%signature gpg\n")
        afile.write("%_source_filedigest_algorithm 8\n")
        afile.write("%_binary_filedigest_algorithm 8\n")
        afile.write("%_gpg_name packaging@saltstack.com\n")


def _mk_tree(runas="root"):
    """
    Create the rpm build tree
    """
    basedir = tempfile.mkdtemp()
    paths = ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]
    for path in paths:
        full = os.path.join(basedir, path)
        __salt__["file.makedirs_perms"](name=full, user=runas, group="mock")
    return basedir


def _get_spec(tree_base, spec, template, saltenv="base"):
    """
    Get the spec file and place it in the SPECS dir
    """
    spec_tgt = os.path.basename(spec)
    dest = os.path.join(tree_base, "SPECS", spec_tgt)
    return __salt__["cp.get_url"](spec, dest, saltenv=saltenv)


def _get_src(tree_base, source, saltenv="base", runas="root"):
    """
    Get the named sources and place them into the tree_base
    """
    parsed = urllib.parse.urlparse(source)
    sbase = os.path.basename(source)
    dest = os.path.join(tree_base, "SOURCES", sbase)
    if parsed.scheme:
        lsrc = __salt__["cp.get_url"](source, dest, saltenv=saltenv)
    else:
        shutil.copy(source, dest)
    __salt__["file.chown"](path=dest, user=runas, group="mock")


def _get_distset(tgt):
    """
    Get the distribution string for use with rpmbuild and mock
    """
    # Centos adds 'centos' string to rpm names, removing that to have
    # consistent naming on Centos and Redhat, and allow for Amazon naming
    tgtattrs = tgt.split("-")
    if tgtattrs[0] == "amzn2":
        distset = '--define "dist .{}"'.format(tgtattrs[0])
    elif tgtattrs[1] in ["6", "7", "8"]:
        distset = '--define "dist .el{}"'.format(tgtattrs[1])
    else:
        distset = ""

    return distset


def _get_deps(deps, tree_base, saltenv="base"):
    """
    Get include string for list of dependent rpms to build package
    """
    deps_list = ""
    if deps is None:
        return deps_list
    if not isinstance(deps, list):
        raise SaltInvocationError(
            "'deps' must be a Python list or comma-separated string"
        )
    for deprpm in deps:
        parsed = urllib.parse._urlparse(deprpm)
        depbase = os.path.basename(deprpm)
        dest = os.path.join(tree_base, depbase)
        if parsed.scheme:
            __salt__["cp.get_url"](deprpm, dest, saltenv=saltenv)
        else:
            shutil.copy(deprpm, dest)

        deps_list += " {}".format(dest)

    return deps_list


def _check_repo_gpg_phrase_utils():
    """
    Check for /usr/libexec/gpg-preset-passphrase is installed
    """
    util_name = "/usr/libexec/gpg-preset-passphrase"
    if __salt__["file.file_exists"](util_name):
        return True
    else:
        raise CommandExecutionError(
            "utility '{}' needs to be installed".format(util_name)
        )


def _get_gpg_key_resources(keyid, env, use_passphrase, gnupghome, runas):
    """
    Obtain gpg key resource infomation to sign repo files with

    keyid

        Optional Key ID to use in signing packages and repository.
        Utilizes Public and Private keys associated with keyid which have
        been loaded into the minion's Pillar data.

    env

        A dictionary of environment variables to be utilized in creating the
        repository.

    use_passphrase : False

        Use a passphrase with the signing key presented in ``keyid``.
        Passphrase is received from Pillar data which could be passed on the
        command line with ``pillar`` parameter.

    gnupghome : /etc/salt/gpgkeys

        Location where GPG related files are stored, used with ``keyid``.

    runas : root

        User to create the repository as, and optionally sign packages.

        .. note::

            Ensure the user has correct permissions to any files and
            directories which are to be utilized.


    Returns:
        tuple
            use_gpg_agent       True | False, Redhat 8 now makes use of a gpg-agent similar ot Debian
            local_keyid         key id to use in signing
            define_gpg_name     string containing definition to use with addsign (use_gpg_agent False)
            phrase              pass phrase (may not be used)

    """
    local_keygrip_to_use = None
    local_key_fingerprint = None
    local_keyid = None
    local_uids = None
    define_gpg_name = ""
    phrase = ""
    retrc = 0
    use_gpg_agent = False

    if (
        __grains__.get("os_family") == "RedHat"
        and __grains__.get("osmajorrelease") >= 8
    ):
        use_gpg_agent = True

    if keyid is not None:
        # import_keys
        pkg_pub_key_file = "{}/{}".format(
            gnupghome, __salt__["pillar.get"]("gpg_pkg_pub_keyname", None)
        )
        pkg_priv_key_file = "{}/{}".format(
            gnupghome, __salt__["pillar.get"]("gpg_pkg_priv_keyname", None)
        )

        if pkg_pub_key_file is None or pkg_priv_key_file is None:
            raise SaltInvocationError(
                "Pillar data should contain Public and Private keys associated with"
                " 'keyid'"
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
                "{} could not be found".format(keyid)
            )

        # gpg keys should have been loaded as part of setup
        # retrieve specified key and preset passphrase
        local_keys = __salt__["gpg.list_keys"](user=runas, gnupghome=gnupghome)
        for gpg_key in local_keys:
            if keyid == gpg_key["keyid"][8:]:
                local_uids = gpg_key["uids"]
                local_keyid = gpg_key["keyid"]
                if use_gpg_agent:
                    local_keygrip_to_use = gpg_key["fingerprint"]
                    local_key_fingerprint = gpg_key["fingerprint"]
                break

        if use_gpg_agent:
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
                    "unable to find keygrip associated with fingerprint '{}' for keyid"
                    " '{}'".format(local_key_fingerprint, local_keyid)
                )

        if local_keyid is None:
            raise SaltInvocationError(
                "The key ID '{}' was not found in GnuPG keyring at '{}'".format(
                    keyid, gnupghome
                )
            )

        if use_passphrase:
            phrase = __salt__["pillar.get"]("gpg_passphrase")
            if use_gpg_agent:
                _check_repo_gpg_phrase_utils()
                cmd = (
                    "/usr/libexec/gpg-preset-passphrase --verbose --preset "
                    '--passphrase "{}" {}'.format(phrase, local_keygrip_to_use)
                )
                retrc = __salt__["cmd.retcode"](cmd, runas=runas, env=env)
                if retrc != 0:
                    raise SaltInvocationError(
                        "Failed to preset passphrase, error {1}, "
                        "check logs for further details".format(retrc)
                    )

        if local_uids:
            define_gpg_name = (
                "--define='%_signature gpg' --define='%_gpg_name {}'".format(
                    local_uids[0]
                )
            )

        # need to update rpm with public key
        cmd = "rpm --import {}".format(pkg_pub_key_file)
        retrc = __salt__["cmd.retcode"](cmd, runas=runas, use_vt=True)
        if retrc != 0:
            raise SaltInvocationError(
                "Failed to import public key from file {} with return "
                "error {}, check logs for further details".format(
                    pkg_pub_key_file, retrc
                )
            )

    return (use_gpg_agent, local_keyid, define_gpg_name, phrase)


def _sign_file(runas, define_gpg_name, phrase, abs_file, timeout):
    """
    Sign file with provided key and definition
    """
    SIGN_PROMPT_RE = re.compile(r"Enter pass phrase: ", re.M)

    # interval of 0.125 is really too fast on some systems
    interval = 0.5
    number_retries = timeout / interval
    times_looped = 0
    error_msg = "Failed to sign file {}".format(abs_file)

    cmd = "rpm {} --addsign {}".format(define_gpg_name, abs_file)
    preexec_fn = functools.partial(salt.utils.user.chugid_and_umask, runas, None)
    try:
        stdout, stderr = None, None
        proc = salt.utils.vt.Terminal(
            cmd,
            shell=True,
            preexec_fn=preexec_fn,
            stream_stdout=True,
            stream_stderr=True,
        )
        while proc.has_unread_data:
            stdout, stderr = proc.recv()
            if stdout and SIGN_PROMPT_RE.search(stdout):
                # have the prompt for inputting the passphrase
                proc.sendline(phrase)
            else:
                times_looped += 1

            if times_looped > number_retries:
                raise SaltInvocationError(
                    "Attemping to sign file {} failed, timed out after {} seconds".format(
                        abs_file, int(times_looped * interval)
                    )
                )
            time.sleep(interval)

        proc_exitstatus = proc.exitstatus
        if proc_exitstatus != 0:
            raise SaltInvocationError(
                "Signing file {} failed with proc.status {}".format(
                    abs_file, proc_exitstatus
                )
            )
    except salt.utils.vt.TerminalException as err:
        trace = traceback.format_exc()
        log.error(error_msg, err, trace)
    finally:
        proc.close(terminate=True, kill=True)


def _sign_files_with_gpg_agent(runas, local_keyid, abs_file, repodir, env, timeout):
    """
    Sign file with provided key utilizing gpg-agent
    """
    cmd = "rpmsign --verbose  --key-id={} --addsign {}".format(local_keyid, abs_file)
    retrc = __salt__["cmd.retcode"](cmd, runas=runas, cwd=repodir, use_vt=True, env=env)
    if retrc != 0:
        raise SaltInvocationError(
            "Signing encountered errors for command '{}', "
            "return error {}, check logs for further details".format(cmd, retrc)
        )


def make_src_pkg(
    dest_dir, spec, sources, env=None, template=None, saltenv="base", runas="root"
):
    """
    Create a source rpm from the given spec file and sources

    CLI Example:

    .. code-block:: bash

        salt '*' pkgbuild.make_src_pkg /var/www/html/
                https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec
                https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl SOURCE package and place it in
    /var/www/html/ on the minion

    .. versionchanged:: 2017.7.0

    dest_dir
        The directory on the minion to place the built package(s)

    spec
        The location of the spec file (used for rpms)

    sources
        The list of package sources

    env
        A dictionary of environment variables to be set prior to execution.

    template
        Run the spec file through a templating engine
        Optional argument, allows for no templating engine used to be
        if none is desired.

    saltenv
        The saltenv to use for files downloaded from the salt filesever

    runas
        The user to run the build process as

        .. versionadded:: 2018.3.3


    .. note::

        using SHA256 as digest and minimum level dist el6

    """
    _create_rpmmacros(runas)
    tree_base = _mk_tree(runas)
    spec_path = _get_spec(tree_base, spec, template, saltenv)
    __salt__["file.chown"](path=spec_path, user=runas, group="mock")
    __salt__["file.chown"](path=tree_base, user=runas, group="mock")

    if isinstance(sources, str):
        sources = sources.split(",")
    for src in sources:
        _get_src(tree_base, src, saltenv, runas)

    # make source rpms for dist el6 with SHA256, usable with mock on other dists
    cmd = 'rpmbuild --verbose --define "_topdir {}" -bs --define "dist .el6" {}'.format(
        tree_base, spec_path
    )
    retrc = __salt__["cmd.retcode"](cmd, runas=runas)
    if retrc != 0:
        raise SaltInvocationError(
            "Make source package for destination directory {}, spec {}, sources {},"
            " failed with return error {}, check logs for further details".format(
                dest_dir, spec, sources, retrc
            )
        )

    srpms = os.path.join(tree_base, "SRPMS")
    ret = []
    if not os.path.isdir(dest_dir):
        __salt__["file.makedirs_perms"](name=dest_dir, user=runas, group="mock")
    for fn_ in os.listdir(srpms):
        full = os.path.join(srpms, fn_)
        tgt = os.path.join(dest_dir, fn_)
        shutil.copy(full, tgt)
        ret.append(tgt)
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
):
    """
    Given the package destination directory, the spec file source and package
    sources, use mock to safely build the rpm defined in the spec file

    CLI Example:

    .. code-block:: bash

        salt '*' pkgbuild.build mock epel-7-x86_64 /var/www/html
                    https://raw.githubusercontent.com/saltstack/libnacl/master/pkg/rpm/python-libnacl.spec
                    https://pypi.python.org/packages/source/l/libnacl/libnacl-1.3.5.tar.gz

    This example command should build the libnacl package for rhel 7 using user
    mock and place it in /var/www/html/ on the minion
    """
    ret = {}
    try:
        __salt__["file.chown"](path=dest_dir, user=runas, group="mock")
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    srpm_dir = os.path.join(dest_dir, "SRPMS")
    srpm_build_dir = tempfile.mkdtemp()
    try:
        srpms = make_src_pkg(
            srpm_build_dir, spec, sources, env, template, saltenv, runas
        )
    except Exception as exc:  # pylint: disable=broad-except
        shutil.rmtree(srpm_build_dir)
        log.error("Failed to make src package")
        return ret

    distset = _get_distset(tgt)

    noclean = ""
    deps_dir = tempfile.mkdtemp()
    deps_list = _get_deps(deps, deps_dir, saltenv)

    retrc = 0
    for srpm in srpms:
        dbase = os.path.dirname(srpm)
        results_dir = tempfile.mkdtemp()
        try:
            __salt__["file.chown"](path=dbase, user=runas, group="mock")
            __salt__["file.chown"](path=results_dir, user=runas, group="mock")
            cmd = "mock --root={} --resultdir={} --init".format(tgt, results_dir)
            retrc |= __salt__["cmd.retcode"](cmd, runas=runas)
            if deps_list and not deps_list.isspace():
                cmd = "mock --root={} --resultdir={} --install {} {}".format(
                    tgt, results_dir, deps_list, noclean
                )
                retrc |= __salt__["cmd.retcode"](cmd, runas=runas)
                noclean += " --no-clean"

            cmd = "mock --root={} --resultdir={} {} {} {}".format(
                tgt, results_dir, distset, noclean, srpm
            )
            retrc |= __salt__["cmd.retcode"](cmd, runas=runas)
            cmdlist = [
                "rpm",
                "-qp",
                "--queryformat",
                "{0}/%{{name}}/%{{version}}-%{{release}}".format(log_dir),
                srpm,
            ]
            log_dest = __salt__["cmd.run_stdout"](cmdlist, python_shell=False)
            for filename in os.listdir(results_dir):
                full = os.path.join(results_dir, filename)
                if filename.endswith("src.rpm"):
                    sdest = os.path.join(srpm_dir, filename)
                    try:
                        __salt__["file.makedirs_perms"](
                            name=srpm_dir, user=runas, group="mock"
                        )
                    except OSError as exc:
                        if exc.errno != errno.EEXIST:
                            raise
                    shutil.copy(full, sdest)
                    ret.setdefault("Source Packages", []).append(sdest)
                elif filename.endswith(".rpm"):
                    bdist = os.path.join(dest_dir, filename)
                    shutil.copy(full, bdist)
                    ret.setdefault("Packages", []).append(bdist)
                else:
                    log_file = os.path.join(log_dest, filename)
                    try:
                        __salt__["file.makedirs_perms"](
                            name=log_dest, user=runas, group="mock"
                        )
                    except OSError as exc:
                        if exc.errno != errno.EEXIST:
                            raise
                    shutil.copy(full, log_file)
                    ret.setdefault("Log Files", []).append(log_file)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error building from %s: %s", srpm, exc)
        finally:
            shutil.rmtree(results_dir)
    if retrc != 0:
        raise SaltInvocationError(
            "Building packages for destination directory {}, spec {}, sources {},"
            " failed with return error {}, check logs for further details".format(
                dest_dir, spec, sources, retrc
            )
        )
    shutil.rmtree(deps_dir)
    shutil.rmtree(srpm_build_dir)
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
    Make a package repository and optionally sign packages present

    Given the repodir, create a ``yum`` repository out of the rpms therein
    and optionally sign it and packages present, the name is directory to
    turn into a repo. This state is best used with onchanges linked to
    your package building states.

    repodir
        The directory to find packages that will be in the repository.

    keyid
        .. versionchanged:: 2016.3.0

        Optional Key ID to use in signing packages and repository.
        Utilizes Public and Private keys associated with keyid which have
        been loaded into the minion's Pillar data.

        For example, contents from a Pillar data file with named Public
        and Private keys as follows:

        .. code-block:: yaml

            gpg_pkg_priv_key: |
              -----BEGIN PGP PRIVATE KEY BLOCK-----
              Version: GnuPG v1

              lQO+BFciIfQBCADAPCtzx7I5Rl32escCMZsPzaEKWe7bIX1em4KCKkBoX47IG54b
              w82PCE8Y1jF/9Uk2m3RKVWp3YcLlc7Ap3gj6VO4ysvVz28UbnhPxsIkOlf2cq8qc
              .
              .
              Ebe+8JCQTwqSXPRTzXmy/b5WXDeM79CkLWvuGpXFor76D+ECMRPv/rawukEcNptn
              R5OmgHqvydEnO4pWbn8JzQO9YX/Us0SMHBVzLC8eIi5ZIopzalvX
              =JvW8
              -----END PGP PRIVATE KEY BLOCK-----

            gpg_pkg_priv_keyname: gpg_pkg_key.pem

            gpg_pkg_pub_key: |
              -----BEGIN PGP PUBLIC KEY BLOCK-----
              Version: GnuPG v1

              mQENBFciIfQBCADAPCtzx7I5Rl32escCMZsPzaEKWe7bIX1em4KCKkBoX47IG54b
              w82PCE8Y1jF/9Uk2m3RKVWp3YcLlc7Ap3gj6VO4ysvVz28UbnhPxsIkOlf2cq8qc
              .
              .
              bYP7t5iwJmQzRMyFInYRt77wkJBPCpJc9FPNebL9vlZcN4zv0KQta+4alcWivvoP
              4QIxE+/+trC6QRw2m2dHk6aAeq/J0Sc7ilZufwnNA71hf9SzRIwcFXMsLx4iLlki
              inNqW9c=
              =s1CX
              -----END PGP PUBLIC KEY BLOCK-----

            gpg_pkg_pub_keyname: gpg_pkg_key.pub

    env
        .. versionchanged:: 2016.3.0

        A dictionary of environment variables to be utilized in creating the
        repository.

        .. note::

            This parameter is not used for making ``yum`` repositories.

    use_passphrase : False
        .. versionadded:: 2016.3.0

        Use a passphrase with the signing key presented in ``keyid``.
        Passphrase is received from Pillar data which could be passed on the
        command line with ``pillar`` parameter.

        .. code-block:: bash

            pillar='{ "gpg_passphrase" : "my_passphrase" }'

        .. versionadded:: 3001.1

        RHEL 8 and above leverages gpg-agent and gpg-preset-passphrase for
        caching keys, etc.

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

        salt '*' pkgbuild.make_repo /var/www/html/

    """
    home = os.path.expanduser("~" + runas)
    rpmmacros = os.path.join(home, ".rpmmacros")
    if not os.path.exists(rpmmacros):
        _create_rpmmacros(runas)

    if gnupghome and env is None:
        env = {}
        env["GNUPGHOME"] = gnupghome

    use_gpg_agent, local_keyid, define_gpg_name, phrase = _get_gpg_key_resources(
        keyid, env, use_passphrase, gnupghome, runas
    )

    # sign_it_here
    for fileused in os.listdir(repodir):
        if fileused.endswith(".rpm"):
            abs_file = os.path.join(repodir, fileused)
            if use_gpg_agent:
                _sign_files_with_gpg_agent(
                    runas, local_keyid, abs_file, repodir, env, timeout
                )
            else:
                _sign_file(runas, define_gpg_name, phrase, abs_file, timeout)

    cmd = "createrepo --update {}".format(repodir)
    retrc = __salt__["cmd.run_all"](cmd, runas=runas)
    return retrc
