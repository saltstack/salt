"""
Management of NFS exports
===============================================

.. versionadded:: 2018.3.0

To ensure an NFS export exists:

.. code-block:: yaml

    add_simple_export:
      nfs_export.present:
        - name:     '/srv/nfs'
        - hosts:    '10.0.2.0/24'
        - options:
          - 'rw'

This creates the following in /etc/exports:

.. code-block:: bash

    /srv/nfs 10.0.2.0/24(rw)

For more complex exports with multiple groups of hosts, use 'clients':

.. code-block:: yaml

    add_complex_export:
      nfs_export.present:
        - name: '/srv/nfs'
        - clients:
          # First export, same as simple one above
          - hosts: '10.0.2.0/24'
            options:
              - 'rw'
          # Second export
          - hosts: '*.example.com'
            options:
              - 'ro'
              - 'subtree_check'

This creates the following in /etc/exports:

.. code-block:: bash

    /srv/nfs 10.0.2.0/24(rw) 192.168.0.0/24,172.19.0.0/16(ro,subtree_check)

Any export of the given path will be modified to match the one specified.

To ensure an NFS export is absent:

.. code-block:: yaml

    delete_export:
      nfs_export.absent:
        - name: '/srv/nfs'

"""

import salt.utils.path


def __virtual__():
    """
    Only work with nfs tools installed
    """
    cmd = "exportfs"
    if salt.utils.path.which(cmd):
        return bool(cmd)

    return (
        False,
        "The nfs_exports state module failed to load: "
        "the exportfs binary is not in the path",
    )


def present(name, clients=None, hosts=None, options=None, exports="/etc/exports"):
    """
    Ensure that the named export is present with the given options

    name
        The export path to configure

    clients
        A list of hosts and the options applied to them.
        This option may not be used in combination with
        the 'hosts' or 'options' shortcuts.

    .. code-block:: yaml

        - clients:
          # First export
          - hosts: '10.0.2.0/24'
            options:
              - 'rw'
          # Second export
          - hosts: '*.example.com'
            options:
              - 'ro'
              - 'subtree_check'

    hosts
        A string matching a number of hosts, for example:

    .. code-block:: yaml

        hosts: '10.0.2.123'

        hosts: '10.0.2.0/24'

        hosts: 'minion1.example.com'

        hosts: '*.example.com'

        hosts: '*'

    options
        A list of NFS options, for example:

    .. code-block:: yaml

        options:
          - 'rw'
          - 'subtree_check'

    """
    path = name
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if not clients:
        if not hosts:
            ret["result"] = False
            ret["comment"] = "Either 'clients' or 'hosts' must be defined"
            return ret
        # options being None is handled by add_export()
        clients = [{"hosts": hosts, "options": options}]

    old = __salt__["nfs3.list_exports"](exports)
    if path in old:
        if old[path] == clients:
            ret["result"] = True
            ret["comment"] = f"Export {path} already configured"
            return ret

        ret["changes"]["new"] = clients
        ret["changes"]["old"] = old[path]
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Export {path} would be changed"
            return ret

        __salt__["nfs3.del_export"](exports, path)

    else:
        ret["changes"]["old"] = None
        ret["changes"]["new"] = clients
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Export {path} would be added"
            return ret

    add_export = __salt__["nfs3.add_export"]
    for exp in clients:
        add_export(exports, path, exp["hosts"], exp["options"])

    ret["changes"]["new"] = clients

    try_reload = __salt__["nfs3.reload_exports"]()
    ret["comment"] = try_reload["stderr"]
    ret["result"] = try_reload["result"]
    return ret


def absent(name, exports="/etc/exports"):
    """
    Ensure that the named path is not exported

    name
        The export path to remove
    """

    path = name
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    old = __salt__["nfs3.list_exports"](exports)
    if path in old:
        if __opts__["test"]:
            ret["comment"] = f"Export {path} would be removed"
            ret["changes"][path] = old[path]
            ret["result"] = None
            return ret

        __salt__["nfs3.del_export"](exports, path)
        try_reload = __salt__["nfs3.reload_exports"]()
        if not try_reload["result"]:
            ret["comment"] = try_reload["stderr"]
        else:
            ret["comment"] = f"Export {path} removed"

        ret["result"] = try_reload["result"]
        ret["changes"][path] = old[path]
    else:
        ret["comment"] = f"Export {path} already absent"
        ret["result"] = True

    return ret
