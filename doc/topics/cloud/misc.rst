================================
Miscellaneous Salt Cloud Options
================================

This page describes various miscellaneous options available in Salt Cloud

Deploy Script Arguments
=======================
Custom deploy scripts are unlikely to need custom arguments to be passed to
them, but salt-bootstrap has been extended quite a bit, and this may be
necessary. script_args can be specified in either the profile or the map file,
to pass arguments to the deploy script:

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


Connection Timeout
==================

There are several stages when deploying Salt where Salt Cloud needs to wait for 
something to happen. The VM getting it's IP address, the VM's SSH port is 
available, etc.

If you find that the Salt Cloud defaults are not enough and your deployment 
fails because Salt Cloud did not wait log enough, there are some settings you 
can tweak.

.. admonition:: Note

    All values should be provided in seconds


You can tweak these settings globally, per cloud provider, or event per profile 
definition.


wait_for_ip_timeout
~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should wait for a VM to start and get an IP back 
from the cloud provider. Default: 5 minutes.


wait_for_ip_interval
~~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should sleep while querying for the VM's IP.  
Default: 5 seconds.


ssh_connect_timeout
~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should wait for a successful SSH connection to 
the VM. Default: 5 minutes.


wait_for_passwd_timeout
~~~~~~~~~~~~~~~~~~~~~~~

The amount of time until an ssh connection can be established via password or 
ssh key. Default 15 seconds.


wait_for_fun_timeout
~~~~~~~~~~~~~~~~~~~~

Some cloud drivers check for an available IP or a successful SSH connection 
using a function, namely, SoftLayer and SoftLayer-HW. So, the amount of time 
Salt Cloud should retry such functions before failing. Default: 5 minutes.


wait_for_spot_timeout
~~~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should wait before an EC2 Spot instance is 
available. This setting is only available for the EC2 cloud driver.
