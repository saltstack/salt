==============================
Getting Started With Parallels
==============================

Parallels Cloud Server is a product by Parallels that delivers a cloud hosting 
solution. The PARALLELS module for Salt Cloud enables you to manage instances 
hosted by a provider using PCS. Further information can be found at:

http://www.parallels.com/products/pcs/

* Using the old format, set up the cloud configuration at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up the location of the salt master
    #
    minion:
        master: saltmaster.example.com

    # Set the PARALLELS access credentials (see below)
    #
    PARALLELS.user: myuser
    PARALLELS.password: badpass

    # Set the access URL for your PARALLELS provider
    #
    PARALLELS.url: https://api.cloud.xmission.com:4465/paci/v1.0/


* Using the new format, set up the cloud configuration at 
  ``/etc/salt/cloud.providers`` or 
  ``/etc/salt/cloud.providers.d/parallels.conf``:

.. code-block:: yaml

    my-parallels-config:
      # Set up the location of the salt master
      #
      minion:
        master: saltmaster.example.com

      # Set the PARALLELS access credentials (see below)
      #
      user: myuser
      password: badpass

      # Set the access URL for your PARALLELS provider
      #
      url: https://api.cloud.xmission.com:4465/paci/v1.0/
      provider: parallels



Access Credentials
==================
The ``user``, ``password`` and ``url`` will be provided to you by your cloud 
provider. These are all required in order for the PARALLELS driver to work.


Cloud Profiles
==============
Set up an initial profile at ``/etc/salt/cloud.profiles`` or 
``/etc/salt/cloud.profiles.d/parallels.conf``:


* Using the old cloud configuration format:

.. code-block:: yaml

    parallels-ubuntu:
        provider: parallels
        image: ubuntu-12.04-x86_64


* Using the new cloud configuration format and the cloud configuration example 
  from above:

.. code-block:: yaml

    parallels-ubuntu:
        provider: my-parallels-config
        image: ubuntu-12.04-x86_64



The profile can be realized now with a salt command:

.. code-block:: bash

    # salt-cloud -p parallels-ubuntu myubuntu

This will create an instance named ``myubuntu`` on the cloud provider. The 
minion that is installed on this instance will have an ``id`` of ``myubuntu``.
If the command was executed on the salt-master, its Salt key will automatically 
be signed on the master.

Once the instance has been created with salt-minion installed, connectivity to 
it can be verified with Salt:

.. code-block:: bash

    # salt myubuntu test.ping


Required Settings
=================
The following settings are always required for PARALLELS:


* Using the old cloud configuration format:

.. code-block:: yaml

    PARALLELS.user: myuser
    PARALLELS.password: badpass
    PARALLELS.url: https://api.cloud.xmission.com:4465/paci/v1.0/


* Using the new cloud configuration format:

.. code-block:: yaml

    my-parallels-config:
      user: myuser
      password: badpass
      url: https://api.cloud.xmission.com:4465/paci/v1.0/
      provider: parallels


Optional Settings
=================
Unlike other cloud providers in Salt Cloud, Parallels does not utilize a 
``size`` setting. This is because Parallels allows the end-user to specify a 
more detailed configuration for their instances, than is allowed by many other 
cloud providers. The following options are available to be used in a profile, 
with their default settings listed.

.. code-block:: yaml

    # Description of the instance. Defaults to the instance name.
    desc: <instance_name>

    # How many CPU cores, and how fast they are (in MHz)
    cpu_number: 1
    cpu_power: 1000

    # How many megabytes of RAM
    ram: 256

    # Bandwidth available, in kbps
    bandwidth: 100

    # How many public IPs will be assigned to this instance
    ip_num: 1

    # Size of the instance disk (in GiB)
    disk_size: 10

    # Username and password
    ssh_username: root
    password: <value from PARALLELS.password>

    # The name of the image, from ``salt-cloud --list-images parallels``
    image: ubuntu-12.04-x86_64
