"""
Module to provide Postgres compatibility to salt for debian family specific tools.

"""

import logging
import shlex

import salt.utils.path

log = logging.getLogger(__name__)

__virtualname__ = "postgres"


def __virtual__():
    """
    Only load this module if the pg_createcluster bin exists
    """
    if salt.utils.path.which("pg_createcluster"):
        return __virtualname__
    return (
        False,
        "postgres execution module not loaded: pg_createcluste command not found.",
    )


def cluster_create(
    version,
    name="main",
    port=None,
    locale=None,
    encoding=None,
    datadir=None,
    allow_group_access=None,
    data_checksums=None,
    wal_segsize=None,
):
    """
    Adds a cluster to the Postgres server.

    .. warning:

       Only works for debian family distros so far.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.cluster_create '9.3'

        salt '*' postgres.cluster_create '9.3' 'main'

        salt '*' postgres.cluster_create '9.3' locale='fr_FR'

        salt '*' postgres.cluster_create '11' data_checksums=True wal_segsize='32'
    """

    cmd = [salt.utils.path.which("pg_createcluster")]
    if port:
        cmd += ["--port", str(port)]
    if locale:
        cmd += ["--locale", locale]
    if encoding:
        cmd += ["--encoding", encoding]
    if datadir:
        cmd += ["--datadir", datadir]
    cmd += [str(version), name]
    # initdb-specific options are passed after '--'
    if allow_group_access or data_checksums or wal_segsize:
        cmd += ["--"]
    if allow_group_access is True:
        cmd += ["--allow-group-access"]
    if data_checksums is True:
        cmd += ["--data-checksums"]
    if wal_segsize:
        cmd += ["--wal-segsize", wal_segsize]
    cmdstr = " ".join([shlex.quote(c) for c in cmd])
    ret = __salt__["cmd.run_all"](cmdstr, python_shell=False)
    if ret.get("retcode", 0) != 0:
        log.error("Error creating a Postgresql cluster %s/%s", version, name)
        return False
    return ret


def cluster_list(verbose=False):
    """
    Return a list of cluster of Postgres server (tuples of version and name).

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.cluster_list

        salt '*' postgres.cluster_list verbose=True
    """
    cmd = [salt.utils.path.which("pg_lsclusters"), "--no-header"]
    ret = __salt__["cmd.run_all"](" ".join([shlex.quote(c) for c in cmd]))
    if ret.get("retcode", 0) != 0:
        log.error("Error listing clusters")
    cluster_dict = _parse_pg_lscluster(ret["stdout"])
    if verbose:
        return cluster_dict
    return cluster_dict.keys()


def cluster_exists(version, name="main"):
    """
    Checks if a given version and name of a cluster exists.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.cluster_exists '9.3'

        salt '*' postgres.cluster_exists '9.3' 'main'
    """
    return f"{version}/{name}" in cluster_list()


def cluster_remove(version, name="main", stop=False):
    """
    Remove a cluster on a Postgres server. By default it doesn't try
    to stop the cluster.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.cluster_remove '9.3'

        salt '*' postgres.cluster_remove '9.3' 'main'

        salt '*' postgres.cluster_remove '9.3' 'main' stop=True

    """
    cmd = [salt.utils.path.which("pg_dropcluster")]
    if stop:
        cmd += ["--stop"]
    cmd += [str(version), name]
    cmdstr = " ".join([shlex.quote(c) for c in cmd])
    ret = __salt__["cmd.run_all"](cmdstr, python_shell=False)
    # FIXME - return Boolean ?
    if ret.get("retcode", 0) != 0:
        log.error("Error removing a Postgresql cluster %s/%s", version, name)
    else:
        ret["changes"] = f"Successfully removed cluster {version}/{name}"
    return ret


def _parse_pg_lscluster(output):
    """
    Helper function to parse the output of pg_lscluster
    """
    cluster_dict = {}
    for line in output.splitlines():
        version, name, port, status, user, datadir, log = line.split()
        cluster_dict[f"{version}/{name}"] = {
            "port": int(port),
            "status": status,
            "user": user,
            "datadir": datadir,
            "log": log,
        }
    return cluster_dict
