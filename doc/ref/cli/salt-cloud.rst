==============
``salt-cloud``
==============

Copy a file to a set of systems

Synopsis
========

::

    salt-cloud -m /etc/salt/cloud.map

    salt-cloud -p PROFILE NAME

    salt-cloud -p PROFILE NAME1 NAME2 NAME3 NAME4 NAME5 NAME6

Description
===========

Salt Cloud is the system used to provision virtual machines on various public
clouds via a cleanly controlled profile and mapping system.

Options
=======

.. program:: salt-cloud

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -p PROFILE, --profile=PROFILE

    Select a single profile to build the named cloud vms from. The profile
    must be defined in the specified profiles file.

.. option:: -m MAP, --map=MAP

    Specify a map file to use. This option will ensure that all of the mapped
    vms are created. If the named vm already exists then it will be skipped.

.. option:: -H, --hard

    When specifying a map file, the default behavior is to ensure that all of
    the vms specified in the map file are created. If the --hard option is
    set, then any vms that exist on configured cloud providers that are
    not specified in the map file will be destroyed. Be advised that this can
    be a destructive operation and should be used with care.

.. option:: -d, --destroy

    Pass in the name(s) of vms to destroy, salt-cloud will search the
    configured cloud providers for the specified names and destroy the
    vms. Be advised that this is a destructive operation and should be used
    with care.

.. option:: -P, --parallel

    Normally when building many cloud VMs they are executed serially. The -P
    option will run each cloud vm build in a separate process allowing for
    large groups of vms to be build at once.

    Be advised that some cloud provider's systems don't seem to be well suited
    for this influx of vm creation. When creating large groups of vms watch the
    cloud provider carefully.

.. option:: -Q, --query

    Execute a query and print out the information about all cloud vms.

.. option:: --list-images

    Display a list of images available in configured cloud providers.
    Pass the cloud provider that available images are desired on, aka 
    "linode", or pass "all" to list images for all configured cloud providers.

.. option:: --list-sizes

    Display a list of sizes available in configured cloud providers. Pass the
    cloud provider that available sizes are desired on, aka "aws", or pass
    "all" to list sizes for all configured cloud providers

.. option:: -C CLOUD_CONFIG, --cloud-config=CLOUD_CONFIG

    Specify an alternative location for the salt cloud configuration file.
    Default location is /etc/salt/cloud.

.. option:: -M MASTER_CONFIG, --master-config=MASTER_CONFIG

    Specify an alternative location for the salt master configuration file.
    The salt master configuration file is used to determine how to handle the
    minion RSA keys. Default location is /etc/salt/master.

.. option:: -V VM_CONFIG, --profiles=VM_CONFIG, --vm_config=VM_CONFIG

    Specify an alternative location for the salt cloud profiles file.
    Default location is /etc/salt/cloud.profiles.

.. option:: --raw-out

    Print the output from the salt command in raw python
    form, this is suitable for re-reading the output into
    an executing python script with eval.

.. option:: --text-out

    Print the output from the salt command in the same form the shell would.

.. option:: --yaml-out

    Print the output from the salt command in yaml.

.. option:: --json-out

    Print the output from the salt command in json.

.. option:: --no-color

    Disable all colored output.

    
Examples
========

To create 4 vms named web1, web2, db1 and db2 from specified profiles:

# salt-cloud -p fedora_rackspace web1 web2 db1 db2

To read in a map file and create all vms specified therein:

# salt-cloud -m /path/to/cloud.map

To read in a map file and create all vms specified therein in parallel:

# salt-cloud -m /path/to/cloud.map -P

To delete any vms not specified in the maf file:

# salt-cloud -m /path/to/cloud.map -H -P

See also
========

:manpage:`salt-cloud(7)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
