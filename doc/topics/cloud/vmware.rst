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

The VMware cloud module needs the vCenter or ESX/ESXi URL, username and password to be
set up in the cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

.. code-block:: yaml

    my-vmware-config:
      driver: vmware
      user: 'DOMAIN\user'
      password: 'verybadpass'
      url: '10.20.30.40'

    vcenter01:
      driver: vmware
      user: 'DOMAIN\user'
      password: 'verybadpass'
      url: 'vcenter01.domain.com'
      protocol: 'https'
      port: 443

    vcenter02:
      driver: vmware
      user: 'DOMAIN\user'
      password: 'verybadpass'
      url: 'vcenter02.domain.com'
      protocol: 'http'
      port: 80

    esx01:
      driver: vmware
      user: 'admin'
      password: 'verybadpass'
      url: 'esx01.domain.com'

.. note::

    Optionally, ``protocol`` and ``port`` can be specified if the vCenter
    server is not using the defaults. Default is ``protocol: https`` and
    ``port: 443``.

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider configuration was renamed to ``driver``.
    This change was made to avoid confusion with the ``provider`` parameter that is
    used in cloud profile configuration. Cloud provider configuration now uses ``driver``
    to refer to the salt-cloud driver that provides the underlying functionality to
    connect to a cloud provider, while cloud profile configuration continues to use
    ``provider`` to refer to the cloud provider configuration that you define.

.. _vmware-cloud-profile:

Profiles
========

Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/vmware.conf``:

.. code-block:: yaml

    vmware-centos6.5:
      provider: vcenter01
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
            controller: IDE 2
          CD/DVD drive 3:
            device_type: client_device
            mode: passthrough
            controller: IDE 3
        disk:
          Hard disk 1:
            size: 30
          Hard disk 2:
            size: 20
            controller: SCSI controller 2
          Hard disk 3:
            size: 5
            controller: SCSI controller 3
        network:
          Network adapter 1:
            name: 10.20.30-400-Test
            switch_type: standard
            ip: 10.20.30.123
            gateway: [10.20.30.110]
            subnet_mask: 255.255.255.128
            domain: example.com
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
            domain: example.com
        scsi:
          SCSI controller 1:
            type: lsilogic
          SCSI controller 2:
            type: lsilogic_sas
            bus_sharing: virtual
          SCSI controller 3:
            type: paravirtual
            bus_sharing: physical
        ide:
          IDE 2
          IDE 3

      domain: example.com
      dns_servers:
        - 123.127.255.240
        - 123.127.255.241
        - 123.127.255.242

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
      customization: True
      private_key: /root/.ssh/mykey.pem
      ssh_username: cloud-user
      password: veryVeryBadPassword
      minion:
        master: 123.127.193.105

      file_map:
        /path/to/local/custom/script: /path/to/remote/script
        /path/to/local/file: /path/to/remote/file
        /srv/salt/yum/epel.repo: /etc/yum.repos.d/epel.repo

      hardware_version: 10
      image: centos64Guest
      
      #For Windows VM
      win_username: Administrator
      win_password: administrator
      win_organization_name: ABC-Corp
      plain_text: True
      win_installer: /root/Salt-Minion-2015.8.4-AMD64-Setup.exe
      win_user_fullname: Windows User

``provider``
    Enter the name that was specified when the cloud provider config was created.

``clonefrom``
    Enter the name of the VM/template to clone from. If not specified, the VM will be created
    without cloning.

``num_cpus``
    Enter the number of vCPUS that you want the VM/template to have. If not specified,
    the current VM/template\'s vCPU count is used.

``cores_per_socket``
    .. versionadded:: Boron
    Enter the number of cores per vCPU that you want the VM/template to have. If not specified,
    this will default to 1. Note that you cannot assign more cores per socket than the total 
    number of vCPUs assigned to the VM.

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
        controller
            Specify the IDE controller label to which this drive should be attached.
            This should be specified only when creating both the specified IDE
            controller as well as the CD/DVD drive at the same time.

    disk
        Enter the disk specification here. If the hard disk doesn\'t exist, it will
        be created with the provided size. If the hard disk already exists, it will
        be expanded if the provided size is greater than the current size of the disk.

        size
            Enter the size of disk in GB
        thin_provision
            Specifies whether the disk should be thin provisioned or not. Default is ``thin_provision: False``.
            .. versionadded:: 2016.3.0
        controller
            Specify the SCSI controller label to which this disk should be attached.
            This should be specified only when creating both the specified SCSI
            controller as well as the hard disk at the same time.

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
        Enter the SCSI controller specification here. If the SCSI controller doesn\'t exist,
        a new SCSI controller will be created of the specified type. If the SCSI controller
        already exists, it will be reconfigured with the specifications. The following
        additional options can be specified per SCSI controller:

        type
            Enter the SCSI controller type you want to create. Currently supported
            types are ``lsilogic``, ``lsilogic_sas`` and ``paravirtual``. Type must
            be specified when creating a new SCSI controller.

        bus_sharing
            Specify this if sharing of virtual disks between virtual machines is desired.
            The following can be specified:

            virtual
                Virtual disks can be shared between virtual machines on the same server.

            physical
                Virtual disks can be shared between virtual machines on any server.

            no
                Virtual disks cannot be shared between virtual machines.

    ide
        Enter the IDE controller specification here. If the IDE controller doesn\'t exist,
        a new IDE controller will be created. If the IDE controller already exists,
        no further changes to it will me made.

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

``customization``
    Specify whether the new virtual machine should be customized or not. If
    ``customization: False`` is set, the new virtual machine will not be customized.
    Default is ``customization: True``.

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

``hardware_version``
    Specify the virtual hardware version for the vm/template that is supported by the
    host.

``image``
    Specify the guest id of the VM. For a full list of supported values see the
    VMware vSphere documentation:

    http://pubs.vmware.com/vsphere-60/topic/com.vmware.wssdk.apiref.doc/vim.vm.GuestOsDescriptor.GuestOsIdentifier.html

    .. note::

        For a clone operation, this argument is ignored.

``win_username``
    Specify windows vm administrator account.
        
    .. note::
    
    	Windows template should have "administrator" account.

``win_password``
    Specify windows vm administrator account password.
    
    .. note::

        During network configuration (if network specified), it is used to specify new administrator password for the machine. 

``win_organization_name``
    Specify windows vm user's organization. Default organization name is blank
   	VMware vSphere documentation:
	
    https://www.vmware.com/support/developer/vc-sdk/visdk25pubs/ReferenceGuide/vim.vm.customization.UserData.html

``win_user_fullname``
    Specify windows vm user's fullname. Default fullname is "Windows User"
   	VMware vSphere documentation:
	
    https://www.vmware.com/support/developer/vc-sdk/visdk25pubs/ReferenceGuide/vim.vm.customization.UserData.html

``plain_text``    	
	Flag to specify whether or not the password is in plain text, rather than encrypted.
	VMware vSphere documentation:

	https://www.vmware.com/support/developer/vc-sdk/visdk25pubs/ReferenceGuide/vim.vm.customization.Password.html

``win_installer``
    Specify windows minion client installer path

Cloning a VM
============

Cloning VMs/templates is the easiest and the preferred way to work with VMs using the VMware driver.

.. note::

    Cloning operations are unsupported on standalone ESXi hosts, a vCenter server will be required.

Example of a minimal profile:

.. code-block:: yaml

    my-minimal-clone:
      provider: vcenter01
      clonefrom: 'test-vm'

When cloning a VM, all the profile configuration parameters are optional and the configuration gets inherited from the clone.

Example to add/resize a disk:

.. code-block:: yaml

    my-disk-example:
      provider: vcenter01
      clonefrom: 'test-vm'

      devices:
        disk:
          Hard disk 1:
            size: 30

Depending on the configuration of the VM that is getting cloned, the disk in the resulting clone will differ.

.. note::

    - If the VM has no disk named 'Hard disk 1' an empty disk with the specified size will be added to the clone.

    - If the VM has a disk named 'Hard disk 1' and the size specified is larger than the original disk, an empty disk with the specified size will be added to the clone.

    - If the VM has a disk named 'Hard disk 1' and the size specified is smaller than the original disk, an empty disk with the original size will be added to the clone.

Example to reconfigure the memory and number of vCPUs:

.. code-block:: yaml

    my-disk-example:
      provider: vcenter01
      clonefrom: 'test-vm'

      memory: 16GB
      num_cpus: 8 


Cloning a Template
==================

Cloning a template works similar to cloning a VM except for the fact that a resource
pool or cluster must be specified additionally in the profile.

Example of a minimal profile:

.. code-block:: yaml

    my-template-clone:
     provider: vcenter01
     clonefrom: 'test-template'
     cluster: 'Prod'


Creating a VM
=============

.. versionadded:: 2016.3.0

Creating a VM from scratch means that more configuration has to be specified in the
profile because there is no place to inherit configuration from.

.. note::

    Unlike most cloud drivers that use prepared images, creating VMs using VMware
    cloud driver needs an installation method that requires no human interaction.
    For Example: preseeded ISO, kickstart URL or network PXE boot.

Example of a minimal profile:

.. code-block:: yaml

    my-minimal-profile:
      provider: esx01
      datastore: esx01-datastore
      resourcepool: Resources
      folder: vm

.. note::

    The example above contains the minimum required configuration needed to create
    a VM from scratch. The resulting VM will only have 1 VCPU, 32MB of RAM and will
    not have any storage or networking.

Example of a complete profile:

.. code-block:: yaml

    my-complete-example:
      provider: esx01
      datastore: esx01-datastore
      resourcepool: Resources
      folder: vm

      num_cpus: 2
      memory: 8GB

      image: debian7_64Guest

      devices:
        scsi:
          SCSI controller 0:
            type: lsilogic_sas
        ide:
          IDE 0
          IDE 1
        disk:
          Hard disk 0:
            controller: 'SCSI controller 0'
            size: 20
        cd:
          CD/DVD drive 0:
            controller: 'IDE 0'
            device_type: datastore_iso_file
            iso_path: '[esx01-datastore] debian-8-with-preseed.iso'
        network:
          Network adapter 0:
            name: 'VM Network'
            swith_type: standard

.. note::

    Depending on VMware ESX/ESXi version, an exact match for ``image`` might not
    be available. In such cases, the closest match to another ``image`` should
    be used. In the example above, a Debian 8 VM is created using the image
    ``debian7_64Guest`` which is for a Debian 7 guest.
