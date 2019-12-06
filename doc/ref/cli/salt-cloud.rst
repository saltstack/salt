==============
``salt-cloud``
==============

Provision virtual machines in the cloud with Salt

Synopsis
========

.. code-block:: bash

    salt-cloud -m /etc/salt/cloud.map

    salt-cloud -m /etc/salt/cloud.map NAME

    salt-cloud -m /etc/salt/cloud.map NAME1 NAME2

    salt-cloud -p PROFILE NAME

    salt-cloud -p PROFILE NAME1 NAME2 NAME3 NAME4 NAME5 NAME6

Description
===========

Salt Cloud is the system used to provision virtual machines on various public
clouds via a cleanly controlled profile and mapping system.

Options
=======

.. program:: salt-cloud

.. include:: _includes/common-options.rst

Execution Options
-----------------

.. option:: -L LOCATION, --location=LOCATION

    Specify which region to connect to.

.. option:: -a ACTION, --action=ACTION

    Perform an action that may be specific to this cloud provider. This
    argument requires one or more instance names to be specified.

.. option:: -f <FUNC-NAME> <PROVIDER>, --function=<FUNC-NAME> <PROVIDER>

    Perform an function that may be specific to this cloud provider, that does
    not apply to an instance. This argument requires a provider to be specified
    (i.e.: nova).

.. option:: -p PROFILE, --profile=PROFILE

    Select a single profile to build the named cloud VMs from. The profile must
    be defined in the specified profiles file.

.. option:: -m MAP, --map=MAP

    Specify a map file to use. If used without any other options, this option
    will ensure that all of the mapped VMs are created. If the named VM already
    exists then it will be skipped.

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

.. option:: -u, --update-bootstrap

    Update salt-bootstrap to the latest stable bootstrap release.

.. option:: -y, --assume-yes

    Default yes in answer to all confirmation questions.

.. option:: -k, --keep-tmp

    Do not remove files from /tmp/ after deploy.sh finishes.

.. option:: --show-deploy-args

    Include the options used to deploy the minion in the data returned.

.. option:: --script-args=SCRIPT_ARGS

    Script arguments to be fed to the bootstrap script when deploying the VM.

Query Options
-------------

.. option:: -Q, --query

    Execute a query and return some information about the nodes running on
    configured cloud providers

.. option:: -F, --full-query

    Execute a query and print out all available information about all cloud VMs.
    Can be used in conjunction with -m to display only information about the
    specified map.

.. option:: -S, --select-query

    Execute a query and print out selected information about all cloud VMs.
    Can be used in conjunction with -m to display only information about the
    specified map.

.. option:: --list-providers

    Display a list of configured providers.

.. option:: --list-profiles

    .. versionadded:: 2014.7.0

    Display a list of configured profiles. Pass in a cloud provider to view
    the provider's associated profiles, such as ``digitalocean``, or pass in
    ``all`` to list all the configured profiles.


Cloud Providers Listings
------------------------

.. option:: --list-locations=LIST_LOCATIONS

    Display a list of locations available in configured cloud providers. Pass
    the cloud provider that available locations are desired on, such as "linode",
    or pass "all" to list locations for all configured cloud providers

.. option:: --list-images=LIST_IMAGES

    Display a list of images available in configured cloud providers. Pass the
    cloud provider that available images are desired on, such as "linode", or pass
    "all" to list images for all configured cloud providers

.. option:: --list-sizes=LIST_SIZES

    Display a list of sizes available in configured cloud providers. Pass the
    cloud provider that available sizes are desired on, such as "AWS", or pass
    "all" to list sizes for all configured cloud providers

Cloud Credentials
-----------------

.. option::     --set-password=<USERNAME> <PROVIDER>

    Configure password for a cloud provider and save it to the keyring.
    PROVIDER can be specified with or without a driver, for example:
    "--set-password bob rackspace" or more specific "--set-password bob
    rackspace:openstack" DEPRECATED!

.. include:: _includes/output-options.rst


Examples
========

To create 4 VMs named web1, web2, db1, and db2 from specified profiles:

.. code-block:: bash

    salt-cloud -p fedora_rackspace web1 web2 db1 db2

To read in a map file and create all VMs specified therein:

.. code-block:: bash

    salt-cloud -m /path/to/cloud.map

To read in a map file and create all VMs specified therein in parallel:

.. code-block:: bash

    salt-cloud -m /path/to/cloud.map -P

To delete any VMs specified in the map file:

.. code-block:: bash

    salt-cloud -m /path/to/cloud.map -d

To delete any VMs NOT specified in the map file:

.. code-block:: bash

    salt-cloud -m /path/to/cloud.map -H

To display the status of all VMs specified in the map file:

.. code-block:: bash

    salt-cloud -m /path/to/cloud.map -Q

See also
========

:manpage:`salt-cloud(7)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
