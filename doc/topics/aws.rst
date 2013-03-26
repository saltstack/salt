========================
Getting Started With AWS
========================

Amazon AWS is a very widely used public cloud platform and one of the core
platforms Salt Cloud has been built to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up an optional default cloud provider
    #
    provider: aws

    # Set up the location of the salt master
    #
    minion:
        master: saltmaster.example.com

    # Specify whether to use public or private IP for deploy script.
    #
    # Valid options are:
    #     private_ips - The salt-master is also hosted with AWS
    #     public_ips - The salt-master is hosted outside of AWS
    #
    AWS.ssh_interface: public_ips

    # Set the AWS access credentials (see below)
    #
    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'

    # Make sure this key is owned by root with permissions 0400.
    #
    AWS.private_key: /etc/salt/my_test_key.pem
    AWS.keyname: my_test_key
    AWS.securitygroup: default

    # Optionally configure default region
    #
    AWS.location: ap-southeast-1
    AWS.availability_zone: ap-southeast-1b

    # Configure which user to use to run the deploy script. This setting is
    # dependent upon the AMI that is used to deploy. It is usually safer to
    # configure this individually in a profile, than globally. Typical users
    # are:
    #
    # Amazon Linux -> ec2-user
    # RHEL         -> ec2-user
    # CentOS       -> ec2-user
    # Ubuntu       -> ubuntu
    #
    AWS.ssh_username: ec2-user


Access Credentials
==================
The ``id`` and ``key`` settings may be found in the Security Credentials area
of the AWS Account page:

https://portal.aws.amazon.com/gp/aws/securityCredentials

Both are located in the Access Credentials area of the page, under the Access
Keys tab. The ``id`` setting is labeled Access Key ID, and the ``key`` setting
is labeled Secret Access Key.


Key Pairs
=========
In order to create an instance with Salt installed and configured, a key pair
will need to be created. This can be done in the EC2 Management Console, in the
Key Pairs area. These key pairs are unique to a specific region. Keys in the
us-east-1 region can be configured at:

https://console.aws.amazon.com/ec2/home?region=us-east-1#s=KeyPairs

Keys in the us-west-1 region can be configured at

https://console.aws.amazon.com/ec2/home?region=us-west-1#s=KeyPairs

...and so on. When creating a key pair, the browser will prompt to download a
pem file. This file must be placed in a directory accessable by Salt Cloud,
with permissions set to either 0400 or 0600.


Security Groups
===============
An instance on AWS needs to belong to a security group. Like key pairs, these
are unique to a specific region. These are also configured in the EC2 Management
Console. Security groups for the us-east-1 region can be configured at:

https://console.aws.amazon.com/ec2/home?region=us-east-1#s=SecurityGroups

...and so on.

A security group defines firewall rules which an instance will adhere to. If
the salt-master is configured outside of AWS, the security group must open the
SSH port (usually port 22) in order for Salt Cloud to install Salt.


Cloud Profiles
==============
Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    base_aws:
        provider: aws
        image: ami-e565ba8c
        size: Micro Instance
        ssh-user: ec2-user

The profile can be realized now with a salt command:

.. code-block:: bash

    # salt-cloud -p base_aws ami.example.com

This will create an instance named ``ami.example.com`` in EC2. The minion that
is installed on this instance will have an ``id`` of ``ami.example.com``. If
the command was executed on the salt-master, its Salt key will automatically be
signed on the master.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    # salt 'ami.example.com' test.ping


Required Settings
=================
The following settings are always required for AWS:

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
    AWS.ssh_interface: public_ips

Many AWS instances do not allow remote access to the root user by default.
Instead, another user must be used to run the deploy script using sudo. Some
common usernames include ec2-user (for Amazon Linux), ubuntu (for Ubuntu
instances), admin (official Debian) and bitnami (for images provided by
Bitnami).

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


Rename on Destroy
=================
When instances on AWS are destroyed, there will be a lag between the time that
the action is sent, and the time that Amazon cleans up the instance. During this
time, the instance still retails a Name tag, which will cause a collision if the
creation of an instance with the same name is attempted before the cleanup
occurs. In order to avoid such collisions, Salt Cloud can be configured to
rename instances when they are destroyed. The new name will look something like:

.. code-block:: bash

    myinstance-DEL20f5b8ad4eb64ed88f2c428df80a1a0c

In order to enable this, add AWS.rename_on_destroy line to the main
configuration file:

.. code-block:: yaml

    AWS.rename_on_destroy: True


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

IMPORTANT: Because this driver is in experimental status, its usage and
configuration should be expected to change.

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
single instance only. In an environment with several machines, this will save a
user from having to sort through all instance data, just to examine a single
instance.

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


Volume Management
=================
The EC2 driver has several functions and actions for management of EBS volumes.


Creating Volumes
----------------
A volume may be created, independent of an instance. A zone must be specified.
A size or a snapshot may be specified (in GiB). If neither is given, a default
size of 10 GiB will be used. If a snapshot is given, the size of the snapshot
will be used.

.. code-block:: bash

    salt-cloud -f create_volume ec2 zone=us-east-1b
    salt-cloud -f create_volume ec2 zone=us-east-1b size=10
    salt-cloud -f create_volume ec2 zone=us-east-1b snapshot=snap12345678


Attaching Volumes
-----------------
Unattached volumes may be attached to an instance. The following values are
required: name or instance_id, volume_id and device.

.. code-block:: bash

    salt-cloud -a attach_volume myinstance volume_id=vol-12345 device=/dev/sdb1


Show a Volume
-------------
The details about an existing volume may be retreived.

.. code-block:: bash

    salt-cloud -a show_volume myinstance volume_id=vol-12345
    salt-cloud -f show_volume ec2 volume_id=vol-12345


Detaching Volumes
-----------------
An existing volume may be detached from an instance.

.. code-block:: bash

    salt-cloud -a detach_volume myinstance volume_id=vol-12345


Deleting Volumes
----------------
A volume that is not attached to an instance may be deleted.

.. code-block:: bash

    salt-cloud -f delete_volume ec2 volume_id=vol-12345


Managing Key Pairs
==================
The EC2 driver has the ability to manage key pairs.


Creating a Key Pair
-------------------
A key pair is required in order to create an instance. When creating a key pair
with this function, the return data will contain a copy of the private key.
This private key is not stored by Amazon, and will not be obtainable past this
point, and should be stored immediately.

.. code-block:: bash

    salt-cloud -f create_keypair ec2 keyname=mykeypair


Show a Key Pair
---------------
This function will show the details related to a key pair, not including the
private key itself (which is not stored by Amazon).

.. code-block:: bash

    salt-cloud -f show_keypair ec2 keyname=mykeypair


Delete a Key Pair
-----------------
This function removes the key pair from Amazon.

.. code-block:: bash

    salt-cloud -f delete_keypair ec2 keyname=mykeypair

