========================
Getting Started With AWS
========================

Amazon AWS is a very widely used public cloud platform and one of the core
platforms Salt Cloud has been built to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up the location of the salt master
    minion:
      master: saltmaster.example.com

    # Set the AWS login data
    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    AWS.keyname: test
    AWS.securitygroup: quick-start
    AWS.private_key: /root/test.pem

    # Set up an optional default cloud provider
    provider: AWS

    # Optionally configure default region
    AWS.location: ap-southeast-1
    AWS.availability_zone: ap-southeast-1b

    # Specify whether to use public or private IP for deploy script
    AWS.ssh_interface

    # Configure which user to use to run the deploy script
    AWS.ssh_username

Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    base_aws:
      provider: aws
      image: ami-e565ba8c
      size: Micro Instance
      os: RHEL6

The profile can be realized now with a salt command:

.. code-block:: yaml

    # salt-cloud -p base_aws ami.example.com

The created virtual machine will be named ``ami.example.com`` in the amazon
cloud and will have the same salt ``id``.

Once the vm is created it will start up the Salt Minion and connect back to
the Salt Master.
