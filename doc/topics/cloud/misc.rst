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

    ec2-amazon:
      provider: my-ec2-config
      image: ami-1624987f
      size: t1.micro
      ssh_username: ec2-user
      script: bootstrap-salt
      script_args: -c /tmp/

This has also been tested to work with pipes, if needed:

.. code-block:: yaml

    script_args: | head


Selecting the File Transport
============================
By default, Salt Cloud uses SFTP to transfer files to Linux hosts. However, if
SFTP is not available, or specific SCP functionality is needed, Salt Cloud can
be configured to use SCP instead.

.. code-block:: yaml

    file_transport: sftp
    file_transport: scp


Sync After Install
==================
Salt allows users to create custom modules, grains, and states which can be
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


Setting Up New Salt Masters
===========================
It has become increasingly common for users to set up multi-hierarchal
infrastructures using Salt Cloud. This sometimes involves setting up an
instance to be a master in addition to a minion. With that in mind, you can
now lay down master configuration on a machine by specifying master options
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


Setting Up a Salt Syndic with Salt Cloud
========================================

In addition to `setting up new Salt Masters`_, :ref:`syndic`s can also be
provisioned using Salt Cloud. In order to set up a Salt Syndic via Salt Cloud,
a Salt Master needs to be installed on the new machine and a master configuration
file needs to be set up using the ``make_master`` setting. This setting can be
defined either in a profile config file or in a map file:

.. code-block:: yaml

    make_master: True

To install the Salt Syndic, the only other specification that needs to be
configured is the ``syndic_master`` key to specify the location of the master
that the syndic will be reporting to. This modification needs to be placed
in the ``master`` setting, which can be configured either in the profile,
provider, or ``/etc/salt/cloud`` config file:

.. code-block:: yaml

    master:
      syndic_master: 123.456.789  # may be either an IP address or a hostname

Many other Salt Syndic configuration settings and specifications can be passed
through to the new syndic machine via the ``master`` configuration setting.
See the :ref:`syndic` documentation for more information.


SSH Port
========

By default ssh port is set to port 22. If you want to use a custom port in
provider, profile, or map blocks use ssh_port option.

.. versionadded:: 2015.5.0

.. code-block:: yaml

    ssh_port: 2222


SSH Port
========

By default ssh port is set to port 22. If you want to use a custom port in
provider, profile, or map blocks use ssh_port option.

.. code-block:: yaml

    ssh_port: 2222


Delete SSH Keys
===============
When Salt Cloud deploys an instance, the SSH pub key for the instance is added
to the known_hosts file for the user that ran the salt-cloud command. When an
instance is deployed, a cloud host generally recycles the IP address for
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

    All settings should be provided in lowercase
    All values should be provided in seconds


You can tweak these settings globally, per cloud provider, or event per profile
definition.


wait_for_ip_timeout
~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should wait for a VM to start and get an IP back
from the cloud host.
Default: varies by cloud provider ( between 5 and 25 minutes)


wait_for_ip_interval
~~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should sleep while querying for the VM's IP.
Default: varies by cloud provider ( between .5 and 10 seconds)


ssh_connect_timeout
~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should wait for a successful SSH connection to
the VM.
Default: varies by cloud provider  (between 5 and 15 minutes)


wait_for_passwd_timeout
~~~~~~~~~~~~~~~~~~~~~~~

The amount of time until an ssh connection can be established via password or
ssh key.
Default: varies by cloud provider (mostly 15 seconds)


wait_for_passwd_maxtries
~~~~~~~~~~~~~~~~~~~~~~~~

The number of attempts to connect to the VM until we abandon.
Default: 15 attempts


wait_for_fun_timeout
~~~~~~~~~~~~~~~~~~~~

Some cloud drivers check for an available IP or a successful SSH connection
using a function, namely, SoftLayer, and SoftLayer-HW. So, the amount of time
Salt Cloud should retry such functions before failing.
Default: 15 minutes.


wait_for_spot_timeout
~~~~~~~~~~~~~~~~~~~~~

The amount of time Salt Cloud should wait before an EC2 Spot instance is
available. This setting is only available for the EC2 cloud driver.
Default: 10  minutes


Salt Cloud Cache
================

Salt Cloud can maintain a cache of node data, for supported providers. The
following options manage this functionality.


update_cachedir
~~~~~~~~~~~~~~~

On supported cloud providers, whether or not to maintain a cache of nodes
returned from a --full-query. The data will be stored in ``msgpack`` format
under ``<SALT_CACHEDIR>/cloud/active/<DRIVER>/<PROVIDER>/<NODE_NAME>.p``. This
setting can be True or False.


diff_cache_events
~~~~~~~~~~~~~~~~~

When the cloud cachedir is being managed, if differences are encountered
between the data that is returned live from the cloud host and the data in
the cache, fire events which describe the changes. This setting can be True or
False.

Some of these events will contain data which describe a node. Because some of
the fields returned may contain sensitive data, the ``cache_event_strip_fields``
configuration option exists to strip those fields from the event return.

.. code-block:: yaml

    cache_event_strip_fields:
      - password
      - priv_key

The following are events that can be fired based on this data.


salt/cloud/minionid/cache_node_new
**********************************
A new node was found on the cloud host which was not listed in the cloud
cachedir. A dict describing the new node will be contained in the event.


salt/cloud/minionid/cache_node_missing
**************************************
A node that was previously listed in the cloud cachedir is no longer available
on the cloud host.


salt/cloud/minionid/cache_node_diff
***********************************
One or more pieces of data in the cloud cachedir has changed on the cloud
host. A dict containing both the old and the new data will be contained in
the event.


SSH Known Hosts
===============

Normally when bootstrapping a VM, salt-cloud will ignore the SSH host key. This
is because it does not know what the host key is before starting (because it
doesn't exist yet). If strict host key checking is turned on without the key
in the ``known_hosts`` file, then the host will never be available, and cannot
be bootstrapped.

If a provider is able to determine the host key before trying to bootstrap it,
that provider's driver can add it to the ``known_hosts`` file, and then turn on
strict host key checking. This can be set up in the main cloud configuration
file (normally ``/etc/salt/cloud``) or in the provider-specific configuration
file:

.. code-block:: yaml

    known_hosts_file: /path/to/.ssh/known_hosts

If this is not set, it will default to ``/dev/null``, and strict host key
checking will be turned off.

It is highly recommended that this option is *not* set, unless the user has
verified that the provider supports this functionality, and that the image
being used is capable of providing the necessary information. At this time,
only the EC2 driver supports this functionality.

SSH Agent
=========

.. versionadded:: 2015.5.0

If the ssh key is not stored on the server salt-cloud is being run on, set
ssh_agent, and salt-cloud will use the forwarded ssh-agent to authenticate.

.. code-block:: yaml

    ssh_agent: True

File Map Upload
===============

.. versionadded:: 2014.7.0

The ``file_map`` option allows an arbitrary group of files to be uploaded to the
target system before running the deploy script. This functionality requires a
provider uses salt.utils.cloud.bootstrap(), which is currently limited to the ec2,
gce, openstack and nova drivers.

The ``file_map`` can be configured globally in ``/etc/salt/cloud``, or in any cloud
provider or profile file. For example, to upload an extra package or a custom deploy
script, a cloud profile using ``file_map`` might look like:

.. code-block:: yaml

    ubuntu14:
      provider: ec2-config
      image: ami-98aa1cf0
      size: t1.micro
      ssh_username: root
      securitygroup: default
      file_map:
        /local/path/to/custom/script: /remote/path/to/use/custom/script
        /local/path/to/package: /remote/path/to/store/package
