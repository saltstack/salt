================================
Miscellaneous Salt Cloud Options
================================

This page describes various miscellaneous options available in Salt Cloud

Deploy Script Arguments
=======================
Custom deploy scripts are unlikely to need custom arguments to be passed to
them, but salt-bootstrap has been extended quite a bit, and this may be
necessary. script_args can be specified in either the profile or the map
file, to pass arguments to the deploy script:

.. code-block:: yaml

    aws-amazon:
        provider: aws
        image: ami-1624987f
        size: Micro Instance
        ssh_username: ec2-user
        script: bootstrap-salt
        script_args: -c /tmp/

This has also been tested to work with pipes, if needed:

.. code-block:: yaml

    script_args: | head

Sync After Install
==================
Salt allows users to create custom modules, grains and states which can be 
synchronised to minions to extend Salt with further functionality.

This option will inform Salt Cloud to synchronise your custom modules, grains,
states or all these to the minion just after it has been created. For this to 
happen, the following line needs to be added to the main cloud 
configuration file:

.. code-block:: yaml

    sync_after_install: all

The available options for this setting are:

.. code-block:: yaml

    modules
    grains
    states
    all

Setting up New Salt Masters
===========================
It has become increasingly common for users to set up multi-hierarchal
infrastructures using Salt Cloud. This sometimes involves setting up an
instance to be a master in addition to a minion. With that in mind, you can
now law down master configuration on a machine by specifying master options
in the profile or map file.

.. code-block:: yaml

    make_master: True

This will cause Salt Cloud to generate master keys for the instance, and tell
salt-bootstrap to install the salt-master package, in addition to the
salt-minion package.

The default master configuration is usually appropriate for most users, and
will not be changed unless specific master configuration has been added to the
profile or map:

.. code-block:: yaml

    master:
        user: root
        interface: 0.0.0.0

Delete SSH Keys
===============
When Salt Cloud deploys an instance, the SSH pub key for the instance is added
to the known_hosts file for the user that ran the salt-cloud command. When an
instance is deployed, a cloud provider generally recycles the IP address for
the instance.  When Salt Cloud attempts to deploy an instance using a recycled
IP address that has previously been accessed from the same machine, the old key
in the known_hosts file will cause a conflict.

In order to mitigate this issue, Salt Cloud can be configured to remove old
keys from the known_hosts file when destroying the node. In order to do this,
the following line needs to be added to the main cloud configuration file:

.. code-block:: yaml

    delete_sshkeys: True

Keeping /tmp/ Files
===================
When Salt Cloud deploys an instance, it uploads temporary files to /tmp/ for
salt-bootstrap to put in place. After the script has run, they are deleted. To
keep these files around (mostly for debugging purposes), the --keep-tmp option
can be added:

.. code-block:: bash

    salt-cloud -p myprofile mymachine --keep-tmp

For those wondering why /tmp/ was used instead of /root/, this had to be done
for images which require the use of sudo, and therefore do not allow remote
root logins, even for file transfers (which makes /root/ unavailable).

Hide Output From Minion Install
===============================
By default Salt Cloud will stream the output from the minion deploy script 
directly to STDOUT. Although this can been very useful, in certain cases you 
may wish to switch this off. The following config option is there to enable or 
disable this output:

.. code-block:: yaml

    display_ssh_output: False
