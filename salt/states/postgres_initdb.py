"""
Initialization of PostgreSQL data directory
===========================================

The postgres_initdb module is used to initialize the postgresql
data directory.

.. versionadded:: 2016.3.0

.. code-block:: yaml

    pgsql-data-dir:
      postgres_initdb.present:
        - name: /var/lib/pgsql/data
        - auth: password
        - user: postgres
        - password: strong_password
        - encoding: UTF8
        - locale: C
        - runas: postgres
        - checksums: True
        - waldir: /var/postgresql/wal
"""


def __virtual__():
    """
    Only load if the postgres module is present
    """
    if "postgres.datadir_init" not in __salt__:
        return (
            False,
            "Unable to load postgres module.  Make sure `postgres.bins_dir` is set.",
        )
    return True


def present(
    name,
    user=None,
    password=None,
    auth="password",
    encoding="UTF8",
    locale=None,
    runas=None,
    waldir=None,
    checksums=False,
):
    """
    Initialize the PostgreSQL data directory

    name
        The name of the directory to initialize

    user
        The database superuser name

    password
        The password to set for the postgres user

    auth
        The default authentication method for local connections

    encoding
        The default encoding for new databases

    locale
        The default locale for new databases

    waldir
        The transaction log (WAL) directory (default is to keep WAL
        inside the data directory)

        .. versionadded:: 2019.2.0

    checksums
        If True, the cluster will be created with data page checksums.

        .. note:: Data page checksums are supported since PostgreSQL 9.3.

        .. versionadded:: 2019.2.0

    runas
        The system user the operation should be performed on behalf of
    """
    _cmt = "Postgres data directory {} is already present".format(name)
    ret = {"name": name, "changes": {}, "result": True, "comment": _cmt}

    if not __salt__["postgres.datadir_exists"](name=name):
        if __opts__["test"]:
            ret["result"] = None
            _cmt = "Postgres data directory {} is set to be initialized".format(name)
            ret["comment"] = _cmt
            return ret

        kwargs = dict(
            user=user,
            password=password,
            auth=auth,
            encoding=encoding,
            locale=locale,
            waldir=waldir,
            checksums=checksums,
            runas=runas,
        )

        if __salt__["postgres.datadir_init"](name, **kwargs):
            _cmt = "Postgres data directory {} has been initialized".format(name)
            ret["comment"] = _cmt
            ret["changes"][name] = "Present"
        else:
            _cmt = "Postgres data directory {} initialization failed".format(name)
            ret["result"] = False
            ret["comment"] = _cmt

    return ret
