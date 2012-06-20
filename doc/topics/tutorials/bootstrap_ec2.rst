===============================================
Bootstrapping Salt on Linux EC2 with Cloud-Init
===============================================

`Salt <http://saltstack.org>`_ is a great tool for remote execution and
configuration management, however you will still need to bootstrap the
daemon when spinning up a new node. One option is to create and save a
custom `AMI`_, but this creates another resource to maintain and document.

A better method for Linux machines uses Canonical's `CloudInit
<https://help.ubuntu.com/community/CloudInit>`_ to run a bootstrap script
during an `EC2 Instance`_ initialization. Cloud-init takes the ``user_data``
string passed into a new AWS instance and runs it in a manner similar to
rc.local. The bootstrap script needs to:

#. Install `Salt`_ with dependencies
#. Point the minion to the master

Here is a sample script::

    #!/bin/bash

    # Install saltstack
    add-apt-repository ppa:saltstack/salt -y
    apt-get update -y
    apt-get install salt -y
    apt-get upgrade -y

    # Set salt master location and start minion
    cp /etc/salt/minion.template /etc/salt/minion
    sed -i '' -e 's/#master: salt/master: [salt_master_fqdn]' /etc/salt/minion
    salt-minion -d

First the script adds the saltstack ppa and installs the package. Then
we copy over the minion config template and tell it where to find the
master. You will have to replace ``[salt_master_fqdn]`` with something
that resolves to your Salt master.

.. _`AMI`: https://en.wikipedia.org/wiki/Amazon_Machine_Image
.. _`EC2 Instance`: http://aws.amazon.com/ec2/instance-types/

Used With Boto
--------------

`Boto <https://github.com/boto/boto>`_ will accept a string for user data
which can be used to pass our bootstrap script. If the script is saved to
a file, you can read it into a string::

    import boto

    user_data = open('salt_bootstrap.sh')

    conn = boto.connect_ec2(<AWS_ACCESS_ID>, <AWS_SECRET_KEY>)

    reservation = conn.run_instances(image_id=<ami_id>,
                                     key_name=<key_name>,
                                     user_data=user_data.read())


Additional Notes
----------------

Sometime in the future the ppa will include and install an upstart file. In the 
meantime, you can use the bootstrap to `build one <https://gist.github.com/1617054>`_.

It may also be useful to set the node's role during this phase. One option
would be saving the node's role to a file and then using a custom Grain
to select it.
