==============
``salt-cloud``
==============

Provision virtual machines in the cloud with Salt

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

    Select a single profile to build the named cloud VMs from. The profile
    must be defined in the specified profiles file.

.. option:: -m MAP, --map=MAP

    Specify a map file to use. If used without any other options, this option
    will ensure that all of the mapped VMs are created. If the named VM
    already exists then it will be skipped.

.. option:: -H, --hard

    When specifying a map file, the default behavior is to ensure that all of
    the VMs specified in the map file are created. If the --hard option is
    set, then any VMs that exist on configured cloud providers that are
    not specified in the map file will be destroyed. Be advised that this can
    be a destructive operation and should be used with care.

.. option:: -d, --destroy

    Pass in the name(s) of VMs to destroy, salt-cloud will search the
    configured cloud providers for the specified names and destroy the
    VMs. Be advised that this is a destructive operation and should be used
    with care. Can be used in conjunction with the -m option to specify a map
    of VMs to be deleted.

.. option:: -P, --parallel

    Normally when building many cloud VMs they are executed serially. The -P
    option will run each cloud vm build in a separate process allowing for
    large groups of VMs to be build at once.

    Be advised that some cloud provider's systems don't seem to be well suited
    for this influx of vm creation. When creating large groups of VMs watch the
    cloud provider carefully.

.. option:: -Q, --query

    Execute a query and print out information about all cloud VMs. Can be used
    in conjunction with -m to display only information about the specified map.

.. option:: -F, --full-query

    Execute a query and print out all available information about all cloud VMs.
    Can be used in conjunction with -m to display only information about the
    specified map.

.. option:: -S, --select-query

    Execute a query and print out selected information about all cloud VMs.
    Can be used in conjunction with -m to display only information about the
    specified map.

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

To create 4 VMs named web1, web2, db1 and db2 from specified profiles:

# salt-cloud -p fedora_rackspace web1 web2 db1 db2

To read in a map file and create all VMs specified therein:

# salt-cloud -m /path/to/cloud.map

To read in a map file and create all VMs specified therein in parallel:

# salt-cloud -m /path/to/cloud.map -P

To delete any VMs specified in the map file:

# salt-cloud -m /path/to/cloud.map -d

To delete any VMs NOT specified in the map file:

# salt-cloud -m /path/to/cloud.map -H

To display the status of all VMs specified in the map file:

# salt-cloud -m /path/to/cloud.map -Q

See also
========

:manpage:`salt-cloud(7)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
