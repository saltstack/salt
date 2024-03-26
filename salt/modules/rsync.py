"""
Wrapper for rsync

.. versionadded:: 2014.1.0

This data can also be passed into :ref:`pillar <pillar-walk-through>`.
Options passed into opts will overwrite options passed into pillar.
"""

import errno
import logging
import re
import tempfile

import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "rsync"


def __virtual__():
    """
    Only load module if rsync binary is present
    """
    if salt.utils.path.which("rsync"):
        return __virtualname__
    return (
        False,
        "The rsync execution module cannot be loaded: "
        "the rsync binary is not in the path.",
    )


def _check(delete, force, update, passwordfile, exclude, excludefrom, dryrun, rsh):
    """
    Generate rsync options
    """
    options = ["-avz"]

    if delete:
        options.append("--delete")
    if force:
        options.append("--force")
    if update:
        options.append("--update")
    if rsh:
        options.append(f"--rsh={rsh}")
    if passwordfile:
        options.extend(["--password-file", passwordfile])
    if excludefrom:
        options.extend(["--exclude-from", excludefrom])
        if exclude:
            exclude = False
    if exclude:
        if isinstance(exclude, list):
            for ex_ in exclude:
                options.extend(["--exclude", ex_])
        else:
            options.extend(["--exclude", exclude])
    if dryrun:
        options.append("--dry-run")
    return options


def rsync(
    src,
    dst,
    delete=False,
    force=False,
    update=False,
    passwordfile=None,
    exclude=None,
    excludefrom=None,
    dryrun=False,
    rsh=None,
    additional_opts=None,
    saltenv="base",
):
    """
    .. versionchanged:: 2016.3.0
        Return data now contains just the output of the rsync command, instead
        of a dictionary as returned from :py:func:`cmd.run_all
        <salt.modules.cmdmod.run_all>`.

    Rsync files from src to dst

    src
        The source location where files will be rsynced from.

    dst
        The destination location where files will be rsynced to.

    delete : False
        Whether to enable the rsync `--delete` flag, which
        will delete extraneous files from dest dirs

    force : False
        Whether to enable the rsync `--force` flag, which
        will force deletion of dirs even if not empty.

    update : False
        Whether to enable the rsync `--update` flag, which
        forces rsync to skip any files which exist on the
        destination and have a modified time that is newer
        than the source file.

    passwordfile
        A file that contains a password for accessing an
        rsync daemon.  The file should contain just the
        password.

    exclude
        Whether to enable the rsync `--exclude` flag, which
        will exclude files matching a PATTERN.

    excludefrom
        Whether to enable the rsync `--excludefrom` flag, which
        will read exclude patterns from a file.

    dryrun : False
        Whether to enable the rsync `--dry-run` flag, which
        will perform a trial run with no changes made.

    rsh
        Whether to enable the rsync `--rsh` flag, to
        specify the remote shell to use.

    additional_opts
        Any additional rsync options, should be specified as a list.

    saltenv
        Specify a salt fileserver environment to be used.

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.rsync /path/to/src /path/to/dest delete=True update=True passwordfile=/etc/pass.crt exclude=exclude/dir
        salt '*' rsync.rsync /path/to/src delete=True excludefrom=/xx.ini
        salt '*' rsync.rsync /path/to/src delete=True exclude='[exclude1/dir,exclude2/dir]' additional_opts='["--partial", "--bwlimit=5000"]'
    """
    if not src:
        src = __salt__["config.option"]("rsync.src")
    if not dst:
        dst = __salt__["config.option"]("rsync.dst")
    if not delete:
        delete = __salt__["config.option"]("rsync.delete")
    if not force:
        force = __salt__["config.option"]("rsync.force")
    if not update:
        update = __salt__["config.option"]("rsync.update")
    if not passwordfile:
        passwordfile = __salt__["config.option"]("rsync.passwordfile")
    if not exclude:
        exclude = __salt__["config.option"]("rsync.exclude")
    if not excludefrom:
        excludefrom = __salt__["config.option"]("rsync.excludefrom")
    if not dryrun:
        dryrun = __salt__["config.option"]("rsync.dryrun")
    if not rsh:
        rsh = __salt__["config.option"]("rsync.rsh")
    if not src or not dst:
        raise SaltInvocationError("src and dst cannot be empty")

    tmp_src = None
    if src.startswith("salt://"):
        _src = src
        _path = re.sub("salt://", "", _src)
        src_is_dir = False
        if _path in __salt__["cp.list_master_dirs"](saltenv=saltenv):
            src_is_dir = True

        if src_is_dir:
            tmp_src = tempfile.mkdtemp()
            dir_src = __salt__["cp.get_dir"](_src, tmp_src, saltenv)
            if dir_src:
                src = tmp_src
                # Ensure src ends in / so we
                # get the contents not the tmpdir
                # itself.
                if not src.endswith("/"):
                    src = f"{src}/"
            else:
                raise CommandExecutionError(f"{src} does not exist")
        else:
            tmp_src = salt.utils.files.mkstemp()
            file_src = __salt__["cp.get_file"](_src, tmp_src, saltenv)
            if file_src:
                src = tmp_src
            else:
                raise CommandExecutionError(f"{src} does not exist")

    option = _check(
        delete, force, update, passwordfile, exclude, excludefrom, dryrun, rsh
    )

    if additional_opts and isinstance(additional_opts, list):
        option = option + additional_opts

    cmd = ["rsync"] + option + [src, dst]
    log.debug("Running rsync command: %s", cmd)
    try:
        return __salt__["cmd.run_all"](cmd, python_shell=False)
    except OSError as exc:
        raise CommandExecutionError(exc.strerror)
    finally:
        if tmp_src:
            __salt__["file.remove"](tmp_src)


def version():
    """
    .. versionchanged:: 2016.3.0
        Return data now contains just the version number as a string, instead
        of a dictionary as returned from :py:func:`cmd.run_all
        <salt.modules.cmdmod.run_all>`.

    Returns rsync version

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.version
    """
    try:
        out = __salt__["cmd.run_stdout"](["rsync", "--version"], python_shell=False)
    except OSError as exc:
        raise CommandExecutionError(exc.strerror)
    try:
        return out.split("\n")[0].split()[2]
    except IndexError:
        raise CommandExecutionError("Unable to determine rsync version")


def config(conf_path="/etc/rsyncd.conf"):
    """
    .. versionchanged:: 2016.3.0
        Return data now contains just the contents of the rsyncd.conf as a
        string, instead of a dictionary as returned from :py:func:`cmd.run_all
        <salt.modules.cmdmod.run_all>`.

    Returns the contents of the rsync config file

    conf_path : /etc/rsyncd.conf
        Path to the config file

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.config
    """
    ret = ""
    try:
        with salt.utils.files.fopen(conf_path, "r") as fp_:
            for line in fp_:
                ret += salt.utils.stringutils.to_unicode(line)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise CommandExecutionError(f"{conf_path} does not exist")
        elif exc.errno == errno.EACCES:
            raise CommandExecutionError(f"Unable to read {conf_path}, access denied")
        elif exc.errno == errno.EISDIR:
            raise CommandExecutionError(
                f"Unable to read {conf_path}, path is a directory"
            )
        else:
            raise CommandExecutionError(f"Error {exc.errno}: {exc.strerror}")
    else:
        return ret
