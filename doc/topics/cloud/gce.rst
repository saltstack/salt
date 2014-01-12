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
* Source install of `Libcloud <https://github.com/apache/libcloud>`_ (or greater than 0.14.0-beta3 when available)
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
   In your Project, go to the *APIs & auth* section and *APIs* link and
   enable the Google Compute Engine service.

#. Create a Service Account
   To set up authorization, navigate to *APIs & auth* section and then the
   *Registered apps* link and click the *REGISTER APP* button.  Give it a
   meaningful name like and select *Web Application*.  After clicking the
   *Register* button, select *Certificate* in the next screen.  Click the
   *Generate Certificate* button, record the generated email address for
   use in the ``service_account_email_address`` of your ``/etc/salt/cloud``
   file.  Also download and save the generated private key.

#. You will need to convert the private key to a format compatible with
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
