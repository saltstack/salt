VM Profiles
===========

Salt cloud designates virtual machines inside the profile configuration file.
The profile configuration file defaults to ``/etc/salt/cloud.profiles`` and is 
a yaml configuration. The syntax for declaring profiles is simple:

.. code-block:: yaml

    fedora_rackspace:
        provider: rackspace
        image: Fedora 17
        size: 256 server
        script: Fedora


A few key pieces of information need to be declared and can change based on the
public cloud provider. A number of additional parameters can also be inserted:

.. code-block:: yaml

    centos_rackspace:
        provider: rackspace
        image: CentOS 6.2
        size: 1024 server
        script: RHEL6
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
