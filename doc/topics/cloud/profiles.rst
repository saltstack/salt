.. _salt-cloud-profiles:

VM Profiles
===========

Salt cloud designates virtual machines inside the profile configuration file.
The profile configuration file defaults to ``/etc/salt/cloud.profiles`` and is
a yaml configuration. The syntax for declaring profiles is simple:

.. code-block:: yaml

    fedora_rackspace:
        provider: my-rackspace-config
        image: Fedora 17
        size: 256 server
        script: bootstrap-salt

It should be noted that the ``script`` option defaults to ``bootstrap-salt``,
and does not normally need to be specified. Further examples in this document
will not show the ``script`` option.

A few key pieces of information need to be declared and can change based on the
cloud provider. A number of additional parameters can also be inserted:

.. code-block:: yaml

    centos_rackspace:
      provider: my-rackspace-config
      image: CentOS 6.2
      size: 1024 server
      minion:
        master: salt.example.com
        append_domain: webs.example.com
        grains:
          role: webserver


The image must be selected from available images. Similarly, sizes must be
selected from the list of sizes. To get a list of available images and sizes
use the following command:

.. code-block:: bash

    salt-cloud --list-images openstack
    salt-cloud --list-sizes openstack


Some parameters can be specified in the main Salt cloud configuration file and
then are applied to all cloud profiles. For instance if only a single cloud
provider is being used then the provider option can be declared in the Salt
cloud configuration file.


Multiple Configuration Files
----------------------------

In addition to ``/etc/salt/cloud.profiles``, profiles can also be specified in
any file matching ``cloud.profiles.d/*conf`` which is a sub-directory relative
to the profiles configuration file(with the above configuration file as an
example, ``/etc/salt/cloud.profiles.d/*.conf``).  This allows for more
extensible configuration, and plays nicely with various configuration
management tools as well as version control systems.


Larger Example
--------------

.. code-block:: yaml

    rhel_ec2:
      provider: my-ec2-config
      image: ami-e565ba8c
      size: t1.micro
      minion:
        cheese: edam

    ubuntu_ec2:
      provider: my-ec2-config
      image: ami-7e2da54e
      size: t1.micro
      minion:
        cheese: edam

    ubuntu_rackspace:
      provider: my-rackspace-config
      image: Ubuntu 12.04 LTS
      size: 256 server
      minion:
        cheese: edam

    fedora_rackspace:
      provider: my-rackspace-config
      image: Fedora 17
      size: 256 server
      minion:
        cheese: edam

    cent_linode:
      provider: my-linode-config
      image: CentOS 6.2 64bit
      size: Linode 512

    cent_gogrid:
      provider: my-gogrid-config
      image: 12834
      size: 512MB

    cent_joyent:
      provider: my-joyent-config
      image: centos-7
      size: g4-highram-16G
