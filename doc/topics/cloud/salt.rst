================================
Using the Salt Modules for Cloud
================================

In addition to the ``salt-cloud`` command, Salt Cloud can be called from Salt,
in a variety of different ways. Most users will be interested in either the
execution module or the state module, but it is also possible to call Salt Cloud
as a runner.

Because the actual work will be performed on a remote minion, the normal Salt
Cloud configuration must exist on any target minion that needs to execute a Salt
Cloud command.  Because Salt Cloud now supports breaking out configuration into
individual files, the configuration is easily managed using Salt's own
``file.managed`` state function. For example, the following directories allow
this configuration to be managed easily:

.. code-block:: yaml

    /etc/salt/cloud.providers.d/
    /etc/salt/cloud.profiles.d/


Minion Keys
-----------
Keep in mind that when creating minions, Salt Cloud will create public and
private minion keys, upload them to the minion, and place the public key on the
machine that created the minion. It will *not* attempt to place any public
minion keys on the master, unless the minion which was used to create the
instance is also the Salt Master. This is because granting arbitrary minions
access to modify keys on the master is a serious security risk, and must be
avoided.


Execution Module
----------------
The ``cloud`` module is available to use from the command line. At the moment,
almost every standard Salt Cloud feature is available to use. The following
commands are available:

list_images
~~~~~~~~~~~
This command is designed to show images that are available to be used to create
an instance using Salt Cloud. In general they are used in the creation of
profiles, but may also be used to create an instance directly (see below).
Listing images requires a provider to be configured, and specified:

.. code-block:: bash

    salt myminion cloud.list_images my-cloud-provider

list_sizes
~~~~~~~~~~
This command is designed to show sizes that are available to be used to create
an instance using Salt Cloud. In general they are used in the creation of
profiles, but may also be used to create an instance directly (see below). This
command is not available for all cloud providers; see the provider-specific
documentation for details. Listing sizes requires a provider to be configured,
and specified:

.. code-block:: bash

    salt myminion cloud.list_sizes my-cloud-provider

list_locations
~~~~~~~~~~~~~~
This command is designed to show locations that are available to be used to
create an instance using Salt Cloud. In general they are used in the creation of
profiles, but may also be used to create an instance directly (see below). This
command is not available for all cloud providers; see the provider-specific
documentation for details. Listing locations requires a provider to be
configured, and specified:

.. code-block:: bash

    salt myminion cloud.list_locations my-cloud-provider

query
~~~~~
This command is used to query all configured cloud providers, and display all
instances associated with those accounts. By default, it will run a standard
query, returning the following fields:

``id``
    The name or ID of the instance, as used by the cloud provider.

``image``
    The disk image that was used to create this instance.

``private_ips``
    Any public IP addresses currently assigned to this instance.

``public_ips``
    Any private IP addresses currently assigned to this instance.

``size``
    The size of the instance; can refer to RAM, CPU(s), disk space, etc.,
    depending on the cloud provider.

``state``
    The running state of the instance; for example, ``running``, ``stopped``,
    ``pending``, etc. This state is dependent upon the provider.

This command may also be used to perform a full query or a select query, as
described below. The following usages are available:

.. code-block:: bash

    salt myminion cloud.query
    salt myminion cloud.query list_nodes
    salt myminion cloud.query list_nodes_full

full_query
~~~~~~~~~~
This command behaves like the ``query`` command, but lists all information
concerning each instance as provided by the cloud provider, in addition to the
fields returned by the ``query`` command.

.. code-block:: bash

    salt myminion cloud.full_query

select_query
~~~~~~~~~~~~
This command behaves like the ``query`` command, but only returned select
fields as defined in the ``/etc/salt/cloud`` configuration file. A sample
configuration for this section of the file might look like:

.. code-block:: yaml

    query.selection:
      - id
      - key_name

This configuration would only return the ``id`` and ``key_name`` fields, for
those cloud providers that support those two fields. This would be called using
the following command:

.. code-block:: bash

    salt myminion cloud.select_query

profile
~~~~~~~
This command is used to create an instance using a profile that is configured
on the target minion. Please note that the profile must be configured before
this command can be used with it.

.. code-block:: bash

    salt myminion cloud.profile ec2-centos64-x64 my-new-instance

Please note that the execution module does *not* run in parallel mode. Using
multiple minions to create instances can effectively perform parallel instance
creation.

create
~~~~~~
This command is similar to the ``profile`` command, in that it is used to create
a new instance. However, it does not require a profile to be pre-configured.
Instead, all of the options that are normally configured in a profile are passed
directly to Salt Cloud to create the instance:

.. code-block:: bash

    salt myminion cloud.create my-ec2-config my-new-instance \
        image=ami-1624987f size='t1.micro' ssh_username=ec2-user \
        securitygroup=default delvol_on_destroy=True

Please note that the execution module does *not* run in parallel mode. Using
multiple minions to create instances can effectively perform parallel instance
creation.

destroy
~~~~~~~
This command is used to destroy an instance or instances. This command will
search all configured providers and remove any instance(s) which matches the
name(s) passed in here. The results of this command are *non-reversable* and
should be used with caution.

.. code-block:: bash

    salt myminion cloud.destroy myinstance
    salt myminion cloud.destroy myinstance1,myinstance2

action
~~~~~~
This command implements both the ``action`` and the ``function`` commands
used in the standard ``salt-cloud`` command. If one of the standard ``action``
commands is used, an instance name must be provided. If one of the standard
``function`` commands is used, a provider configuration must be named.

.. code-block:: bash

    salt myminion cloud.action start instance=myinstance
    salt myminion cloud.action show_image provider=my-ec2-config \
        image=ami-1624987f

The actions available are largely dependent upon the module for the specific
cloud provider. The following actions are available for all cloud providers:

``list_nodes``
    This is a direct call to the ``query`` function as described above, but is
    only performed against a single cloud provider. A provider configuration
    must be included.

``list_nodes_select``
    This is a direct call to the ``full_query`` function as described above, but
    is only performed against a single cloud provider. A provider configuration
    must be included.

``list_nodes_select``
    This is a direct call to the ``select_query`` function as described above,
    but is only performed against a single cloud provider.  A provider
    configuration must be included.

``show_instance``
    This is a thin wrapper around ``list_nodes``, which returns the full
    information about a single instance. An instance name must be provided.


State Module
------------
A subset of the execution module is available through the ``cloud`` state
module. Not all functions are currently included, because there is currently
insufficient code for them to perform statefully. For example, a command to
create an instance may be issued with a series of options, but those options
cannot currently be statefully managed. Additional states to manage these
options will be released at a later time.

cloud.present
~~~~~~~~~~~~~
This state will ensure that an instance is present inside a particular cloud
provider. Any option that is normally specified in the ``cloud.create``
execution module and function may be declared here, but only the actual
presence of the instance will be managed statefully.

.. code-block:: yaml

    my-instance-name:
      cloud.present:
        - cloud_provider: my-ec2-config
        - image: ami-1624987f
        - size: 't1.micro'
        - ssh_username: ec2-user
        - securitygroup: default
        - delvol_on_destroy: True

cloud.profile
~~~~~~~~~~~~~
This state will ensure that an instance is present inside a particular cloud
provider. This function calls the ``cloud.profile`` execution module and
function, but as with ``cloud.present``, only the actual presence of the
instance will be managed statefully.

.. code-block:: yaml

    my-instance-name:
      cloud.profile:
        - profile: ec2-centos64-x64

cloud.absent
~~~~~~~~~~~~
This state will ensure that an instance (identified by name) does not exist in
any of the cloud providers configured on the target minion. Please note that
this state is *non-reversable* and may be considered especially destructive when
issued as a cloud state.

.. code-block:: yaml

    my-instance-name:
      cloud.absent


Runner Module
-------------
The ``cloud`` runner module is executed on the master, and performs actions
using the configuration and Salt modules on the master itself. This means that
any public minion keys will also be properly accepted by the master.

Using the functions in the runner module is no different than using those in
the execution module, outside of the behavior described in the above paragraph.
The following functions are available inside the runner:

- list_images
- list_sizes
- list_locations
- query
- full_query
- select_query
- profile
- destroy
- action

Outside of the standard usage of ``salt-run`` itself, commands are executed as
usual:

.. code-block:: bash

    salt-run cloud.profile ec2-centos64-x86_64 my-instance-name


CloudClient
-----------
The execution, state, and runner modules ultimately all use the CloudClient
library that ships with Salt. To use the CloudClient library locally (either on
the master or a minion), create a client object and issue a command against it:

.. code-block:: python

    import salt.cloud
    import pprint

    client = salt.cloud.CloudClient("/etc/salt/cloud")
    nodes = client.query()
    pprint.pprint(nodes)

Reactor
-------
Examples of using the reactor with Salt Cloud are available in the
:formula_url:`ec2-autoscale-reactor <ec2-autoscale-reactor>` and
:formula_url:`salt-cloud-reactor <salt-cloud-reactor>` formulas.
