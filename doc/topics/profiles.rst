VM Profiles
===========

Salt cloud designates virtual machines inside the profile configuration file.
The profile configuration file defaults to ``/etc/salt/cloud.profiles`` and is a
yaml configuration. The syntax for declaring profiles is simple:

.. code-block:: yaml

    fedora_rackspace:
      provider: rackspace
      image: Fedora 17
      size: 256 server
      script: Fedora

A few key peices of information need to be declared and can change based on the
public cloud provider. A number of additional parameters can also be inserted:

.. code-block:: yaml

    centos_rackspace:
      provider: rackspace
      image: CentOS 6.2
      size: 1024 server
      script: RHEL6
      minion:
        master: salt.example.com
      grains:
        role: webserver

Some parameters can be specified in the main Salt cloud config file and then
are applied to all cloud profiles. For instance if only a single cloud provider
is being used then the provider option can be declared in the Salt cloud config
file.

Larger Example
--------------

.. code-block:: yaml

    rhel_aws:
      provider: aws
      image: ami-e565ba8c
      size: Micro Instance
      script: RHEL6
      minion:
          cheese: edam

    ubuntu_aws:
      provider: aws
      image: ami-7e2da54e
      size: Micro Instance
      script: Ubuntu
      minion:
          cheese: edam

    ubuntu_rackspace:
      provider: rackspace
      image: Ubuntu 12.04 LTS
      size: 256 server
      script: Ubuntu
      minion:
          cheese: edam

    fedora_rackspace:
      provider: rackspace
      image: Fedora 17
      size: 256 server
      script: Fedora
      minion:
          cheese: edam

    cent_linode:
      provider: linode
      image: CentOS 6.2 64bit
      size: Linode 512
      script: RHEL6

    cent_gogrid:
      provider: gogrid
      image: 12834
      size: 512MB
      script: RHEL6

    cent_joyent:
      provider: joyent
      image: centos-6
      script: RHEL6
      size: Small 1GB
