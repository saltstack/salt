"""
Manage virt
===========

For the key certificate this state uses the external pillar in the master to call
for the generation and signing of certificates for systems running libvirt:

.. code-block:: yaml

    libvirt_keys:
      virt.keys
"""


import fnmatch
import logging
import os

import salt.utils.args
import salt.utils.files
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    import libvirt  # pylint: disable=import-error

    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False


__virtualname__ = "virt"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only if virt module is available.

    :return:
    """
    if "virt.node_info" in __salt__:
        return __virtualname__
    return (False, "virt module could not be loaded")


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
    for key, value in kwargs.items():
        pillar_kwargs["ext_pillar_virt.{}".format(key)] = value

    pillar = __salt__["pillar.ext"]({"libvirt": "_"}, pillar_kwargs)
    paths = {
        "serverkey": os.path.join(basepath, "libvirt", "private", "serverkey.pem"),
        "servercert": os.path.join(basepath, "libvirt", "servercert.pem"),
        "clientkey": os.path.join(basepath, "libvirt", "private", "clientkey.pem"),
        "clientcert": os.path.join(basepath, "libvirt", "clientcert.pem"),
        "cacert": os.path.join(basepath, "CA", "cacert.pem"),
    }

    for key in paths:
        p_key = "libvirt.{}.pem".format(key)
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
                    salt.utils.stringutils.to_str(pillar["libvirt.{}.pem".format(key)])
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
    result = True if not __opts__["test"] else None
    ret = {"name": domain, "changes": {}, "result": result, "comment": ""}
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
                response = True
                if not __opts__["test"]:
                    response = __salt__["virt.{}".format(function)](
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
            ignored_domains.append({"domain": targeted_domain, "issue": str(err)})
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


def defined(
    name,
    cpu=None,
    mem=None,
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
    connection=None,
    username=None,
    password=None,
    os_type=None,
    arch=None,
    boot=None,
    numatune=None,
    boot_dev=None,
    hypervisor_features=None,
    clock=None,
    serials=None,
    consoles=None,
    stop_on_reboot=False,
    live=True,
    host_devices=None,
):
    """
    Starts an existing guest, or defines and starts a new VM with specified arguments.

    .. versionadded:: 3001

    :param name: name of the virtual machine to run
    :param cpu:
        Number of virtual CPUs to assign to the virtual machine or a dictionary with detailed information to configure
        cpu model and topology, numa node tuning, cpu tuning and iothreads allocation. The structure of the dictionary is
        documented in :ref:`init-cpu-def`.

        .. code-block:: yaml

             cpu:
               placement: static
               cpuset: 0-11
               current: 5
               maximum: 12
               vcpus:
                 0:
                   enabled: 'yes'
                   hotpluggable: 'no'
                   order: 1
                 1:
                   enabled: 'no'
                   hotpluggable: 'yes'
               match: minimum
               mode: custom
               check: full
               vendor: Intel
               model:
                 name: core2duo
                 fallback: allow
                 vendor_id: GenuineIntel
               topology:
                 sockets: 1
                 cores: 12
                 threads: 1
               cache:
                 level: 3
                 mode: emulate
               feature:
                 policy: optional
                 name: lahf_lm
               numa:
                 0:
                    cpus: 0-3
                    memory: 1g
                    discard: 'yes'
                    distances:
                      0: 10     # sibling id : value
                      1: 21
                      2: 31
                      3: 41
                 1:
                    cpus: 4-6
                    memory: 1g
                    memAccess: shared
                    distances:
                      0: 21
                      1: 10
                      2: 21
                      3: 31
               tuning:
                    vcpupin:
                      0: 1-4,^2  # vcpuid : cpuset
                      1: 0,1
                      2: 2,3
                      3: 0,4
                    emulatorpin: 1-3
                    iothreadpin:
                      1: 5,6    # iothread id: cpuset
                      2: 7,8
                    shares: 2048
                    period: 1000000
                    quota: -1
                    global_period: 1000000
                    global_quota: -1
                    emulator_period: 1000000
                    emulator_quota: -1
                    iothread_period: 1000000
                    iothread_quota: -1
                    vcpusched:
                      - scheduler: fifo
                        priority: 1
                      - scheduler: fifo
                        priority: 2
                        vcpus: 1-3
                      - scheduler: rr
                        priority: 3
                        vcpus: 4
                    iothreadsched:
                      - scheduler: batch
                        iothreads: 2
                    emulatorsched:
                      scheduler: idle
                    cachetune:
                      0-3:      # vcpus set
                        0:      # cache id
                          level: 3
                          type: both
                          size: 4
                        1:
                          level: 3
                          type: both
                          size: 6
                        monitor:
                          1: 3
                          0-3: 3
                      4-5:
                        monitor:
                          4: 3  # vcpus: level
                          5: 3
                    memorytune:
                      0-3:      # vcpus set
                        0: 60   # node id: bandwidth
                      4-5:
                        0: 60
               iothreads: 4

        .. versionadded:: 3003

    :param mem: Amount of memory to allocate to the virtual machine in MiB. Since 3002, a dictionary can be used to
        contain detailed configuration which support memory allocation or tuning. Supported parameters are ``boot``,
        ``current``, ``max``, ``slots``, ``hard_limit``, ``soft_limit``, ``swap_hard_limit``, ``min_guarantee``,
        ``hugepages`` ,  ``nosharepages``, ``locked``, ``source``, ``access``, ``allocation`` and ``discard``. The structure
        of the dictionary is documented in  :ref:`init-mem-def`. Both decimal and binary base are supported. Detail unit
        specification is documented  in :ref:`virt-units`. Please note that the value for ``slots`` must be an integer.

        .. code-block:: yaml

            boot: 1g
            current: 1g
            max: 1g
            slots: 10
            hard_limit: 1024
            soft_limit: 512m
            swap_hard_limit: 1g
            min_guarantee: 512mib
            hugepages:
              - size: 2m
              - nodeset: 0-2
                size: 1g
              - nodeset: 3
                size: 2g
            nosharepages: True
            locked: True
            source: file
            access: shared
            allocation: immediate
            discard: True

        .. versionchanged:: 3002

    :param vm_type: force virtual machine type for the new VM. The default value is taken from
        the host capabilities. This could be useful for example to use ``'qemu'`` type instead
        of the ``'kvm'`` one.
    :param disk_profile:
        Name of the disk profile to use for the new virtual machine
    :param disks:
        List of disk to create for the new virtual machine.
        See :ref:`init-disk-def` for more details on the items on this list.
    :param nic_profile:
        Name of the network interfaces profile to use for the new virtual machine
    :param interfaces:
        List of network interfaces to create for the new virtual machine.
        See :ref:`init-nic-def` for more details on the items on this list.
    :param graphics:
        Graphics device to create for the new virtual machine.
        See :ref:`init-graphics-def` for more details on this dictionary
    :param saltenv:
        Fileserver environment (Default: ``'base'``).
        See :mod:`cp module for more details <salt.modules.cp>`
    :param seed: ``True`` to seed the disk image. Only used when the ``image`` parameter is provided.
                 (Default: ``True``)
    :param install: install salt minion if absent (Default: ``True``)
    :param pub_key: public key to seed with (Default: ``None``)
    :param priv_key: public key to seed with (Default: ``None``)
    :param seed_cmd: Salt command to execute to seed the image. (Default: ``'seed.apply'``)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults
    :param os_type:
        type of virtualization as found in the ``//os/type`` element of the libvirt definition.
        The default value is taken from the host capabilities, with a preference for ``hvm``.
        Only used when creating a new virtual machine.
    :param arch:
        architecture of the virtual machine. The default value is taken from the host capabilities,
        but ``x86_64`` is prefed over ``i686``. Only used when creating a new virtual machine.

    :param boot:
        Specifies kernel, initial ramdisk and kernel command line parameters for the virtual machine.
        This is an optional parameter, all of the keys are optional within the dictionary.

        Refer to :ref:`init-boot-def` for the complete boot parameters description.

        To update any boot parameters, specify the new path for each. To remove any boot parameters,
        pass a None object, for instance: 'kernel': ``None``.

        .. versionadded:: 3000

    :param boot_dev:
        Space separated list of devices to boot from sorted by decreasing priority.
        Values can be ``hd``, ``fd``, ``cdrom`` or ``network``.

        By default, the value will ``"hd"``.

        .. versionadded:: 3002

    :param numatune:
        The optional numatune element provides details of how to tune the performance of a NUMA host via controlling NUMA
        policy for domain process. The optional ``memory`` element specifies how to allocate memory for the domain process
        on a NUMA host. ``memnode`` elements can specify memory allocation policies per each guest NUMA node. The definition
        used in the dictionary can be found at :ref:`init-cpu-def`.

        .. versionadded:: 3003

        .. code-block:: python

            {
                'memory': {'mode': 'strict', 'nodeset': '0-11'},
                'memnodes': {0: {'mode': 'strict', 'nodeset': 1}, 1: {'mode': 'preferred', 'nodeset': 2}}
            }

    :param hypervisor_features:
        Enable or disable hypervisor-specific features on the virtual machine.

        .. versionadded:: 3003

        .. code-block:: yaml

            hypervisor_features:
              kvm-hint-dedicated: True

    :param clock:
        Configure the guest clock.
        The value is a dictionary with the following keys:

        adjustment
            time adjustment in seconds or ``reset``

        utc
            set to ``False`` to use the host local time as the guest clock. Defaults to ``True``.

        timezone
            synchronize the guest to the correspding timezone

        timers
            a dictionary associating the timer name with its configuration.
            This configuration is a dictionary with the properties ``track``, ``tickpolicy``,
            ``catchup``, ``frequency``, ``mode``, ``present``, ``slew``, ``threshold`` and ``limit``.
            See `libvirt time keeping documentation <https://libvirt.org/formatdomain.html#time-keeping>`_ for the possible values.

        .. versionadded:: 3003

        Set the clock to local time using an offset in seconds
        .. code-block:: yaml

            clock:
              adjustment: 3600
              utc: False

        Set the clock to a specific time zone:

        .. code-block:: yaml

            clock:
              timezone: CEST

    :param serials:
        Dictionary providing details on the serials connection to create. (Default: ``None``)
        See :ref:`init-chardevs-def` for more details on the possible values.

        .. versionadded:: 3003
    :param consoles:
        Dictionary providing details on the consoles device to create. (Default: ``None``)
        See :ref:`init-chardevs-def` for more details on the possible values.

        .. versionadded:: 3003

    :param stop_on_reboot:
        If set to ``True`` the guest will stop instead of rebooting.
        This is specially useful when creating a virtual machine with an installation cdrom or
        an autoinstallation needing a special first boot configuration.
        Defaults to ``False``

        .. versionadded:: 3003

    :param live:
        If set to ``False`` the changes will not be applied live to the running instance, but will
        only apply at the next start. Note that reboot will not take those changes.

        .. versionadded:: 3003

    :param host_devices:
        List of host devices to passthrough to the guest.
        The value is a list of device names as provided by the :py:func:`~salt.modules.virt.node_devices` function.
        (Default: ``None``)

        .. versionadded:: 3003

    .. rubric:: Example States

    Make sure a virtual machine called ``domain_name`` is defined:

    .. code-block:: yaml

        domain_name:
          virt.defined:
            - cpu: 2
            - mem: 2048
            - boot_dev: network hd
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
        "result": True if not __opts__["test"] else None,
        "comment": "",
    }

    try:
        if name in __salt__["virt.list_domains"](
            connection=connection, username=username, password=password
        ):
            status = __salt__["virt.update"](
                name,
                cpu=cpu,
                mem=mem,
                disk_profile=disk_profile,
                disks=disks,
                nic_profile=nic_profile,
                interfaces=interfaces,
                graphics=graphics,
                live=live,
                connection=connection,
                username=username,
                password=password,
                boot=boot,
                numatune=numatune,
                serials=serials,
                consoles=consoles,
                test=__opts__["test"],
                boot_dev=boot_dev,
                hypervisor_features=hypervisor_features,
                clock=clock,
                stop_on_reboot=stop_on_reboot,
                host_devices=host_devices,
            )
            ret["changes"][name] = status
            if not status.get("definition"):
                ret["changes"] = {}
                ret["comment"] = "Domain {} unchanged".format(name)
                ret["result"] = True
            elif status.get("errors"):
                ret[
                    "comment"
                ] = "Domain {} updated with live update(s) failures".format(name)
            else:
                ret["comment"] = "Domain {} updated".format(name)
        else:
            if not __opts__["test"]:
                __salt__["virt.init"](
                    name,
                    cpu=cpu,
                    mem=mem,
                    os_type=os_type,
                    arch=arch,
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
                    numatune=numatune,
                    serials=serials,
                    consoles=consoles,
                    start=False,
                    boot_dev=boot_dev,
                    hypervisor_features=hypervisor_features,
                    clock=clock,
                    stop_on_reboot=stop_on_reboot,
                    host_devices=host_devices,
                )
            ret["changes"][name] = {"definition": True}
            ret["comment"] = "Domain {} defined".format(name)
    except libvirt.libvirtError as err:
        # Something bad happened when defining / updating the VM, report it
        ret["comment"] = str(err)
        ret["result"] = False

    return ret


def running(
    name,
    cpu=None,
    mem=None,
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
    connection=None,
    username=None,
    password=None,
    os_type=None,
    arch=None,
    boot=None,
    boot_dev=None,
    numatune=None,
    hypervisor_features=None,
    clock=None,
    serials=None,
    consoles=None,
    stop_on_reboot=False,
    host_devices=None,
):
    """
    Starts an existing guest, or defines and starts a new VM with specified arguments.

    .. versionadded:: 2016.3.0

    :param name: name of the virtual machine to run
    :param cpu:
        Number of virtual CPUs to assign to the virtual machine or a dictionary with detailed information to configure
        cpu model and topology, numa node tuning, cpu tuning and iothreads allocation. The structure of the dictionary is
        documented in :ref:`init-cpu-def`.

        To update any cpu parameters specify the new values to the corresponding tag. To remove any element or attribute,
        specify ``None`` object. Please note that ``None`` object is mapped to ``null`` in yaml, use ``null`` in sls file
        instead.
    :param mem: Amount of memory to allocate to the virtual machine in MiB. Since 3002, a dictionary can be used to
        contain detailed configuration which support memory allocation or tuning. Supported parameters are ``boot``,
        ``current``, ``max``, ``slots``, ``hard_limit``, ``soft_limit``, ``swap_hard_limit``, ``min_guarantee``,
        ``hugepages`` ,  ``nosharepages``, ``locked``, ``source``, ``access``, ``allocation`` and ``discard``. The structure
        of the dictionary is documented in  :ref:`init-mem-def`. Both decimal and binary base are supported. Detail unit
        specification is documented  in :ref:`virt-units`. Please note that the value for ``slots`` must be an integer.

        To remove any parameters, pass a None object, for instance: 'soft_limit': ``None``. Please note  that ``None``
        is mapped to ``null`` in sls file, pass ``null`` in sls file instead.

        .. code-block:: yaml

            - mem:
                hard_limit: null
                soft_limit: null

        .. versionchanged:: 3002
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
        Specifies kernel, initial ramdisk and kernel command line parameters for the virtual machine.
        This is an optional parameter, all of the keys are optional within the dictionary.

        Refer to :ref:`init-boot-def` for the complete boot parameters description.

        To update any boot parameters, specify the new path for each. To remove any boot parameters,
        pass a None object, for instance: 'kernel': ``None``.

        .. versionadded:: 3000
    :param serials:
        Dictionary providing details on the serials connection to create. (Default: ``None``)
        See :ref:`init-chardevs-def` for more details on the possible values.

        .. versionadded:: 3003
    :param consoles:
        Dictionary providing details on the consoles device to create. (Default: ``None``)
        See :ref:`init-chardevs-def` for more details on the possible values.

        .. versionadded:: 3003

    :param boot_dev:
        Space separated list of devices to boot from sorted by decreasing priority.
        Values can be ``hd``, ``fd``, ``cdrom`` or ``network``.

        By default, the value will ``"hd"``.

        .. versionadded:: 3002

    :param numatune:
        The optional numatune element provides details of how to tune the performance of a NUMA host via controlling NUMA
        policy for domain process. The optional ``memory`` element specifies how to allocate memory for the domain process
        on a NUMA host. ``memnode`` elements can specify memory allocation policies per each guest NUMA node. The definition
        used in the dictionary can be found at :ref:`init-cpu-def`.

        To update any numatune parameters, specify the new value. To remove any ``numatune`` parameters, pass a None object,
        for instance: 'numatune': ``None``. Please note that ``None`` is mapped to ``null`` in sls file, pass ``null`` in
        sls file instead.

        .. versionadded:: 3003

    :param stop_on_reboot:
        If set to ``True`` the guest will stop instead of rebooting.
        This is specially useful when creating a virtual machine with an installation cdrom or
        an autoinstallation needing a special first boot configuration.
        Defaults to ``False``

        .. versionadded:: 3003

    :param hypervisor_features:
        Enable or disable hypervisor-specific features on the virtual machine.

        .. versionadded:: 3003

        .. code-block:: yaml

            hypervisor_features:
              kvm-hint-dedicated: True

    :param clock:
        Configure the guest clock.
        The value is a dictionary with the following keys:

        adjustment
            time adjustment in seconds or ``reset``

        utc
            set to ``False`` to use the host local time as the guest clock. Defaults to ``True``.

        timezone
            synchronize the guest to the correspding timezone

        timers
            a dictionary associating the timer name with its configuration.
            This configuration is a dictionary with the properties ``track``, ``tickpolicy``,
            ``catchup``, ``frequency``, ``mode``, ``present``, ``slew``, ``threshold`` and ``limit``.
            See `libvirt time keeping documentation <https://libvirt.org/formatdomain.html#time-keeping>`_ for the possible values.

        .. versionadded:: 3003

        Set the clock to local time using an offset in seconds
        .. code-block:: yaml

            clock:
              adjustment: 3600
              utc: False

        Set the clock to a specific time zone:

        .. code-block:: yaml

            clock:
              timezone: CEST

    :param host_devices:
        List of host devices to passthrough to the guest.
        The value is a list of device names as provided by the :py:func:`~salt.modules.virt.node_devices` function.
        (Default: ``None``)

        .. versionadded:: 3003

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
            - boot_dev: network hd
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
    merged_disks = disks

    ret = defined(
        name,
        cpu=cpu,
        mem=mem,
        vm_type=vm_type,
        disk_profile=disk_profile,
        disks=merged_disks,
        nic_profile=nic_profile,
        interfaces=interfaces,
        graphics=graphics,
        seed=seed,
        install=install,
        pub_key=pub_key,
        priv_key=priv_key,
        os_type=os_type,
        arch=arch,
        boot=boot,
        boot_dev=boot_dev,
        numatune=numatune,
        hypervisor_features=hypervisor_features,
        clock=clock,
        stop_on_reboot=stop_on_reboot,
        connection=connection,
        username=username,
        password=password,
        serials=serials,
        consoles=consoles,
        host_devices=host_devices,
    )

    result = True if not __opts__["test"] else None
    if ret["result"] is None or ret["result"]:
        changed = ret["changes"].get(name, {}).get("definition", False)
        try:
            domain_state = __salt__["virt.vm_state"](name)
            if domain_state.get(name) != "running":
                if not __opts__["test"]:
                    __salt__["virt.start"](
                        name,
                        connection=connection,
                        username=username,
                        password=password,
                    )
                comment = "Domain {} started".format(name)
                if not ret["comment"].endswith("unchanged"):
                    comment = "{} and started".format(ret["comment"])
                ret["comment"] = comment
                if name not in ret["changes"]:
                    ret["changes"][name] = {}
                ret["changes"][name]["started"] = True
            elif not changed:
                ret["comment"] = "Domain {} exists and is running".format(name)

        except libvirt.libvirtError as err:
            # Something bad happened when starting / updating the VM, report it
            ret["comment"] = str(err)
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
            ret["comment"] = 'No domains found for criteria "{}"'.format(name)
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
                        ignored_domains.append({"domain": domain, "issue": str(err)})
                if len(domains) > 1:
                    if result:
                        ret["changes"]["reverted"].append(result)
                else:
                    ret["changes"] = result
                    break

            ret["result"] = len(domains) != len(ignored_domains)
            if ret["result"]:
                ret["comment"] = "Domain{} has been reverted".format(
                    len(domains) > 1 and "s" or ""
                )
            if ignored_domains:
                ret["changes"]["ignored"] = ignored_domains
            if not ret["changes"]["reverted"]:
                ret["changes"].pop("reverted")
    except libvirt.libvirtError as err:
        ret["comment"] = str(err)
    except CommandExecutionError as err:
        ret["comment"] = str(err)

    return ret


def network_defined(
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
    mtu=None,
    domain=None,
    nat=None,
    interfaces=None,
    addresses=None,
    physical_function=None,
    dns=None,
):
    """
    Defines a new network with specified arguments.

    :param name: Network name
    :param bridge: Bridge name
    :param forward: Forward mode(bridge, router, nat)

        .. versionchanged:: 3003
           a ``None`` value creates an isolated network with no forwarding at all

    :param vport: Virtualport type (Default: ``'None'``)
        The value can also be a dictionary with ``type`` and ``parameters`` keys.
        The ``parameters`` value is a dictionary of virtual port parameters.

        .. code-block:: yaml

          - vport:
              type: openvswitch
              parameters:
                interfaceid: 09b11c53-8b5c-4eeb-8f00-d84eaa0aaa4f

        .. versionchanged:: 3003
           possible dictionary value

    :param tag: Vlan tag (Default: ``'None'``)
        The value can also be a dictionary with the ``tags`` and optional ``trunk`` keys.
        ``trunk`` is a boolean value indicating whether to use VLAN trunking.
        ``tags`` is a list of dictionaries with keys ``id`` and ``nativeMode``.
        The ``nativeMode`` value can be one of ``tagged`` or ``untagged``.

        .. code-block:: yaml

          - tag:
              trunk: True
              tags:
                - id: 42
                  nativeMode: untagged
                - id: 47

        .. versionchanged:: 3003
           possible dictionary value

    :param ipv4_config:
        IPv4 network configuration. See the
        :py:func:`virt.network_define <salt.modules.virt.network_define>`
        function corresponding parameter documentation
        for more details on this dictionary.
        (Default: None).
    :param ipv6_config:
        IPv6 network configuration. See the :py:func:`virt.network_define
        <salt.modules.virt.network_define>` function corresponding parameter documentation
        for more details on this dictionary.
        (Default: None).
    :param autostart: Network autostart (default ``'True'``)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults
    :param mtu: size of the Maximum Transmission Unit (MTU) of the network.
        (default ``None``)

        .. versionadded:: 3003

    :param domain: DNS domain name of the DHCP server.
        The value is a dictionary with a mandatory ``name`` property and an optional ``localOnly`` boolean one.
        (default ``None``)

        .. code-block:: yaml

          - domain:
              name: lab.acme.org
              localOnly: True

        .. versionadded:: 3003

    :param nat: addresses and ports to route in NAT forward mode.
        The value is a dictionary with optional keys ``address`` and ``port``.
        Both values are a dictionary with ``start`` and ``end`` values.
        (default ``None``)

        .. code-block:: yaml

          - forward: nat
          - nat:
              address:
                start: 1.2.3.4
                end: 1.2.3.10
              port:
                start: 500
                end: 1000

        .. versionadded:: 3003

    :param interfaces: whitespace separated list of network interfaces devices that can be used for this network.
        (default ``None``)

        .. code-block:: yaml

          - forward: passthrough
          - interfaces: "eth10 eth11 eth12"

        .. versionadded:: 3003

    :param addresses: whitespace separated list of addreses of PCI devices that can be used for this network in `hostdev` forward mode.
        (default ``None``)

        .. code-block:: yaml

          - forward: hostdev
          - interfaces: "0000:04:00.1 0000:e3:01.2"

        .. versionadded:: 3003

    :param physical_function: device name of the physical interface to use in ``hostdev`` forward mode.
        (default ``None``)

        .. code-block:: yaml

          - forward: hostdev
          - physical_function: "eth0"

        .. versionadded:: 3003

    :param dns: virtual network DNS configuration
        The value is a dictionary described in :ref:`net-define-dns`.
        (default ``None``)

        .. code-block:: yaml

          - dns:
              forwarders:
                - domain: example.com
                  addr: 192.168.1.1
                - addr: 8.8.8.8
                - domain: www.example.com
              txt:
                example.com: "v=spf1 a -all"
                _http.tcp.example.com: "name=value,paper=A4"
              hosts:
                192.168.1.2:
                  - mirror.acme.lab
                  - test.acme.lab
              srvs:
                - name: ldap
                  protocol: tcp
                  domain: ldapserver.example.com
                  target: .
                  port: 389
                  priority: 1
                  weight: 10

        .. versionadded:: 3003

    .. versionadded:: 3001

    .. code-block:: yaml

        network_name:
          virt.network_defined

    .. code-block:: yaml

        network_name:
          virt.network_defined:
            - bridge: main
            - forward: bridge
            - vport: openvswitch
            - tag: 180
            - autostart: True

    .. code-block:: yaml

        network_name:
          virt.network_defined:
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
    ret = {
        "name": name,
        "changes": {},
        "result": True if not __opts__["test"] else None,
        "comment": "",
    }

    try:
        info = __salt__["virt.network_info"](
            name, connection=connection, username=username, password=password
        )
        if info and info[name]:
            needs_autostart = (
                info[name]["autostart"]
                and not autostart
                or not info[name]["autostart"]
                and autostart
            )
            needs_update = __salt__["virt.network_update"](
                name,
                bridge,
                forward,
                vport=vport,
                tag=tag,
                ipv4_config=ipv4_config,
                ipv6_config=ipv6_config,
                mtu=mtu,
                domain=domain,
                nat=nat,
                interfaces=interfaces,
                addresses=addresses,
                physical_function=physical_function,
                dns=dns,
                test=True,
                connection=connection,
                username=username,
                password=password,
            )
            if needs_update:
                if not __opts__["test"]:
                    __salt__["virt.network_update"](
                        name,
                        bridge,
                        forward,
                        vport=vport,
                        tag=tag,
                        ipv4_config=ipv4_config,
                        ipv6_config=ipv6_config,
                        mtu=mtu,
                        domain=domain,
                        nat=nat,
                        interfaces=interfaces,
                        addresses=addresses,
                        physical_function=physical_function,
                        dns=dns,
                        test=False,
                        connection=connection,
                        username=username,
                        password=password,
                    )
                action = ", autostart flag changed" if needs_autostart else ""
                ret["changes"][name] = "Network updated{}".format(action)
                ret["comment"] = "Network {} updated{}".format(name, action)
            else:
                ret["comment"] = "Network {} unchanged".format(name)
                ret["result"] = True
        else:
            needs_autostart = autostart
            if not __opts__["test"]:
                __salt__["virt.network_define"](
                    name,
                    bridge,
                    forward,
                    vport=vport,
                    tag=tag,
                    ipv4_config=ipv4_config,
                    ipv6_config=ipv6_config,
                    mtu=mtu,
                    domain=domain,
                    nat=nat,
                    interfaces=interfaces,
                    addresses=addresses,
                    physical_function=physical_function,
                    dns=dns,
                    autostart=False,
                    start=False,
                    connection=connection,
                    username=username,
                    password=password,
                )
            if needs_autostart:
                ret["changes"][name] = "Network defined, marked for autostart"
                ret["comment"] = "Network {} defined, marked for autostart".format(name)
            else:
                ret["changes"][name] = "Network defined"
                ret["comment"] = "Network {} defined".format(name)

        if needs_autostart:
            if not __opts__["test"]:
                __salt__["virt.network_set_autostart"](
                    name,
                    state="on" if autostart else "off",
                    connection=connection,
                    username=username,
                    password=password,
                )
    except libvirt.libvirtError as err:
        ret["result"] = False
        ret["comment"] = err.get_error_message()

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
    mtu=None,
    domain=None,
    nat=None,
    interfaces=None,
    addresses=None,
    physical_function=None,
    dns=None,
):
    """
    Defines and starts a new network with specified arguments.

    :param name: Network name
    :param bridge: Bridge name
    :param forward: Forward mode(bridge, router, nat)

        .. versionchanged:: 3003
           a ``None`` value creates an isolated network with no forwarding at all

    :param vport: Virtualport type (Default: ``'None'``)
        The value can also be a dictionary with ``type`` and ``parameters`` keys.
        The ``parameters`` value is a dictionary of virtual port parameters.

        .. code-block:: yaml

          - vport:
              type: openvswitch
              parameters:
                interfaceid: 09b11c53-8b5c-4eeb-8f00-d84eaa0aaa4f

        .. versionchanged:: 3003
           possible dictionary value

    :param tag: Vlan tag (Default: ``'None'``)
        The value can also be a dictionary with the ``tags`` and optional ``trunk`` keys.
        ``trunk`` is a boolean value indicating whether to use VLAN trunking.
        ``tags`` is a list of dictionaries with keys ``id`` and ``nativeMode``.
        The ``nativeMode`` value can be one of ``tagged`` or ``untagged``.

        .. code-block:: yaml

          - tag:
              trunk: True
              tags:
                - id: 42
                  nativeMode: untagged
                - id: 47

        .. versionchanged:: 3003
           possible dictionary value

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
    :param mtu: size of the Maximum Transmission Unit (MTU) of the network.
        (default ``None``)

        .. versionadded:: 3003

    :param domain: DNS domain name of the DHCP server.
        The value is a dictionary with a mandatory ``name`` property and an optional ``localOnly`` boolean one.
        (default ``None``)

        .. code-block:: yaml

          - domain:
              name: lab.acme.org
              localOnly: True

        .. versionadded:: 3003

    :param nat: addresses and ports to route in NAT forward mode.
        The value is a dictionary with optional keys ``address`` and ``port``.
        Both values are a dictionary with ``start`` and ``end`` values.
        (default ``None``)

        .. code-block:: yaml

          - forward: nat
          - nat:
              address:
                start: 1.2.3.4
                end: 1.2.3.10
              port:
                start: 500
                end: 1000

        .. versionadded:: 3003

    :param interfaces: whitespace separated list of network interfaces devices that can be used for this network.
        (default ``None``)

        .. code-block:: yaml

          - forward: passthrough
          - interfaces: "eth10 eth11 eth12"

        .. versionadded:: 3003

    :param addresses: whitespace separated list of addreses of PCI devices that can be used for this network in `hostdev` forward mode.
        (default ``None``)

        .. code-block:: yaml

          - forward: hostdev
          - interfaces: "0000:04:00.1 0000:e3:01.2"

        .. versionadded:: 3003

    :param physical_function: device name of the physical interface to use in ``hostdev`` forward mode.
        (default ``None``)

        .. code-block:: yaml

          - forward: hostdev
          - physical_function: "eth0"

        .. versionadded:: 3003

    :param dns: virtual network DNS configuration
        The value is a dictionary described in :ref:`net-define-dns`.
        (default ``None``)

        .. code-block:: yaml

          - dns:
              forwarders:
                - domain: example.com
                  addr: 192.168.1.1
                - addr: 8.8.8.8
                - domain: www.example.com
              txt:
                host.widgets.com.: "printer=lpr5"
                example.com.: "This domain name is reserved for use in documentation"
              hosts:
                192.168.1.2:
                  - mirror.acme.lab
                  - test.acme.lab
              srvs:
                - name: ldap
                  protocol: tcp
                  domain: ldapserver.example.com
                  target: .
                  port: 389
                  priority: 1
                  weight: 10

        .. versionadded:: 3003

    .. code-block:: yaml

        network_name:
          virt.network_running

    .. code-block:: yaml

        network_name:
          virt.network_running:
            - bridge: main
            - forward: bridge
            - vport: openvswitch
            - tag: 180
            - autostart: True

    .. code-block:: yaml

        network_name:
          virt.network_running:
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
    ret = network_defined(
        name,
        bridge,
        forward,
        vport=vport,
        tag=tag,
        ipv4_config=ipv4_config,
        ipv6_config=ipv6_config,
        mtu=mtu,
        domain=domain,
        nat=nat,
        interfaces=interfaces,
        addresses=addresses,
        physical_function=physical_function,
        dns=dns,
        autostart=autostart,
        connection=connection,
        username=username,
        password=password,
    )

    defined = name in ret["changes"] and ret["changes"][name].startswith(
        "Network defined"
    )

    result = True if not __opts__["test"] else None
    if ret["result"] is None or ret["result"]:
        try:
            info = __salt__["virt.network_info"](
                name, connection=connection, username=username, password=password
            )
            # In the corner case where test=True and the network wasn't defined
            # we may not get the network in the info dict and that is normal.
            if info.get(name, {}).get("active", False):
                ret["comment"] = "{} and is running".format(ret["comment"])
            else:
                if not __opts__["test"]:
                    __salt__["virt.network_start"](
                        name,
                        connection=connection,
                        username=username,
                        password=password,
                    )
                change = "Network started"
                if name in ret["changes"]:
                    change = "{} and started".format(ret["changes"][name])
                ret["changes"][name] = change
                ret["comment"] = "{} and started".format(ret["comment"])
            ret["result"] = result

        except libvirt.libvirtError as err:
            ret["result"] = False
            ret["comment"] = err.get_error_message()

    return ret


# Some of the libvirt storage drivers do not support the build action
BUILDABLE_POOL_TYPES = {"disk", "fs", "netfs", "dir", "logical", "vstorage", "zfs"}


def pool_defined(
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
    Defines a new pool with specified arguments.

    .. versionadded:: 3001

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
          virt.pool_defined:
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

                action = ""
                if info[name]["state"] != "running":
                    if ptype in BUILDABLE_POOL_TYPES:
                        if not __opts__["test"]:
                            # Storage pools build like disk or logical will fail if the disk or LV group
                            # was already existing. Since we can't easily figure that out, just log the
                            # possible libvirt error.
                            try:
                                __salt__["virt.pool_build"](
                                    name,
                                    connection=connection,
                                    username=username,
                                    password=password,
                                )
                            except libvirt.libvirtError as err:
                                log.warning(
                                    "Failed to build libvirt storage pool: %s",
                                    err.get_error_message(),
                                )
                        action = ", built"

                action = (
                    "{}, autostart flag changed".format(action)
                    if needs_autostart
                    else action
                )
                ret["changes"][name] = "Pool updated{}".format(action)
                ret["comment"] = "Pool {} updated{}".format(name, action)

            else:
                ret["comment"] = "Pool {} unchanged".format(name)
                ret["result"] = True
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

                if ptype in BUILDABLE_POOL_TYPES:
                    # Storage pools build like disk or logical will fail if the disk or LV group
                    # was already existing. Since we can't easily figure that out, just log the
                    # possible libvirt error.
                    try:
                        __salt__["virt.pool_build"](
                            name,
                            connection=connection,
                            username=username,
                            password=password,
                        )
                    except libvirt.libvirtError as err:
                        log.warning(
                            "Failed to build libvirt storage pool: %s",
                            err.get_error_message(),
                        )
            if needs_autostart:
                ret["changes"][name] = "Pool defined, marked for autostart"
                ret["comment"] = "Pool {} defined, marked for autostart".format(name)
            else:
                ret["changes"][name] = "Pool defined"
                ret["comment"] = "Pool {} defined".format(name)

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
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. code-block:: yaml

        pool_name:
          virt.pool_running

    .. code-block:: yaml

        pool_name:
          virt.pool_running:
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
    ret = pool_defined(
        name,
        ptype=ptype,
        target=target,
        permissions=permissions,
        source=source,
        transient=transient,
        autostart=autostart,
        connection=connection,
        username=username,
        password=password,
    )
    defined = name in ret["changes"] and ret["changes"][name].startswith("Pool defined")
    updated = name in ret["changes"] and ret["changes"][name].startswith("Pool updated")

    result = True if not __opts__["test"] else None
    if ret["result"] is None or ret["result"]:
        try:
            info = __salt__["virt.pool_info"](
                name, connection=connection, username=username, password=password
            )
            action = "started"
            # In the corner case where test=True and the pool wasn"t defined
            # we may get not get our pool in the info dict and that is normal.
            is_running = info.get(name, {}).get("state", "stopped") == "running"
            if is_running:
                if updated:
                    action = "restarted"
                    if not __opts__["test"]:
                        __salt__["virt.pool_stop"](
                            name,
                            connection=connection,
                            username=username,
                            password=password,
                        )
                    # if the disk or LV group is already existing build will fail (issue #56454)
                    if ptype in BUILDABLE_POOL_TYPES - {"disk", "logical"}:
                        if not __opts__["test"]:
                            __salt__["virt.pool_build"](
                                name,
                                connection=connection,
                                username=username,
                                password=password,
                            )
                        action = "built, {}".format(action)
                else:
                    action = "already running"
                    result = True

            if not is_running or updated or defined:
                if not __opts__["test"]:
                    __salt__["virt.pool_start"](
                        name,
                        connection=connection,
                        username=username,
                        password=password,
                    )

            comment = "Pool {}".format(name)
            change = "Pool"
            if name in ret["changes"]:
                comment = "{},".format(ret["comment"])
                change = "{},".format(ret["changes"][name])

            if action != "already running":
                ret["changes"][name] = "{} {}".format(change, action)

            ret["comment"] = "{} {}".format(comment, action)
            ret["result"] = result

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

    .. code-block:: yaml

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
                ret["comment"] = 'Unsupported actions for pool of type "{}": {}'.format(
                    info[name]["type"], ", ".join(unsupported)
                )
        else:
            ret["comment"] = "Storage pool could not be found: {}".format(name)
    except libvirt.libvirtError as err:
        ret["comment"] = "Failed deleting pool: {}".format(err.get_error_message())
        ret["result"] = False

    return ret


def volume_defined(
    pool,
    name,
    size,
    allocation=0,
    format=None,
    type=None,
    permissions=None,
    backing_store=None,
    nocow=False,
    connection=None,
    username=None,
    password=None,
):
    """
    Ensure a disk volume is existing.

    :param pool: name of the pool containing the volume
    :param name: name of the volume
    :param size: capacity of the volume to define in MiB
    :param allocation: allocated size of the volume in MiB. Defaults to 0.
    :param format:
        volume format. The allowed values are depending on the pool type.
        Check the virt.pool_capabilities output for the possible values and the default.
    :param type:
        type of the volume. One of file, block, dir, network, netdiri, ploop or None.
        By default, the type is guessed by libvirt from the pool type.
    :param permissions:
        Permissions to set on the target folder. This is mostly used for filesystem-based
        pool types. See :ref:`pool-define-permissions` for more details on this structure.
    :param backing_store:
        dictionary describing a backing file for the volume. It must contain a ``path``
        property pointing to the base volume and a ``format`` property defining the format
        of the base volume.

        The base volume format will not be guessed for security reasons and is thus mandatory.
    :param nocow: disable COW for the volume.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. rubric:: CLI Example:

    Volume on ESX:

    .. code-block:: yaml

        esx_volume:
          virt.volume_defined:
            - pool: "[local-storage]"
            - name: myvm/myvm.vmdk
            - size: 8192

    QCow2 volume with backing file:

    .. code-block:: bash

        myvolume:
          virt.volume_defined:
            - pool: default
            - name: myvm.qcow2
            - format: qcow2
            - size: 8192
            - permissions:
                mode: '0775'
                owner: '123'
                group: '345'
            - backing_store:
                path: /path/to/base.img
                format: raw
            - nocow: True

    .. versionadded:: 3001
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    pools = __salt__["virt.list_pools"](
        connection=connection, username=username, password=password
    )
    if pool not in pools:
        raise SaltInvocationError("Storage pool {} not existing".format(pool))

    vol_infos = (
        __salt__["virt.volume_infos"](
            pool, name, connection=connection, username=username, password=password
        )
        .get(pool, {})
        .get(name)
    )

    if vol_infos:
        ret["comment"] = "volume is existing"
        # if backing store or format are different, return an error
        backing_store_info = vol_infos.get("backing_store") or {}
        same_backing_store = backing_store_info.get("path") == (
            backing_store or {}
        ).get("path") and backing_store_info.get("format") == (backing_store or {}).get(
            "format"
        )
        if not same_backing_store or (
            vol_infos.get("format") != format and format is not None
        ):
            ret["result"] = False
            ret["comment"] = (
                "A volume with the same name but different backing store or format is"
                " existing"
            )
            return ret

        # otherwise assume the volume has already been defined
        # if the sizes don't match, issue a warning comment: too dangerous to do this for now
        if int(vol_infos.get("capacity")) != int(size) * 1024 * 1024:
            ret[
                "comment"
            ] = "The capacity of the volume is different, but no resize performed"
        return ret

    ret["result"] = None if __opts__["test"] else True
    test_comment = "would be "
    try:
        if not __opts__["test"]:
            __salt__["virt.volume_define"](
                pool,
                name,
                size,
                allocation=allocation,
                format=format,
                type=type,
                permissions=permissions,
                backing_store=backing_store,
                nocow=nocow,
                connection=connection,
                username=username,
                password=password,
            )
            test_comment = ""

        ret["comment"] = "Volume {} {}defined in pool {}".format(
            name, test_comment, pool
        )
        ret["changes"] = {"{}/{}".format(pool, name): {"old": "", "new": "defined"}}
    except libvirt.libvirtError as err:
        ret["comment"] = err.get_error_message()
        ret["result"] = False
    return ret
