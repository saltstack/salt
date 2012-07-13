========================
Getting Started With EC2
========================

Amazon EC2 is a very widely used public cloud platform and one of the core
platforms Salt Cloud has been built to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up the location of the salt master
    minion:
      master: saltmaster.example.com

    # Set the EC2 login data
    EC2.id: HJGRYCILJLKJYG
    EC2.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    EC2.keyname: test
    EC2.securitygroup: quick-start
    EC2.private_key: /root/test.pem

    # Set up an optional default cloud provider
    provider: EC2

Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    base_ec2:
      image: ami-e565ba8c
      size: Micro Instance
      os: RHEL6

The profile can be realized now with a salt command:

.. code-block:: yaml

    # salt-cloud -p base_ec2 ami.example.com

The created virtual machine will be named ``ami.example.com`` in the amazon
cloud and will have the same salt ``id``.

Once the vm is created it will start up the Salt Minion and connect back to
the Salt Master.
