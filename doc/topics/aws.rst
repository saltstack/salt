========================
Getting Started With AWS
========================

Amazon AWS is a very widely used public cloud platform and one of the core
platforms Salt Cloud has been built to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up an optional default cloud provider
    provider: AWS

    # Set up the location of the salt master
    minion:
      master: saltmaster.example.com

    # Specify whether to use public or private IP for deploy script
    # private_ips or public_ips.
    # Use private_ips if your salt-master is on a private vlan
    AWS.ssh_interface: public_ips

    # Set the AWS login data. You will have to change all of these.
    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'

    # Make sure this key is owned by root with permissions 0400.
    AWS.private_key: /etc/salt/my_test_key.pem
    AWS.keyname: my_test_key
    AWS.securitygroup: default

    # Optionally configure default region
    AWS.location: ap-southeast-1
    AWS.availability_zone: ap-southeast-1b

    # Configure which user to use to run the deploy script
    # This depends on what distro you will be using (specifically, on what AMI)
    # If you are using multiple distros, do NOT set this here.
    # Instead set it for each profile in the cloud.profiles discussed below.
    # ubuntu -> ubuntu
    # RHEL -> ec2-user
    AWS.ssh_username: ec2-user


To configure these, start by log into your amazon account and go to
:doc:`https://portal.aws.amazon.com/gp/aws/securityCredentials <https://portal.aws.amazon.com/gp/aws/securityCredentials>`
For ``id``, and ``key`` under the  Access Keys section, pick an Access Key Id and matching Secret Access Key
(you will have to click show to see the secret)

Next, log into :doc:`https://console.aws.amazon.com/ec2/home?region=us-east-1#s=KeyPairs <https://console.aws.amazon.com/ec2/home?region=us-east-1#s=KeyPairs>`
You should find a Key Pair Name there. This is your ``keyname``.
For the reset of this document, we'll call that key my_test_key.
For your ``private_key`` look in ~/.ssh on the laptop or desktop.
If you used a pre-existing ssh key, make sure the private key is in PEM format.
Upload it to the salt master, move / rename it to /etc/salt/my_test_key.pem
Make sure it is owned by root with permissions set to 0400.
If you went with the defaults when you configured your AWS account,
your ``securitygroup`` will be default.
If you followed the quick-start guide it may be quickstart.

Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    base_aws:
      provider: aws
      image: ami-e565ba8c
      size: Micro Instance
      script: RHEL6
      ssh-user: ec2-user

The profile can be realized now with a salt command:

.. code-block:: bash

    # salt-cloud -p base_aws ami.example.com

The created virtual machine will be named ``ami.example.com`` in the amazon
cloud and will have the same salt ``id``.

Once the vm is created it will start up the Salt Minion and connect back to
the Salt Master.
You can confirm this is by running the following on hte salt master.

.. code-block: bash

    # salt 'ami.example.com' cmd.run 'uname -a'

Required Settings
=================

AWS has several options that are always required:

.. code-block:: yaml

    # Set the AWS login data
    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    AWS.keyname: test
    AWS.securitygroup: quick-start
    AWS.private_key: /root/test.pem

Optional Settings
=================

AWS allows a location to be set for servers to be deployed in. Availability
zones exist inside regions, and may be added to increase specificity.

.. code-block:: yaml

    # Optionally configure default region
    AWS.location: ap-southeast-1
    AWS.availability_zone: ap-southeast-1b

AWS instances can have a public or private IP, or both. When an instance is
deployed, Salt Cloud needs to log into it via SSH to run the deploy script.
By default, the public IP will be used for this. If the salt-cloud command
is run from another AWS instance, the private IP should be used.

.. code-block:: yaml

    # Specify whether to use public or private IP for deploy script
    # private_ips or public_ips
    AWS.ssh_interface: public_ip

AWS instances may not allow remote access to the root user by default. Instead,
another user must be used to run the deploy script using sudo. Some common
usernames include ec2-user (for Amazon Linux), ubuntu (for Ubuntu instances),
admin (official Debian) and bitnami (for images provided by Bitnami).

.. code-block:: yaml

    # Configure which user to use to run the deploy script
    AWS.ssh_username: ec2-user

Multiple usernames can be provided, in which case Salt Cloud will attempt to
guess the correct username. This is mostly useful in the main configuration
file:

.. code-block:: yaml

    AWS.ssh_username:
      - ec2-user
      - ubuntu
      - admin
      - bitnami

Multiple security groups can also be specified in the same fashion:

.. code-block:: yaml

    AWS.securitygroup:
      - default
      - extra

Modify AWS Tags
===============
One of the features of AWS is the ability to tag resources. In fact, under the
hood, the names given to EC2 instances by salt-cloud are actually just stored
as a tag called Name. Salt Cloud has the ability to manage these tags:

.. code-block:: bash

    salt-cloud -a get_tags mymachine
    salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
    salt-cloud -a del_tags mymachine tag1,tag2,tag3

Rename AWS Instances
====================
As mentioned above, AWS instances are named via a tag. However, renaming an
instance by renaming its tag will cause the salt keys to mismatch. A rename
function exists which renames both the instance, and the salt keys.

.. code-block:: bash

    salt-cloud -a rename mymachine newname=yourmachine

AWS Termination Protection
==========================
AWS allows the user to enable and disable termination protection on a specific
instance. An instance with this protection enabled cannot be destroyed.

.. code-block:: bash

    salt-cloud -a enable_term_protect mymachine
    salt-cloud -a disable_term_protect mymachine

EC2 Images
==========
The following are lists of available AMI images, generally sorted by OS. These
lists are on 3rd-party websites, are not managed by Salt Stack in any way. They
are provided here as a reference for those who are interested, and contain no
warranty (express or implied) from anyone affiliated with Salt Stack. Most of
them have never been used, much less tested, by the Salt Stack team.

* `Arch Linux`__
.. __: https://wiki.archlinux.org/index.php/Arch_Linux_AMIs_for_Amazon_Web_Services

* `FreeBSD`__
.. __: http://www.daemonology.net/freebsd-on-ec2/

* `Fedora`__
.. __: https://fedoraproject.org/wiki/Cloud_images

* `CentOS`__
.. __: http://wiki.centos.org/Cloud/AWS

* `Ubuntu`__
.. __: http://cloud-images.ubuntu.com/locator/ec2/

* `Debian`__
.. __: http://wiki.debian.org/Cloud/AmazonEC2Image

* `Gentoo`__
.. __: https://aws.amazon.com/amis?platform=Gentoo&selection=platform

* `All Images on Amazon`__
.. __: https://aws.amazon.com/amis

Experimental EC2 Driver
=======================
An experimental driver has been added to Salt Cloud called EC2. The
configuration for this driver is the same as for AWS, but with EC2 in the
argument names:

.. code-block:: yaml

    # Set the EC2 login data
    EC2.id: HJGRYCILJLKJYG
    EC2.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    EC2.keyname: test
    EC2.securitygroup: quick-start
    EC2.private_key: /root/test.pem

This driver contains optimizations over the old AWS driver, which increase
speed and functionality. However, because this is a new driver, it is currently
considered to be experimental, and as such, the old AWS driver may still be
used as before.

The remainder of this document describes settings which may be used with the
EC2 driver.

show_image
==========
This is a function that describes an AMI on EC2. This will give insight as to
the defaults that will be applied to an instance using a particular AMI.

.. code-block:: bash

    $ salt-cloud -f show_image ec2 image=ami-fd20ad94

show_instance
=============
This action is a thin wrapper around --full-query, which displays details on a
single instance only. In an environment with several machines, this will save
a user from having to sort through all instance data, just to examine a
single instance.

.. code-block:: bash

    $ salt-cloud -a show_instance myinstance

delvol_on_destroy
=================
This argument overrides the default DeleteOnTermination setting in the AMI for
the root EBS volume for an instance. Many AMIs contain 'false' as a default,
resulting in orphaned volumes in the EC2 account, which may unknowingly be
charged to the account. This setting can be added to the profile or map file
for an instance.

.. code-block:: yaml

    delvol_on_destroy: True


This can also be set as a global setting in the EC2 cloud configuration:

.. code-block:: yaml

    EC2.delvol_on_destroy: True


The setting for this may be changed on an existing instance using one of the
following commands:

.. code-block:: bash

    salt-cloud -a delvol_on_destroy myinstance
    salt-cloud -a keepvol_on_destroy myinstance


EC2 Termination Protection
==========================
AWS allows the user to enable and disable termination protection on a specific
instance. An instance with this protection enabled cannot be destroyed. The EC2
driver adds a show_term_protect action to the regular AWS functionality.

.. code-block:: bash

    salt-cloud -a show_term_protect mymachine
    salt-cloud -a enable_term_protect mymachine
    salt-cloud -a disable_term_protect mymachine


Alternate Endpoint
==================
Normally, ec2 endpoints are build using the region and the service_url. The
resulting endpoint would follow this pattern:

.. code-block::

    ec2.<region>.<service_url>

This results in an endpoint that looks like:

.. code-block::

    ec2.us-east-1.amazonaws.com

There are other projects that support an EC2 compatibility layer, which this
scheme does not account for. This can be overridden by specifying the endpoint
directly in the main cloud configuration file:

.. code-block:: yaml

    EC2.endpoint: myendpoint.example.com:1138/services/Cloud

