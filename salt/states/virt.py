# -*- coding: utf-8 -*-
"""
Manage virt
===========

For the key certificate this state uses the external pillar in the master to call
for the generation and signing of certificates for systems running libvirt:

.. code-block:: yaml

    libvirt_keys:
      virt.keys
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
import os

# Import Salt libs
import salt.utils.args
import salt.utils.files
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

try:
    import libvirt  # pylint: disable=import-error

    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False


__virtualname__ = "virt"


def __virtual__():
    """
    Only if virt module is available.

    :return:
    """

    if "virt.node_info" in __salt__:
        return __virtualname__
    return False


def keys(name, basepath="/etc/pki", **kwargs):
    """
    Manage libvirt keys.

    name
        The name variable used to track the execution

    basepath
        Defaults to ``/etc/pki``, this is the root location used for libvirt
        keys on the hypervisor

    The following parameters are optional:

        country
            The country that the certificate should use.  Defaults to US.

        .. versionadded:: 2018.3.0

        state
            The state that the certificate should use.  Defaults to Utah.

        .. versionadded:: 2018.3.0

        locality
            The locality that the certificate should use.
            Defaults to Salt Lake City.

        .. versionadded:: 2018.3.0

        organization
            The organization that the certificate should use.
            Defaults to Salted.

        .. versionadded:: 2018.3.0

        expiration_days
            The number of days that the certificate should be valid for.
            Defaults to 365 days (1 year)

        .. versionadded:: 2018.3.0

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # Grab all kwargs to make them available as pillar values
    # rename them to something hopefully unique to avoid
    # overriding anything existing
    pillar_kwargs = {}
    for key, value in six.iteritems(kwargs):
        pillar_kwargs["ext_pillar_virt.{0}".format(key)] = value

    pillar = __salt__["pillar.ext"]({"libvirt": "_"}, pillar_kwargs)
    paths = {
        "serverkey": os.path.join(basepath, "libvirt", "private", "serverkey.pem"),
        "servercert": os.path.join(basepath, "libvirt", "servercert.pem"),
        "clientkey": os.path.join(basepath, "libvirt", "private", "clientkey.pem"),
        "clientcert": os.path.join(basepath, "libvirt", "clientcert.pem"),
        "cacert": os.path.join(basepath, "CA", "cacert.pem"),
    }

    for key in paths:
        p_key = "libvirt.{0}.pem".format(key)
        if p_key not in pillar:
            continue
        if not os.path.exists(os.path.dirname(paths[key])):
            os.makedirs(os.path.dirname(paths[key]))
        if os.path.isfile(paths[key]):
            with salt.utils.files.fopen(paths[key], "r") as fp_:
                if salt.utils.stringutils.to_unicode(fp_.read()) != pillar[p_key]:
                    ret["changes"][key] = "update"
        else:
            ret["changes"][key] = "new"

    if not ret["changes"]:
        ret["comment"] = "All keys are correct"
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Libvirt keys are set to be updated"
        ret["changes"] = {}
    else:
        for key in ret["changes"]:
            with salt.utils.files.fopen(paths[key], "w+") as fp_:
                fp_.write(
                    salt.utils.stringutils.to_str(pillar["libvirt.{0}.pem".format(key)])
                )

        ret["comment"] = "Updated libvirt certs and keys"

    return ret


def _virt_call(
    domain,
    function,
    section,
    comment,
    state=None,
    connection=None,
    username=None,
    password=None,
    **kwargs
):
    """
    Helper to call the virt functions. Wildcards supported.

    :param domain: the domain to apply the function on. Can contain wildcards.
    :param function: virt function to call
    :param section: key for the changed domains in the return changes dictionary
    :param comment: comment to return
    :param state: the expected final state of the VM. If None the VM state won't be checked.
    :return: the salt state return
    """
    ret = {"name": domain, "changes": {}, "result": True, "comment": ""}
    targeted_domains = fnmatch.filter(__salt__["virt.list_domains"](), domain)
    changed_domains = list()
    ignored_domains = list()
    noaction_domains = list()
    for targeted_domain in targeted_domains:
        try:
            action_needed = True
            # If a state has been provided, use it to see if we have something to do
            if state is not None:
                domain_state = __salt__["virt.vm_state"](targeted_domain)
                action_needed = domain_state.get(targeted_domain) != state
            if action_needed:
                response = __salt__["virt.{0}".format(function)](
                    targeted_domain,
                    connection=connection,
                    username=username,
                    password=password,
                    **kwargs
                )
                if isinstance(response, dict):
                    response = response["name"]
                changed_domains.append({"domain": targeted_domain, function: response})
            else:
                noaction_domains.append(targeted_domain)
        except libvirt.libvirtError as err:
            ignored_domains.append(
                {"domain": targeted_domain, "issue": six.text_type(err)}
            )
    if not changed_domains:
        ret["result"] = not ignored_domains and bool(targeted_domains)
        ret["comment"] = "No changes had happened"
        if ignored_domains:
            ret["changes"] = {"ignored": ignored_domains}
    else:
        ret["changes"] = {section: changed_domains}
        ret["comment"] = comment

    return ret


def stopped(name, connection=None, username=None, password=None):
    """
    Stops a VM by shutting it down nicely.

    .. versionadded:: 2016.3.0

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    """

    return _virt_call(
        name,
        "shutdown",
        "stopped",
        "Machine has been shut down",
        state="shutdown",
        connection=connection,
        username=username,
        password=password,
    )


def powered_off(name, connection=None, username=None, password=None):
    """
    Stops a VM by power off.

    .. versionadded:: 2016.3.0

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    """
    return _virt_call(
        name,
        "stop",
        "unpowered",
        "Machine has been powered off",
        state="shutdown",
        connection=connection,
        username=username,
        password=password,
    )


def running(
    name,
    cpu=None,
    mem=None,
    image=None,
    vm_type=None,
    disk_profile=None,
    disks=None,
    nic_profile=None,
    interfaces=None,
    graphics=None,
    seed=True,
    install=True,
    pub_key=None,
    priv_key=None,
    update=False,
    connection=None,
    username=None,
    password=None,
    os_type=None,
    arch=None,
    boot=None,
):
    """
    Starts an existing guest, or defines and starts a new VM with specified arguments.

    .. versionadded:: 2016.3.0

    :param name: name of the virtual machine to run
    :param cpu: number of CPUs for the virtual machine to create
    :param mem: amount of memory in MiB for the new virtual machine
    :param image: disk image to use for the first disk of the new VM

        .. deprecated:: 2019.2.0
    :param vm_type: force virtual machine type for the new VM. The default value is taken from
        the host capabilities. This could be useful for example to use ``'qemu'`` type instead
        of the ``'kvm'`` one.

        .. versionadded:: 2019.2.0
    :param disk_profile:
        Name of the disk profile to use for the new virtual machine

        .. versionadded:: 2019.2.0
    :param disks:
        List of disk to create for the new virtual machine.
        See :ref:`init-disk-def` for more details on the items on this list.

        .. versionadded:: 2019.2.0
    :param nic_profile:
        Name of the network interfaces profile to use for the new virtual machine

        .. versionadded:: 2019.2.0
    :param interfaces:
        List of network interfaces to create for the new virtual machine.
        See :ref:`init-nic-def` for more details on the items on this list.

        .. versionadded:: 2019.2.0
    :param graphics:
        Graphics device to create for the new virtual machine.
        See :ref:`init-graphics-def` for more details on this dictionary

        .. versionadded:: 2019.2.0
    :param saltenv:
        Fileserver environment (Default: ``'base'``).
        See :mod:`cp module for more details <salt.modules.cp>`

        .. versionadded:: 2019.2.0
    :param seed: ``True`` to seed the disk image. Only used when the ``image`` parameter is provided.
                 (Default: ``True``)

        .. versionadded:: 2019.2.0
    :param install: install salt minion if absent (Default: ``True``)

        .. versionadded:: 2019.2.0
    :param pub_key: public key to seed with (Default: ``None``)

        .. versionadded:: 2019.2.0
    :param priv_key: public key to seed with (Default: ``None``)

        .. versionadded:: 2019.2.0
    :param seed_cmd: Salt command to execute to seed the image. (Default: ``'seed.apply'``)

        .. versionadded:: 2019.2.0
    :param update: set to ``True`` to update a defined module. (Default: ``False``)

        .. versionadded:: 2019.2.0
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param os_type:
        type of virtualization as found in the ``//os/type`` element of the libvirt definition.
        The default value is taken from the host capabilities, with a preference for ``hvm``.
        Only used when creating a new virtual machine.

        .. versionadded:: 3000
    :param arch:
        architecture of the virtual machine. The default value is taken from the host capabilities,
        but ``x86_64`` is prefed over ``i686``. Only used when creating a new virtual machine.

        .. versionadded:: 3000

    :param boot:
        Specifies kernel for the virtual machine, as well as boot parameters
        for the virtual machine. This is an optionl parameter, and all of the
        keys are optional within the dictionary. If a remote path is provided
        to kernel or initrd, salt will handle the downloading of the specified
        remote fild, and will modify the XML accordingly.

        .. code-block:: python

            {
                'kernel': '/root/f8-i386-vmlinuz',
                'initrd': '/root/f8-i386-initrd',
                'cmdline': 'console=ttyS0 ks=http://example.com/f8-i386/os/'
            }

        .. versionadded:: 3000

    .. rubric:: Example States

    Make sure an already-defined virtual machine called ``domain_name`` is running:

    .. code-block:: yaml

        domain_name:
          virt.running

    Do the same, but define the virtual machine if needed:

    .. code-block:: yaml

        domain_name:
          virt.running:
            - cpu: 2
            - mem: 2048
            - disk_profile: prod
            - disks:
              - name: system
                size: 8192
                overlay_image: True
                pool: default
                image: /path/to/image.qcow2
              - name: data
                size: 16834
            - nic_profile: prod
            - interfaces:
              - name: eth0
                mac: 01:23:45:67:89:AB
              - name: eth1
                type: network
                source: admin
            - graphics:
                type: spice
                listen:
                    type: address
                    address: 192.168.0.125

    """

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "{0} is running".format(name),
    }

    try:
        try:
            domain_state = __salt__["virt.vm_state"](name)
            if domain_state.get(name) != "running":
                action_msg = "started"
                if update:
                    status = __salt__["virt.update"](
                        name,
                        cpu=cpu,
                        mem=mem,
                        disk_profile=disk_profile,
                        disks=disks,
                        nic_profile=nic_profile,
                        interfaces=interfaces,
                        graphics=graphics,
                        live=False,
                        connection=connection,
                        username=username,
                        password=password,
                        boot=boot,
                    )
                    if status["definition"]:
                        action_msg = "updated and started"
                __salt__["virt.start"](name)
                ret["changes"][name] = "Domain {0}".format(action_msg)
                ret["comment"] = "Domain {0} {1}".format(name, action_msg)
            else:
                if update:
                    status = __salt__["virt.update"](
                        name,
                        cpu=cpu,
                        mem=mem,
                        disk_profile=disk_profile,
                        disks=disks,
                        nic_profile=nic_profile,
                        interfaces=interfaces,
                        graphics=graphics,
                        connection=connection,
                        username=username,
                        password=password,
                        boot=boot,
                    )
                    ret["changes"][name] = status
                    if status.get("errors", None):
                        ret[
                            "comment"
                        ] = "Domain {0} updated, but some live update(s) failed".format(
                            name
                        )
                    elif not status["definition"]:
                        ret["comment"] = "Domain {0} exists and is running".format(name)
                    else:
                        ret[
                            "comment"
                        ] = "Domain {0} updated, restart to fully apply the changes".format(
                            name
                        )
                else:
                    ret["comment"] = "Domain {0} exists and is running".format(name)
        except CommandExecutionError:
            if image:
                salt.utils.versions.warn_until(
                    "Sodium",
                    "'image' parameter has been deprecated. Rather use the 'disks' parameter "
                    "to override or define the image. 'image' will be removed in {version}.",
                )
            __salt__["virt.init"](
                name,
                cpu=cpu,
                mem=mem,
                os_type=os_type,
                arch=arch,
                image=image,
                hypervisor=vm_type,
                disk=disk_profile,
                disks=disks,
                nic=nic_profile,
                interfaces=interfaces,
                graphics=graphics,
                seed=seed,
                install=install,
                pub_key=pub_key,
                priv_key=priv_key,
                connection=connection,
                username=username,
                password=password,
                boot=boot,
            )
            ret["changes"][name] = "Domain defined and started"
            ret["comment"] = "Domain {0} defined and started".format(name)
    except libvirt.libvirtError as err:
        # Something bad happened when starting / updating the VM, report it
        ret["comment"] = six.text_type(err)
        ret["result"] = False

    return ret


def snapshot(name, suffix=None, connection=None, username=None, password=None):
    """
    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: 2016.3.0

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.snapshot:
            - suffix: periodic

        domain*:
          virt.snapshot:
            - suffix: periodic
    """

    return _virt_call(
        name,
        "snapshot",
        "saved",
        "Snapshot has been taken",
        suffix=suffix,
        connection=connection,
        username=username,
        password=password,
    )


# Deprecated states
def rebooted(name, connection=None, username=None, password=None):
    """
    Reboots VMs

    .. versionadded:: 2016.3.0

    :param name:

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    """

    return _virt_call(
        name,
        "reboot",
        "rebooted",
        "Machine has been rebooted",
        connection=connection,
        username=username,
        password=password,
    )


def unpowered(name):
    """
    .. deprecated:: 2016.3.0
       Use :py:func:`~salt.modules.virt.powered_off` instead.

    Stops a VM by power off.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    """

    return _virt_call(name, "stop", "unpowered", "Machine has been powered off")


def saved(name, suffix=None):
    """
    .. deprecated:: 2016.3.0
       Use :py:func:`~salt.modules.virt.snapshot` instead.

    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.saved:
            - suffix: periodic

        domain*:
          virt.saved:
            - suffix: periodic
    """

    return _virt_call(
        name, "snapshot", "saved", "Snapshots has been taken", suffix=suffix
    )


def reverted(
    name, snapshot=None, cleanup=False
):  # pylint: disable=redefined-outer-name
    """
    .. deprecated:: 2016.3.0

    Reverts to the particular snapshot.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.reverted:
            - cleanup: True

        domain_name_1:
          virt.reverted:
            - snapshot: snapshot_name
            - cleanup: False
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    try:
        domains = fnmatch.filter(__salt__["virt.list_domains"](), name)
        if not domains:
            ret["comment"] = 'No domains found for criteria "{0}"'.format(name)
        else:
            ignored_domains = list()
            if len(domains) > 1:
                ret["changes"] = {"reverted": list()}
            for domain in domains:
                result = {}
                try:
                    result = __salt__["virt.revert_snapshot"](
                        domain, snapshot=snapshot, cleanup=cleanup
                    )
                    result = {
                        "domain": domain,
                        "current": result["reverted"],
                        "deleted": result["deleted"],
                    }
                except CommandExecutionError as err:
                    if len(domains) > 1:
                        ignored_domains.append(
                            {"domain": domain, "issue": six.text_type(err)}
                        )
                if len(domains) > 1:
                    if result:
                        ret["changes"]["reverted"].append(result)
                else:
                    ret["changes"] = result
                    break

            ret["result"] = len(domains) != len(ignored_domains)
            if ret["result"]:
                ret["comment"] = "Domain{0} has been reverted".format(
                    len(domains) > 1 and "s" or ""
                )
            if ignored_domains:
                ret["changes"]["ignored"] = ignored_domains
            if not ret["changes"]["reverted"]:
                ret["changes"].pop("reverted")
    except libvirt.libvirtError as err:
        ret["comment"] = six.text_type(err)
    except CommandExecutionError as err:
        ret["comment"] = six.text_type(err)

    return ret


def network_running(
    name,
    bridge,
    forward,
    vport=None,
    tag=None,
    ipv4_config=None,
    ipv6_config=None,
    autostart=True,
    connection=None,
    username=None,
    password=None,
):
    """
    Defines and starts a new network with specified arguments.

    :param bridge: Bridge name
    :param forward: Forward mode(bridge, router, nat)
    :param vport: Virtualport type (Default: ``'None'``)
    :param tag: Vlan tag (Default: ``'None'``)
    :param ipv4_config:
        IPv4 network configuration. See the :py:func`virt.network_define
        <salt.modules.virt.network_define>` function corresponding parameter documentation
        for more details on this dictionary.
        (Default: None).

        .. versionadded:: 3000
    :param ipv6_config:
        IPv6 network configuration. See the :py:func`virt.network_define
        <salt.modules.virt.network_define>` function corresponding parameter documentation
        for more details on this dictionary.
        (Default: None).

        .. versionadded:: 3000
    :param autostart: Network autostart (default ``'True'``)
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.network_define

    .. code-block:: yaml

        network_name:
          virt.network_define:
            - bridge: main
            - forward: bridge
            - vport: openvswitch
            - tag: 180
            - autostart: True

    .. code-block:: yaml

        network_name:
          virt.network_define:
            - bridge: natted
            - forward: nat
            - ipv4_config:
                cidr: 192.168.42.0/24
                dhcp_ranges:
                  - start: 192.168.42.10
                    end: 192.168.42.25
                  - start: 192.168.42.100
                    end: 192.168.42.150
            - autostart: True

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        info = __salt__["virt.network_info"](
            name, connection=connection, username=username, password=password
        )
        if info:
            if info[name]["active"]:
                ret["comment"] = "Network {0} exists and is running".format(name)
            else:
                __salt__["virt.network_start"](
                    name, connection=connection, username=username, password=password
                )
                ret["changes"][name] = "Network started"
                ret["comment"] = "Network {0} started".format(name)
        else:
            __salt__["virt.network_define"](
                name,
                bridge,
                forward,
                vport=vport,
                tag=tag,
                ipv4_config=ipv4_config,
                ipv6_config=ipv6_config,
                autostart=autostart,
                start=True,
                connection=connection,
                username=username,
                password=password,
            )
            ret["changes"][name] = "Network defined and started"
            ret["comment"] = "Network {0} defined and started".format(name)
    except libvirt.libvirtError as err:
        ret["result"] = False
        ret["comment"] = err.get_error_message()

    return ret


def pool_running(
    name,
    ptype=None,
    target=None,
    permissions=None,
    source=None,
    transient=False,
    autostart=True,
    connection=None,
    username=None,
    password=None,
):
    """
    Defines and starts a new pool with specified arguments.

    .. versionadded:: 2019.2.0

    :param ptype: libvirt pool type
    :param target: full path to the target device or folder. (Default: ``None``)
    :param permissions:
        target permissions. See :ref:`pool-define-permissions` for more details on this structure.
    :param source:
        dictionary containing keys matching the ``source_*`` parameters in function
        :func:`salt.modules.virt.pool_define`.
    :param transient:
        when set to ``True``, the pool will be automatically undefined after being stopped. (Default: ``False``)
    :param autostart:
        Whether to start the pool when booting the host. (Default: ``True``)
    :param start:
        When ``True``, define and start the pool, otherwise the pool will be left stopped.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. code-block:: yaml

        pool_name:
          virt.pool_define

    .. code-block:: yaml

        pool_name:
          virt.pool_define:
            - ptype: netfs
            - target: /mnt/cifs
            - permissions:
                - mode: 0770
                - owner: 1000
                - group: 100
            - source:
                dir: samba_share
                hosts:
                  - one.example.com
                  - two.example.com
                format: cifs
            - autostart: True

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True if not __opts__["test"] else None,
        "comment": "",
    }

    try:
        info = __salt__["virt.pool_info"](
            name, connection=connection, username=username, password=password
        )
        needs_autostart = False
        if info:
            needs_autostart = (
                info[name]["autostart"]
                and not autostart
                or not info[name]["autostart"]
                and autostart
            )

            # Update can happen for both running and stopped pools
            needs_update = __salt__["virt.pool_update"](
                name,
                ptype=ptype,
                target=target,
                permissions=permissions,
                source_devices=(source or {}).get("devices"),
                source_dir=(source or {}).get("dir"),
                source_initiator=(source or {}).get("initiator"),
                source_adapter=(source or {}).get("adapter"),
                source_hosts=(source or {}).get("hosts"),
                source_auth=(source or {}).get("auth"),
                source_name=(source or {}).get("name"),
                source_format=(source or {}).get("format"),
                test=True,
                connection=connection,
                username=username,
                password=password,
            )
            if needs_update:
                if not __opts__["test"]:
                    __salt__["virt.pool_update"](
                        name,
                        ptype=ptype,
                        target=target,
                        permissions=permissions,
                        source_devices=(source or {}).get("devices"),
                        source_dir=(source or {}).get("dir"),
                        source_initiator=(source or {}).get("initiator"),
                        source_adapter=(source or {}).get("adapter"),
                        source_hosts=(source or {}).get("hosts"),
                        source_auth=(source or {}).get("auth"),
                        source_name=(source or {}).get("name"),
                        source_format=(source or {}).get("format"),
                        connection=connection,
                        username=username,
                        password=password,
                    )

                action = "started"
                if info[name]["state"] == "running":
                    action = "restarted"
                    if not __opts__["test"]:
                        __salt__["virt.pool_stop"](
                            name,
                            connection=connection,
                            username=username,
                            password=password,
                        )

                if not __opts__["test"]:
                    __salt__["virt.pool_build"](
                        name,
                        connection=connection,
                        username=username,
                        password=password,
                    )
                    __salt__["virt.pool_start"](
                        name,
                        connection=connection,
                        username=username,
                        password=password,
                    )

                autostart_str = ", autostart flag changed" if needs_autostart else ""
                ret["changes"][name] = "Pool updated, built{0} and {1}".format(
                    autostart_str, action
                )
                ret["comment"] = "Pool {0} updated, built{1} and {2}".format(
                    name, autostart_str, action
                )

            else:
                if info[name]["state"] == "running":
                    ret["comment"] = "Pool {0} unchanged and is running".format(name)
                    ret["result"] = True
                else:
                    ret["changes"][name] = "Pool started"
                    ret["comment"] = "Pool {0} started".format(name)
                    if not __opts__["test"]:
                        __salt__["virt.pool_start"](
                            name,
                            connection=connection,
                            username=username,
                            password=password,
                        )
        else:
            needs_autostart = autostart
            if not __opts__["test"]:
                __salt__["virt.pool_define"](
                    name,
                    ptype=ptype,
                    target=target,
                    permissions=permissions,
                    source_devices=(source or {}).get("devices"),
                    source_dir=(source or {}).get("dir"),
                    source_initiator=(source or {}).get("initiator"),
                    source_adapter=(source or {}).get("adapter"),
                    source_hosts=(source or {}).get("hosts"),
                    source_auth=(source or {}).get("auth"),
                    source_name=(source or {}).get("name"),
                    source_format=(source or {}).get("format"),
                    transient=transient,
                    start=False,
                    connection=connection,
                    username=username,
                    password=password,
                )

                __salt__["virt.pool_build"](
                    name, connection=connection, username=username, password=password
                )

                __salt__["virt.pool_start"](
                    name, connection=connection, username=username, password=password
                )
            if needs_autostart:
                ret["changes"][name] = "Pool defined, started and marked for autostart"
                ret[
                    "comment"
                ] = "Pool {0} defined, started and marked for autostart".format(name)
            else:
                ret["changes"][name] = "Pool defined and started"
                ret["comment"] = "Pool {0} defined and started".format(name)

        if needs_autostart:
            if not __opts__["test"]:
                __salt__["virt.pool_set_autostart"](
                    name,
                    state="on" if autostart else "off",
                    connection=connection,
                    username=username,
                    password=password,
                )
    except libvirt.libvirtError as err:
        ret["comment"] = err.get_error_message()
        ret["result"] = False

    return ret


def pool_deleted(name, purge=False, connection=None, username=None, password=None):
    """
    Deletes a virtual storage pool.

    :param name: the name of the pool to delete.
    :param purge:
        if ``True``, the volumes contained in the pool will be deleted as well as the pool itself.
        Note that these will be lost for ever. If ``False`` the pool will simply be undefined.
        (Default: ``False``)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    In order to be purged a storage pool needs to be running to get the list of volumes to delete.

    Some libvirt storage drivers may not implement deleting, those actions are implemented on a
    best effort idea. In any case check the result's comment property to see if any of the action
    was unsupported.

    .. code-block::yaml

        pool_name:
          uyuni_virt.pool_deleted:
            - purge: True

    .. versionadded:: 3000
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        info = __salt__["virt.pool_info"](
            name, connection=connection, username=username, password=password
        )
        if info:
            ret["changes"]["stopped"] = False
            ret["changes"]["deleted"] = False
            ret["changes"]["undefined"] = False
            ret["changes"]["deleted_volumes"] = []
            unsupported = []

            if info[name]["state"] == "running":
                if purge:
                    unsupported_volume_delete = [
                        "iscsi",
                        "iscsi-direct",
                        "mpath",
                        "scsi",
                    ]
                    if info[name]["type"] not in unsupported_volume_delete:
                        __salt__["virt.pool_refresh"](
                            name,
                            connection=connection,
                            username=username,
                            password=password,
                        )
                        volumes = __salt__["virt.pool_list_volumes"](
                            name,
                            connection=connection,
                            username=username,
                            password=password,
                        )
                        for volume in volumes:
                            # Not supported for iSCSI and SCSI drivers
                            deleted = __opts__["test"]
                            if not __opts__["test"]:
                                deleted = __salt__["virt.volume_delete"](
                                    name,
                                    volume,
                                    connection=connection,
                                    username=username,
                                    password=password,
                                )
                            if deleted:
                                ret["changes"]["deleted_volumes"].append(volume)
                    else:
                        unsupported.append("deleting volume")

                if not __opts__["test"]:
                    ret["changes"]["stopped"] = __salt__["virt.pool_stop"](
                        name,
                        connection=connection,
                        username=username,
                        password=password,
                    )
                else:
                    ret["changes"]["stopped"] = True

                if purge:
                    supported_pool_delete = [
                        "dir",
                        "fs",
                        "netfs",
                        "logical",
                        "vstorage",
                        "zfs",
                    ]
                    if info[name]["type"] in supported_pool_delete:
                        if not __opts__["test"]:
                            ret["changes"]["deleted"] = __salt__["virt.pool_delete"](
                                name,
                                connection=connection,
                                username=username,
                                password=password,
                            )
                        else:
                            ret["changes"]["deleted"] = True
                    else:
                        unsupported.append("deleting pool")

            if not __opts__["test"]:
                ret["changes"]["undefined"] = __salt__["virt.pool_undefine"](
                    name, connection=connection, username=username, password=password
                )
            else:
                ret["changes"]["undefined"] = True
                ret["result"] = None

            if unsupported:
                ret[
                    "comment"
                ] = 'Unsupported actions for pool of type "{0}": {1}'.format(
                    info[name]["type"], ", ".join(unsupported)
                )
        else:
            ret["comment"] = "Storage pool could not be found: {0}".format(name)
    except libvirt.libvirtError as err:
        ret["comment"] = "Failed deleting pool: {0}".format(err.get_error_message())
        ret["result"] = False

    return ret
