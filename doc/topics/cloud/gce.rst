.. _cloud-getting-started-gce:

==========================================
Getting Started With Google Compute Engine
==========================================

Google Compute Engine (GCE) is Google-infrastructure as a service that lets you
run your large-scale computing workloads on virtual machines.  This document
covers how to use Salt Cloud to provision and manage your virtual machines
hosted within Google's infrastructure.

You can find out more about GCE and other Google Cloud Platform services
at https://cloud.google.com.


Dependencies
============

* LibCloud >= 1.0.0

.. versionchanged:: 2017.7.0

* A Google Cloud Platform account with Compute Engine enabled
* A registered Service Account for authorization
* Oh, and obviously you'll need `salt <https://github.com/saltstack/salt>`_


.. _gce_setup:

Google Compute Engine Setup
===========================
#. Sign up for Google Cloud Platform

   Go to https://cloud.google.com and use your Google account to sign up for
   Google Cloud Platform and complete the guided instructions.

#. Create a Project

   Next, go to the console at https://cloud.google.com/console and create a
   new Project.  Make sure to select your new Project if you are not
   automatically directed to the Project.

   Projects are a way of grouping together related users, services, and
   billing.  You may opt to create multiple Projects and the remaining
   instructions will need to be completed for each Project if you wish to
   use GCE and Salt Cloud to manage your virtual machines.

#. Enable the Google Compute Engine service

   In your Project, either just click *Compute Engine* to the left, or go to
   the *APIs & auth* section and *APIs* link and enable the Google Compute
   Engine service.

#. Create a Service Account

   To set up authorization, navigate to *APIs & auth* section and then the
   *Credentials* link and click the *CREATE NEW CLIENT ID* button. Select
   *Service Account* and click the *Create Client ID* button. This will
   automatically download a ``.json`` file, which may or may not be used
   in later steps, depending on your version of ``libcloud``.

   Look for a new *Service Account* section in the page and record the generated
   email address for the matching key/fingerprint. The email address will be used
   in the ``service_account_email_address`` of the ``/etc/salt/cloud.providers``
   or the ``/etc/salt/cloud.providers.d/*.conf`` file.

#. Key Format

   .. note:: If you are using ``libcloud >= 0.17.0`` it is recommended that you use the ``JSON
       format`` file you downloaded above and skip to the `Provider Configuration`_ section
       below, using the JSON file **in place of 'NEW.pem'** in the documentation.

       If you are using an older version of libcloud or are unsure of the version you
       have, please follow the instructions below to generate and format a new P12 key.

   In the new *Service Account* section, click *Generate new P12 key*, which
   will automatically download a ``.p12`` private key file. The ``.p12``
   private key needs to be converted to a format compatible with libcloud.
   This new Google-generated private key was encrypted using *notasecret* as
   a passphrase. Use the following command and record the location of the
   converted private key and record the location for use in the
   ``service_account_private_key`` of the ``/etc/salt/cloud`` file:

   .. code-block:: bash

       openssl pkcs12 -in ORIG.p12 -passin pass:notasecret \
       -nodes -nocerts | openssl rsa -out NEW.pem



Provider Configuration
======================

Set up the provider cloud config at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``:

.. code-block:: yaml

    gce-config:
      # Set up the Project name and Service Account authorization
      project: "your-project-id"
      service_account_email_address: "123-a5gt@developer.gserviceaccount.com"
      service_account_private_key: "/path/to/your/NEW.pem"

      # Set up the location of the salt master
      minion:
        master: saltmaster.example.com

      # Set up grains information, which will be common for all nodes
      # using this provider
      grains:
        node_type: broker
        release: 1.0.1

      driver: gce

.. note::

    Empty strings as values for ``service_account_private_key`` and ``service_account_email_address``
    can be used on GCE instances. This will result in the service account assigned to the GCE instance
    being used.

.. note::

    The value provided for ``project`` must not contain underscores or spaces and
    is labeled as "Project ID" on the Google Developers Console.

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Profile Configuration
=====================
Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/*.conf``:

.. code-block:: yaml

    my-gce-profile:
      image: centos-6
      size: n1-standard-1
      location: europe-west1-b
      network: default
      subnetwork: default
      labels: '{"name": "myinstance"}'
      tags: '["one", "two", "three"]'
      metadata: '{"one": "1", "2": "two"}'
      use_persistent_disk: True
      delete_boot_pd: False
      deploy: True
      make_master: False
      provider: gce-config

The profile can be realized now with a salt command:

.. code-block:: bash

    salt-cloud -p my-gce-profile gce-instance

This will create an salt minion instance named ``gce-instance`` in GCE.  If
the command was executed on the salt-master, its Salt key will automatically
be signed on the master.

Once the instance has been created with a salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt gce-instance test.version


GCE Specific Settings
=====================
Consult the sample profile below for more information about GCE specific
settings. Some of them are mandatory and are properly labeled below but
typically also include a hard-coded default.

Initial Profile
---------------
Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/gce.conf``:

.. code-block:: yaml

    my-gce-profile:
      image: centos-6
      size: n1-standard-1
      location: europe-west1-b
      network: default
      subnetwork: default
      labels: '{"name": "myinstance"}'
      tags: '["one", "two", "three"]'
      metadata: '{"one": "1", "2": "two"}'
      use_persistent_disk: True
      delete_boot_pd: False
      ssh_interface: public_ips
      external_ip: "ephemeral"

image
-----

Image is used to define what Operating System image should be used
to for the instance. Examples are Debian 7 (wheezy) and CentOS 6. Required.

size
----

A 'size', in GCE terms, refers to the instance's 'machine type'. See
the on-line documentation for a complete list of GCE machine types. Required.

location
--------

A 'location', in GCE terms, refers to the instance's 'zone'. GCE
has the notion of both Regions (e.g. us-central1, europe-west1, etc)
and Zones (e.g. us-central1-a, us-central1-b, etc). Required.

network
-------

Use this setting to define the network resource for the instance.
All GCE projects contain a network named 'default' but it's possible
to use this setting to create instances belonging to a different
network resource.

subnetwork
----------

Use this setting to define the subnetwork an instance will be created in.
This requires that the network your instance is created under has a mode of 'custom' or 'auto'.
Additionally, the subnetwork your instance is created under is associated with the location you provide.

.. versionadded:: 2017.7.0

labels
------

This setting allows you to set labels on your GCE instances. It
should be a dictionary and must be parse-able by the python
ast.literal_eval() function to convert it to a python dictionary.

.. versionadded:: 3006

tags
----

GCE supports instance/network tags and this setting allows you to
set custom tags. It should be a list of strings and must be
parse-able by the python ast.literal_eval() function to convert it
to a python list.

metadata
--------

GCE supports instance metadata and this setting allows you to
set custom metadata. It should be a hash of key/value strings and
parse-able by the python ast.literal_eval() function to convert it
to a python dictionary.

use_persistent_disk
-------------------

Use this setting to ensure that when new instances are created,
they will use a persistent disk to preserve data between instance
terminations and re-creations.

delete_boot_pd
--------------

In the event that you wish the boot persistent disk to be permanently
deleted when you destroy an instance, set delete_boot_pd to True.

ssh_interface
-------------

.. versionadded:: 2015.5.0

Specify whether to use public or private IP for deploy script.

Valid options are:

- private_ips: The salt-master is also hosted with GCE
- public_ips: The salt-master is hosted outside of GCE

external_ip
-----------

Per instance setting: Used a named fixed IP address to this host.

Valid options are:

- ephemeral: The host will use a GCE ephemeral IP
- None: No external IP will be configured on this host.

Optionally, pass the name of a GCE address to use a fixed IP address.
If the address does not already exist, it will be created.

ex_disk_type
------------

GCE supports two different disk types, ``pd-standard`` and ``pd-ssd``.
The default disk type setting is ``pd-standard``. To specify using an SSD
disk, set ``pd-ssd`` as the value.

.. versionadded:: 2014.7.0

ip_forwarding
-------------

GCE instances can be enabled to use IP Forwarding. When set to ``True``,
this options allows the instance to send/receive non-matching src/dst
packets. Default is ``False``.

.. versionadded:: 2015.8.1

Profile with scopes
-------------------

Scopes can be specified by setting the optional ``ex_service_accounts``
key in your cloud profile. The following example enables the bigquery scope.

.. code-block:: yaml

  my-gce-profile:
   image: centos-6
    ssh_username: salt
    size: f1-micro
    location: us-central1-a
    network: default
    subnetwork: default
    labels: '{"name": "myinstance"}'
    tags: '["one", "two", "three"]'
    metadata: '{"one": "1", "2": "two",
                "sshKeys": ""}'
    use_persistent_disk: True
    delete_boot_pd: False
    deploy: False
    make_master: False
    provider: gce-config
    ex_service_accounts:
      - scopes:
        - bigquery


Email can also be specified as an (optional) parameter.

.. code-block:: yaml

  my-gce-profile:
  ...snip
    ex_service_accounts:
      - scopes:
        - bigquery
        email: default

There can be multiple entries for scopes since ``ex-service_accounts`` accepts
a list of dictionaries. For more information refer to the libcloud documentation
on `specifying service account scopes`__.

SSH Remote Access
=================

GCE instances do not allow remote access to the root user by default.
Instead, another user must be used to run the deploy script using sudo.
Append something like this to ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/*.conf``:

.. code-block:: yaml

  my-gce-profile:
      ...

      # SSH to GCE instances as gceuser
      ssh_username: gceuser

      # Use the local private SSH key file located here
      ssh_keyfile: /etc/cloud/google_compute_engine

If you have not already used this SSH key to login to instances in this
GCE project you will also need to add the public key to your projects
metadata at https://cloud.google.com/console. You could also add it via
the metadata setting too:

.. code-block:: yaml

  my-gce-profile:
      ...

      metadata: '{"one": "1", "2": "two",
                  "sshKeys": "gceuser:ssh-rsa <Your SSH Public Key> gceuser@host"}'


Single instance details
=======================
This action is a thin wrapper around ``--full-query``, which displays details on a
single instance only. In an environment with several machines, this will save a
user from having to sort through all instance data, just to examine a single
instance.

.. code-block:: bash

    salt-cloud -a show_instance myinstance


Destroy, persistent disks, and metadata
=======================================
As noted in the provider configuration, it's possible to force the boot
persistent disk to be deleted when you destroy the instance.  The way that
this has been implemented is to use the instance metadata to record the
cloud profile used when creating the instance.  When ``destroy`` is called,
if the instance contains a ``salt-cloud-profile`` key, it's value is used
to reference the matching profile to determine if ``delete_boot_pd`` is
set to ``True``.

Be aware that any GCE instances created with salt cloud will contain this
custom ``salt-cloud-profile`` metadata entry.


List various resources
======================
It's also possible to list several GCE resources similar to what can be done
with other providers.  The following commands can be used to list GCE zones
(locations), machine types (sizes), and images.

.. code-block:: bash

    salt-cloud --list-locations gce
    salt-cloud --list-sizes gce
    salt-cloud --list-images gce


Persistent Disk
===============
The Compute Engine provider provides functions via salt-cloud to manage your
Persistent Disks. You can create and destroy disks as well as attach and
detach them from running instances.

Create
------
When creating a disk, you can create an empty disk and specify its size (in
GB), or specify either an 'image' or 'snapshot'.

.. code-block:: bash

    salt-cloud -f create_disk gce disk_name=pd location=us-central1-b size=200

Delete
------
Deleting a disk only requires the name of the disk to delete

.. code-block:: bash

    salt-cloud -f delete_disk gce disk_name=old-backup

Attach
------
Attaching a disk to an existing instance is really an 'action' and requires
both an instance name and disk name. It's possible to use this ation to
create bootable persistent disks if necessary. Compute Engine also supports
attaching a persistent disk in READ_ONLY mode to multiple instances at the
same time (but then cannot be attached in READ_WRITE to any instance).

.. code-block:: bash

    salt-cloud -a attach_disk myinstance disk_name=pd mode=READ_WRITE boot=yes

Detach
------
Detaching a disk is also an action against an instance and only requires
the name of the disk. Note that this does *not* safely sync and umount the
disk from the instance. To ensure no data loss, you must first make sure the
disk is unmounted from the instance.

.. code-block:: bash

    salt-cloud -a detach_disk myinstance disk_name=pd

Show disk
---------
It's also possible to look up the details for an existing disk with either
a function or an action.

.. code-block:: bash

    salt-cloud -a show_disk myinstance disk_name=pd
    salt-cloud -f show_disk gce disk_name=pd

Create snapshot
---------------
You can take a snapshot of an existing disk's content. The snapshot can then
in turn be used to create other persistent disks. Note that to prevent data
corruption, it is strongly suggested that you unmount the disk prior to
taking a snapshot. You must name the snapshot and provide the name of the
disk.

.. code-block:: bash

    salt-cloud -f create_snapshot gce name=backup-20140226 disk_name=pd

Delete snapshot
---------------
You can delete a snapshot when it's no longer needed by specifying the name
of the snapshot.

.. code-block:: bash

    salt-cloud -f delete_snapshot gce name=backup-20140226

Show snapshot
-------------
Use this function to look up information about the snapshot.

.. code-block:: bash

    salt-cloud -f show_snapshot gce name=backup-20140226

Networking
==========
Compute Engine supports multiple private networks per project. Instances
within a private network can easily communicate with each other by an
internal DNS service that resolves instance names. Instances within a private
network can also communicate with either directly without needing special
routing or firewall rules even if they span different regions/zones.

Networks also support custom firewall rules. By default, traffic between
instances on the same private network is open to all ports and protocols.
Inbound SSH traffic (port 22) is also allowed but all other inbound traffic
is blocked.

Create network
--------------
New networks require a name and CIDR range if they don't have a 'mode'.
Optionally, 'mode' can be provided. Supported modes are 'auto', 'custom', 'legacy'.
Optionally, 'description' can be provided to add an extra note to your network.
New instances can be created and added to this network by setting the network name during create. It is
not possible to add/remove existing instances to a network.

.. code-block:: bash

    salt-cloud -f create_network gce name=mynet cidr=10.10.10.0/24
    salt-cloud -f create_network gce name=mynet mode=auto description=some optional info.

.. versionchanged:: 2017.7.0

Destroy network
---------------
Destroy a network by specifying the name. If a resource is currently using
the target network an exception will be raised.

.. code-block:: bash

    salt-cloud -f delete_network gce name=mynet

Show network
------------
Specify the network name to view information about the network.

.. code-block:: bash

    salt-cloud -f show_network gce name=mynet

Create subnetwork
-----------------

New subnetworks require a name, region, and CIDR range.
Optionally, 'description' can be provided to add an extra note to your subnetwork.
New instances can be created and added to this subnetwork by setting the subnetwork name during create. It is
not possible to add/remove existing instances to a subnetwork.

.. code-block:: bash

    salt-cloud -f create_subnetwork gce name=mynet network=mynet region=us-central1 cidr=10.0.10.0/24
    salt-cloud -f create_subnetwork gce name=mynet network=mynet region=us-central1 cidr=10.10.10.0/24 description=some info about my subnet.

.. versionadded:: 2017.7.0

Destroy subnetwork
------------------

Destroy a subnetwork by specifying the name and region. If a resource is currently using
the target subnetwork an exception will be raised.

.. code-block:: bash

    salt-cloud -f delete_subnetwork gce name=mynet region=us-central1

.. versionadded:: 2017.7.0

Show subnetwork
---------------

Specify the subnetwork name to view information about the subnetwork.

.. code-block:: bash

    salt-cloud -f show_subnetwork gce name=mynet

.. versionadded:: 2017.7.0

Create address
--------------
Create a new named static IP address in a region.

.. code-block:: bash

    salt-cloud -f create_address gce name=my-fixed-ip region=us-central1

Delete address
--------------
Delete an existing named fixed IP address.

.. code-block:: bash

    salt-cloud -f delete_address gce name=my-fixed-ip region=us-central1

Show address
------------
View details on a named address.

.. code-block:: bash

    salt-cloud -f show_address gce name=my-fixed-ip region=us-central1

Create firewall
---------------
You'll need to create custom firewall rules if you want to allow other traffic
than what is described above. For instance, if you run a web service on
your instances, you'll need to explicitly allow HTTP and/or SSL traffic.
The firewall rule must have a name and it will use the 'default' network
unless otherwise specified with a 'network' attribute. Firewalls also support
instance tags for source/destination

.. code-block:: bash

    salt-cloud -f create_fwrule gce name=web allow=tcp:80,tcp:443,icmp

Delete firewall
---------------
Deleting a firewall rule will prevent any previously allowed traffic for the
named firewall rule.

.. code-block:: bash

    salt-cloud -f delete_fwrule gce name=web

Show firewall
-------------
Use this function to review an existing firewall rule's information.

.. code-block:: bash

    salt-cloud -f show_fwrule gce name=web

Load Balancer
=============
Compute Engine possess a load-balancer feature for splitting traffic across
multiple instances. Please reference the
`documentation <https://cloud.google.com/load-balancing/docs>`_
for a more complete description.

The load-balancer functionality is slightly different than that described
in Google's documentation.  The concept of *TargetPool* and *ForwardingRule*
are consolidated in salt-cloud/libcloud.  HTTP Health Checks are optional.

HTTP Health Check
-----------------
HTTP Health Checks can be used as a means to toggle load-balancing across
instance members, or to detect if an HTTP site is functioning.  A common
use-case is to set up a health check URL and if you want to toggle traffic
on/off to an instance, you can temporarily have it return a non-200 response.
A non-200 response to the load-balancer's health check will keep the LB from
sending any new traffic to the "down" instance.  Once the instance's
health check URL beings returning 200-responses, the LB will again start to
send traffic to it. Review Compute Engine's documentation for allowable
parameters.  You can use the following salt-cloud functions to manage your
HTTP health checks.

.. code-block:: bash

    salt-cloud -f create_hc gce name=myhc path=/ port=80
    salt-cloud -f delete_hc gce name=myhc
    salt-cloud -f show_hc gce name=myhc


Load-balancer
-------------
When creating a new load-balancer, it requires a name, region, port range,
and list of members. There are other optional parameters for protocol,
and list of health checks. Deleting or showing details about the LB only
requires the name.

.. code-block:: bash

    salt-cloud -f create_lb gce name=lb region=... ports=80 members=w1,w2,w3
    salt-cloud -f delete_lb gce name=lb
    salt-cloud -f show_lb gce name=lb

You can also create a load balancer using a named fixed IP addressby specifying the name of the address.
If the address does not exist yet it will be created.

.. code-block:: bash

    salt-cloud -f create_lb gce name=my-lb region=us-central1 ports=234 members=s1,s2,s3 address=my-lb-ip

Attach and Detach LB
--------------------
It is possible to attach or detach an instance from an existing load-balancer.
Both the instance and load-balancer must exist before using these functions.

.. code-block:: bash

    salt-cloud -f attach_lb gce name=lb member=w4
    salt-cloud -f detach_lb gce name=lb member=oops

__ https://libcloud.readthedocs.io/en/latest/compute/drivers/gce.html#specifying-service-account-scopes
