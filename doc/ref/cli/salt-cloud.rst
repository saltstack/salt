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

    Print a usage message briefly summarizing these command-line options

.. option:: -p PROFILE, --profile=PROFILE

    Select a single profile to build the named cloud vms from. The profile
    must be defined in the specified profiles file

.. option:: -m MAP, --map=MAP

    Specify a map file to use. This option will ensure that all of the mapped
    vms are created. If the named vm already exists then it will be skipped

.. option:: -P, --parallel

    Normally when building many cloud VMs they are executed serially. The -P
    option will run each cloud vm build in a separate process allowing for
    large groups of vms to be build at once.

    Be advised that some cloud provider's systems don't seem to be well suited
    for this influx of vm creation. When creating large groups of vms watch the
    cloud provider carefully.

.. option:: -Q, --query

    Execute a query and print out the information about all cloud vms

.. option:: -C CLOUD_CONFIG, --cloud-config=CLOUD_CONFIG

    Specify an alternative location for the salt cloud configuration file.
    Default location is /etc/salt/cloud

.. option:: -M MASTER_CONFIG, --master-config=MASTER_CONFIG

    Specify an alternative location for the salt master configuration file.
    The salt master configuration file is used to determine how to handle the
    minion RSA keys. Default location is /etc/salt/master

.. option:: -V VM_CONFIG, --profiles=VM_CONFIG, --vm_config=VM_CONFIG

    Specify an alternative location for the salt cloud profiles file.
    Default location is /etc/salt/cloud.profiles
    

See also
========

:manpage:`salt-cloud(7)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
