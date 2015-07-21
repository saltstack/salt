===========================
Getting Started With VMware
===========================

.. versionadded:: 2015.5.4

**Author**: Nitin Madhok <nmadhok@clemson.edu>

The VMware cloud module allows you to manage VMware ESX, ESXi, and vCenter.


Dependencies
============
The vmware module for Salt Cloud requires the ``pyVmomi`` package, which is
available at PyPI:

https://pypi.python.org/pypi/pyvmomi

This package can be installed using `pip` or `easy_install`:

.. code-block:: bash

    pip install pyvmomi
    easy_install pyvmomi


Configuration
=============
The VMware cloud module needs the vCenter URL, username and password to be
set up in the cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

.. code-block:: yaml

    my-vmware-config:
      provider: vmware
      user: "DOMAIN\user"
      password: "verybadpass"
      url: "vcenter01.domain.com"

    vmware-vcenter02:
      provider: vmware
      user: "DOMAIN\user"
      password: "verybadpass"
      url: "vcenter02.domain.com"

    vmware-vcenter03:
      provider: vmware
      user: "DOMAIN\user"
      password: "verybadpass"
      url: "vcenter03.domain.com"
      protocol: "http"
      port: 80

.. note::

    Optionally, ``protocol`` and ``port`` can be specified if the vCenter
    server is not using the defaults. Default is ``protocol: https`` and
    ``port: 443``.

.. _vmware-cloud-profile:

Profiles
========
Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/vmware.conf``:

.. code-block:: yaml

    vmware-centos6.5:
      provider: vmware-vcenter01
      clonefrom: test-vm

      ## Optional arguments
      num_cpus: 4
      memory: 8GB
      devices:
        cd:
          CD/DVD drive 1:
            device_type: datastore_iso_file
            iso_path: "[nap004-1] vmimages/tools-isoimages/linux.iso"
          CD/DVD drive 2:
            device_type: client_device
            mode: atapi
          CD/DVD drive 3:
            device_type: client_device
            mode: passthrough
        disk:
          Hard disk 1:
            size: 30
          Hard disk 2:
            size: 20
          Hard disk 3:
            size: 5
        network:
          Network adapter 1:
            name: 10.20.30-400-Test
            switch_type: standard
            ip: 10.20.30.123
            gateway: [10.20.30.110]
            subnet_mask: 255.255.255.128
            domain: mycompany.com
          Network adapter 2:
            name: 10.30.40-500-Dev-DHCP
            adapter_type: e1000
            switch_type: distributed
          Network adapter 3:
            name: 10.40.50-600-Prod
            adapter_type: vmxnet3
            switch_type: distributed
            ip: 10.40.50.123
            gateway: [10.40.50.110]
            subnet_mask: 255.255.255.128
            domain: mycompany.com
        scsi:
          SCSI controller 1:
            type: lsilogic
          SCSI controller 2:
            type: lsilogic_sas
            bus_sharing: virtual
          SCSI controller 3:
            type: paravirtual
            bus_sharing: physical

      domain: mycompany.com
      dns_servers:
        - 123.127.255.240
        - 123.127.255.241
        - 123.127.255.242

      # If cloning from template, either resourcepool or cluster MUST be specified!
      resourcepool: Resources
      cluster: Prod

      datastore: HUGE-DATASTORE-Cluster
      folder: Development
      datacenter: DC1
      host: c4212n-002.domain.com
      template: False
      power_on: True
      extra_config:
        mem.hotadd: 'yes'
        guestinfo.foo: bar
        guestinfo.domain: foobar.com
        guestinfo.customVariable: customValue

      deploy: True
      private_key: /root/.ssh/mykey.pem
      ssh_username: cloud-user
      password: veryVeryBadPassword
      minion:
        master: 123.127.193.105

      file_map:
        /path/to/local/custom/script: /path/to/remote/script
        /path/to/local/file: /path/to/remote/file
        /srv/salt/yum/epel.repo: /etc/yum.repos.d/epel.repo


``provider``
    Enter the name that was specified when the cloud provider config was created.

``clonefrom``
    Enter the name of the VM/template to clone from.

``num_cpus``
    Enter the number of vCPUS that you want the VM/template to have. If not specified,
    the current VM/template\'s vCPU count is used.

``memory``
    Enter the memory size (in MB or GB) that you want the VM/template to have. If
    not specified, the current VM/template\'s memory size is used. Example
    ``memory: 8GB`` or ``memory: 8192MB``.

``devices``
    Enter the device specifications here. Currently, the following devices can be
    created or reconfigured:

    cd
        Enter the CD/DVD drive specification here. If the CD/DVD drive doesn\'t exist,
        it will be created with the specified configuration. If the CD/DVD drive
        already exists, it will be reconfigured with the specifications. The following
        options can be specified per CD/DVD drive:

        device_type
            Specify how the CD/DVD drive should be used. Currently supported types are
            ``client_device`` and ``datastore_iso_file``. Default is
            ``device_type: client_device``
        iso_path
            Enter the path to the iso file present on the datastore only if
            ``device_type: datastore_iso_file``. The syntax to specify this is
            ``iso_path: "[datastoreName] vmimages/tools-isoimages/linux.iso"``. This
            field is ignored if ``device_type: client_device``
        mode
            Enter the mode of connection only if ``device_type: client_device``. Currently
            supported modes are ``passthrough`` and ``atapi``. This field is ignored if
            ``device_type: datastore_iso_file``. Default is ``mode: passthrough``

    disk
        Enter the disk specification here. If the hard disk doesn\'t exist, it will
        be created with the provided size. If the hard disk already exists, it will
        be expanded if the provided size is greater than the current size of the disk.

    network
        Enter the network adapter specification here. If the network adapter doesn\'t
        exist, a new network adapter will be created with the specified network name,
        type and other configuration. If the network adapter already exists, it will
        be reconfigured with the specifications. The following additional options can
        be specified per network adapter (See example above):

        name
            Enter the network name you want the network adapter to be mapped to.

        adapter_type
            Enter the network adapter type you want to create. Currently supported
            types are ``vmxnet``, ``vmxnet2``, ``vmxnet3``, ``e1000`` and ``e1000e``.
            If no type is specified, by default ``vmxnet3`` will be used.

        switch_type
            Enter the type of switch to use. This decides whether to use a standard
            switch network or a distributed virtual portgroup. Currently supported
            types are ``standard`` for standard portgroups and ``distributed`` for
            distributed virtual portgroups.

        ip
            Enter the static IP you want the network adapter to be mapped to. If the
            network specified is DHCP enabled, you do not have to specify this.

        gateway
            Enter the gateway for the network as a list. If the network specified
            is DHCP enabled, you do not have to specify this.

        subnet_mask
            Enter the subnet mask for the network. If the network specified is DHCP
            enabled, you do not have to specify this.

        domain
            Enter the domain to be used with the network adapter. If the network
            specified is DHCP enabled, you do not have to specify this.

    scsi
        Enter the SCSI adapter specification here. If the SCSI adapter doesn\'t exist,
        a new SCSI adapter will be created of the specified type. If the SCSI adapter
        already exists, it will be reconfigured with the specifications. The following
        additional options can be specified per SCSI adapter:

        type
            Enter the SCSI adapter type you want to create. Currently supported
            types are ``lsilogic``, ``lsilogic_sas`` and ``paravirtual``. Type must
            be specified when creating a new SCSI adapter.

        bus_sharing
            Specify this if sharing of virtual disks between virtual machines is desired.
            The following can be specified:

            virtual
                Virtual disks can be shared between virtual machines on the same server.

            physical
                Virtual disks can be shared between virtual machines on any server.

            no
                Virtual disks cannot be shared between virtual machines.

``domain``
    Enter the global domain name to be used for DNS. If not specified and if the VM name
    is a FQDN, ``domain`` is set to the domain from the VM name. Default is ``local``.

``dns_servers``
    Enter the list of DNS servers to use in order of priority.

``resourcepool``
    Enter the name of the resourcepool to which the new virtual machine should be
    attached. This determines what compute resources will be available to the clone.

    .. note::

        - For a clone operation from a virtual machine, it will use the same
          resourcepool as the original virtual machine unless specified.
        - For a clone operation from a template to a virtual machine, specifying
          either this or cluster is required. If both are specified, the resourcepool
          value will be used.
        - For a clone operation to a template, this argument is ignored.

``cluster``
    Enter the name of the cluster whose resource pool the new virtual machine should
    be attached to.

    .. note::

        - For a clone operation from a virtual machine, it will use the same cluster\'s
          resourcepool as the original virtual machine unless specified.
        - For a clone operation from a template to a virtual machine, specifying either
          this or resourcepool is required. If both are specified, the resourcepool
          value will be used.
        - For a clone operation to a template, this argument is ignored.

``datastore``
    Enter the name of the datastore or the datastore cluster where the virtual machine
    should be located on physical storage. If not specified, the current datastore is
    used.

    .. note::

        - If you specify a datastore cluster name, DRS Storage recommendation is
          automatically applied.
        - If you specify a datastore name, DRS Storage recommendation is disabled.

``folder``
    Enter the name of the folder that will contain the new virtual machine.

    .. note::

        - For a clone operation from a VM/template, the new VM/template will be added
          to the same folder that the original VM/template belongs to unless specified.
        - If both folder and datacenter are specified, the folder value will be used.

``datacenter``
    Enter the name of the datacenter that will contain the new virtual machine.

    .. note::

        - For a clone operation from a VM/template, the new VM/template will be added
          to the same folder that the original VM/template belongs to unless specified.
        - If both folder and datacenter are specified, the folder value will be used.

``host``
    Enter the name of the target host where the virtual machine should be registered.

    If not specified:

    .. note::

        - If resource pool is not specified, current host is used.
        - If resource pool is specified, and the target pool represents a stand-alone
          host, the host is used.
        - If resource pool is specified, and the target pool represents a DRS-enabled
          cluster, a host selected by DRS is used.
        - If resource pool is specified and the target pool represents a cluster without
          DRS enabled, an InvalidArgument exception be thrown.

``template``
    Specifies whether the new virtual machine should be marked as a template or not.
    Default is ``template: False``.

``power_on``
    Specifies whether the new virtual machine should be powered on or not. If
    ``template: True`` is set, this field is ignored. Default is ``power_on: True``.

``extra_config``
    Specifies the additional configuration information for the virtual machine. This
    describes a set of modifications to the additional options. If the key is already
    present, it will be reset with the new value provided. Otherwise, a new option is
    added. Keys with empty values will be removed.

``deploy``
    Specifies if salt should be installed on the newly created VM. Default is ``True``
    so salt will be installed using the bootstrap script. If ``template: True`` or
    ``power_on: False`` is set, this field is ignored and salt will not be installed.

``private_key``
    Specify the path to the private key to use to be able to ssh to the VM.

``ssh_username``
    Specify the username to use in order to ssh to the VM. Default is ``root``

``password``
    Specify a password to use in order to ssh to the VM. If ``private_key`` is
    specified, you do not need to specify this.

``minion``
    Specify custom minion configuration you want the salt minion to have. A good example
    would be to specify the ``master`` as the IP/DNS name of the master.

``file_map``
    Specify file/files you want to copy to the VM before the bootstrap script is run
    and salt is installed. A good example of using this would be if you need to put
    custom repo files on the server in case your server will be in a private network
    and cannot reach external networks.
