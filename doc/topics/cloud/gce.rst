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
* Libcloud >= 0.14.0-beta3
* PyCrypto >= 2.1.
* A Google Cloud Platform account with Compute Engine enabled
* A registered Service Account for authorization
* Oh, and obviously you'll need `salt <https://github.com/saltstack/salt>`_


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
   prompt you to save a private key file.  Look for a new *Service Account*
   section in the page and record the generated email address for the
   matching key/fingerprint.  The email address will be used in the
   ``service_account_email_address`` of your ``/etc/salt/cloud``
   file.

#. Key Format

   You will need to convert the private key to a format compatible with
   libcloud.  The original Google-generated private key was encrypted using
   *notasecret* as a passphrase.  Use the following command and record the
   location of the converted private key and record the location for use
   in the ``service_account_private_key`` of your ``/etc/salt/cloud`` file::

     openssl pkcs12 -in ORIG.pkey -passin pass:notasecret \
     -nodes -nocerts | openssl rsa -out NEW.pem



Configuration
=============

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud

    providers:
      gce-config:
        # Set up the Project name and Service Account authorization
        #
        project: "your_project_name"
        service_account_email_address: "123-a5gt@developer.gserviceaccount.com"
        service_account_private_key: "/path/to/your/NEW.pem"

        # Set up the location of the salt master
        #
        minion:
          master: saltmaster.example.com

        # Set up grains information, which will be common for all nodes
        # using this provider
        grains:
          node_type: broker
          release: 1.0.1

        provider: gce



Cloud Profiles
==============
Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    all_settings:
      image: centos-6
      size: n1-standard-1
      location: europe-west1-b
      network: default
      tags: '["one", "two", "three"]'
      metadata: '{"one": "1", "2": "two"}'
      use_persistent_disk: True
      delete_boot_pd: False
      deploy: True
      make_master: False
      provider: gce-config

The profile can be realized now with a salt command:

.. code-block:: bash

    salt-cloud -p all_settings gce-instance

This will create an salt minion instance named ``gce-instance`` in GCE.  If
the command was executed on the salt-master, its Salt key will automatically
be signed on the master.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt 'ami.example.com' test.ping


GCE Specific Settings
=====================
Consult the sample profile below for more information about GCE specific
settings.  Some of them are mandatory and are properly labeled below but
typically also include a hard-coded default.

.. code-block:: yaml

    all_settings:

      # Image is used to define what Operating System image should be used
      # to for the instance.  Examples are Debian 7 (wheezy) and CentOS 6.
      #
      # MANDATORY
      #
      image: centos-6

      # A 'size', in GCE terms, refers to the instance's 'machine type'.  See
      # the on-line documentation for a complete list of GCE machine types.
      #
      # MANDATORY
      #
      size: n1-standard-1

      # A 'location', in GCE terms, refers to the instance's 'zone'.  GCE
      # has the notion of both Regions (e.g. us-central1, europe-west1, etc)
      # and Zones (e.g. us-central1-a, us-central1-b, etc).
      #
      # MANDATORY
      #
      location: europe-west1-b

      # Use this setting to define the network resource for the instance.
      # All GCE projects contain a network named 'default' but it's possible
      # to use this setting to create instances belonging to a different
      # network resource.
      #
      network: default

      # GCE supports instance/network tags and this setting allows you to
      # set custom tags.  It should be a list of strings and must be
      # parse-able by the python ast.literal_eval() function to convert it
      # to a python list.
      #
      tags: '["one", "two", "three"]'

      # GCE supports instance metadata and this setting allows you to
      # set custom metadata.  It should be a hash of key/value strings and
      # parse-able by the python ast.literal_eval() function to convert it
      # to a python dictionary.
      #
      metadata: '{"one": "1", "2": "two"}'

      # Use this setting to ensure that when new instances are created,
      # they will use a persistent disk to preserve data between instance
      # terminations and re-creations.
      #
      use_persistent_disk: True

      # In the event that you wish the boot persistent disk to be permanently
      # deleted when you destroy an instance, set delete_boot_pd to True.
      #
      delete_boot_pd: False


GCE instances do not allow remote access to the root user by default.
Instead, another user must be used to run the deploy script using sudo.

.. code-block:: yaml

    my-gce-config:
      # Configure which user to use to run the deploy script
      ssh_username: user
      ssh_keyfile: /home/user/.ssh/google_compute_engine


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
in turn be used to create other persistend disks. Note that to prevent data
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
New networks require a name and CIDR range. New instances can be created
and added to this network by setting the network name during create. It is
not possible to add/remove existing instances to a network.

.. code-block:: bash

    salt-cloud -f create_network gce name=mynet cidr=10.10.10.0/24

Destroy network
---------------
Destroy a network by specifying the name. Make sure that there are no
instances associated with the network prior to deleting it or you'll have
a bad day.

.. code-block:: bash

    salt-cloud -f delete_network gce name=mynet

Show network
------------
Specify the network name to view information about the network.

.. code-block:: bash

    salt-cloud -f show_network gce name=mynet

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
`documentation <https://developers.google.com/compute/docs/load-balancing/>`_
for a more complete discription.

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
and list of healtch checks. Deleting or showing details about the LB only
requires the name.

.. code-block:: bash

    salt-cloud -f create_lb gce name=lb region=... ports=80 members=w1,w2,w3
    salt-cloud -f delete_lb gce name=lb
    salt-cloud -f show_lb gce name=lb


Attach and Detach LB
--------------------
It is possible to attach or detach an instance from an existing load-balancer.
Both the instance and load-balancer must exist before using these functions.

.. code-block:: bash

    salt-cloud -f attach_lb gce name=lb member=w4
    salt-cloud -f detach_lb gce name=lb member=oops

