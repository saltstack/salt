The MacOS X (Maverick) Developer Step By Step Guide To Salt Installation
========================================================================

This document provides a step-by-step guide to installing a Salt cluster
consisting of  one master, and one minion running on a local VM hosted on Mac OS X.


.. note::
    This guide is aimed at developers who wish to run Salt in a virtual machine.
    The official (Linux) walkthrough can be found
    `here <http://docs.saltstack.com/topics/tutorials/walkthrough.html>`_.



The 5 Cent Salt Intro
---------------------

Since you're here you've probably already heard about Salt, so you already
know Salt lets you configure and run commands on hordes of servers easily.
Here's a brief overview of a Salt cluster:

- Salt works by having a "master" server sending commands to one or multiple
  "minion" servers [#]_. The master server is the "command center". It is
  going to be the place where you store your configuration files, aka: "which
  server is the db, which is the web server, and what libraries and software
  they should have installed". The minions receive orders from the master.
  Minions are the servers actually performing work for your business.

- Salt has two types of configuration files:

  1. the "salt communication channels" or "meta"  or "config" configuration
  files (not official names): one for the master (usually is /etc/salt/master
  , **on the master server**), and one for minions (default is
  /etc/salt/minion or /etc/salt/minion.conf, **on the minion servers**). Those
  files are used to determine things like the Salt Master IP, port, Salt
  folder locations, etc.. If these are configured incorrectly, your minions
  will probably be unable to receive orders from the master, or the master
  will not know which software a given minion should install.

  2. the "business" or "service" configuration files (once again, not an
  official name): these are configuration files, ending with ".sls" extension,
  that describe which software should run on which server, along with
  particular configuration properties for the software that is being
  installed. These files should be created in the /srv/salt folder by default,
  but their location can be changed using ... /etc/salt/master configuration file!

.. note::

    This tutorial contains a third important configuration file, not to
    be confused with the previous two: the virtual machine provisioning
    configuration file. This in itself is not specifically tied to Salt, but
    it also contains some Salt configuration. More on that in step 3. Also
    note that all configuration files are YAML files. So indentation matters.

.. [#]

    Salt also works with "masterless" configuration where a minion is
    autonomous (in which case salt can be seen as a local configuration tool),
    or in "multiple master" configuration. See the documentation for more on
    that.



Before Digging In, The Architecture Of The Salt Cluster
-------------------------------------------------------

Salt Master
+++++++++++
The "Salt master" server is going to be the Mac OS machine, directly. Commands
will be run from a terminal app, so Salt will need to be installed on the Mac.
This is going to be more convenient for toying around with configuration files.

Salt Minion
+++++++++++
We'll only have one "Salt minion" server. It is going to be running on a
Virtual Machine running on the Mac, using VirtualBox. It will run an Ubuntu
distribution.


Step 1 - Configuring The Salt Master On Your Mac
================================================
`official documentation
<http://docs.saltstack.com/topics/installation/osx.html>`_

Because Salt has a lot of dependencies that are not built in Mac OS X, we will
use Homebrew to install Salt. Homebrew is a package manager for Mac, it's
great, use it (for this tutorial at least!). Some people spend a lot of time
installing libs by hand to better understand dependencies, and then realize how
useful a package manager is once they're configuring a brand new machine and
have to do it all over again. It also lets you *uninstall* things easily.

.. note::

    Brew is a Ruby program (Ruby is installed by default with your Mac). Brew
    downloads, compiles, and links software. The linking phase is when compiled
    software is deployed on your machine. It may conflict with manually
    installed software, especially in the /usr/local directory. It's ok,
    remove the manually installed version then refresh the link by typing
    ``brew link 'packageName'``. Brew has a ``brew doctor`` command that can
    help you troubleshoot. It's a great command, use it often. Brew requires
    xcode command line tools. When you run brew the first time it asks you to
    install them if they're not already on your system. Brew installs
    software in /usr/local/bin (system bins are in /usr/bin). In order to use
    those bins you need your $PATH to search there first. Brew tells you if
    your $PATH needs to be fixed.

.. tip::

    Use the keyboard shortcut ``cmd + shift + period`` in the "open" Mac OS X
    dialog box to display hidden files and folders, such as .profile.


Install Homebrew
----------------
Install Homebrew here http://brew.sh/
Or just type

.. code-block:: bash

    ruby -e "$(curl -fsSL https://raw.github.com/Homebrew/homebrew/go/install)"


Now type the following commands in your terminal (you may want to type ``brew
doctor`` after each to make sure everything's fine):

.. code-block:: bash

    brew install python
    brew install swig
    brew install zmq

.. note::

    zmq is ZeroMQ. It's a fantastic library used for server to server network
    communication and is at the core of Salt efficiency.

Install Salt
------------

You should now have everything ready to launch this command:

.. code-block:: bash

    pip install salt

.. note::

    There should be no need for ``sudo pip install salt``. Brew installed
    Python for your user, so you should have all the access. In case you
    would like to check, type ``which python`` to ensure that it's
    /usr/local/bin/python, and ``which pip`` which should be
    /usr/local/bin/pip.

Now type ``python`` in a terminal then, ``import salt``. There should be no
errors. Now exit the Python terminal using ``exit()``.

Create The Master Configuration
-------------------------------

If the default /etc/salt/master configuration file was not created,
copy-paste it from here:
http://docs.saltstack.com/ref/configuration/examples.html#configuration-examples-master

.. note::

    ``/etc/salt/master`` is a file, not a folder.

Salt Master configuration changes. The Salt master needs a few customization
to be able to run on Mac OS X:

.. code-block:: bash

    sudo launchctl limit maxfiles 4096 8192

In the /etc/salt/master file, change max_open_files to 8192 (or just add the
line: ``max_open_files: 8192`` (no quote) if it doesn't already exists).

You should now be able to launch the Salt master:

.. code-block:: bash

    sudo salt-master --log-level=all

There should be no errors when running the above command.

.. note::

    This command is supposed to be a daemon, but for toying around, we'll keep
    it running on a terminal to monitor the activity.


Now that the master is set, let's configure a minion on a VM.

Step 2 - Configuring The Minion VM
==================================

The Salt minion is going to run on a Virtual Machine. There are a lot of
software options that let you run virtual machines on a mac, But for this
tutorial we're going to use VirtualBox. In addition to virtualBox, we will use
Vagrant, which allows you to create the base VM configuration.

Vagrant lets you build ready to use VM images, starting from an OS image and
customizing it using "provisioners". In our case, we'll use it to:

* Download the base Ubuntu image
* Install salt on that Ubuntu image (Salt is going to be the "provisioner"
  for the VM).
* Launch the VM
* SSH into the VM to debug
* Stop the VM once you're done.

Install VirtualBox
------------------

Go get it here: https://www.virtualBox.org/wiki/Downloads (click on VirtualBox
for OS X hosts => x86/amd64)

Install Vagrant
---------------

Go get it here: http://downloads.vagrantup.com/ and choose the latest version
(1.3.5 at time of writing), then the .dmg file. Double-click to install it.
Make sure the ``vagrant`` command is found when run in the terminal. Type
``vagrant``. It should display a list of commands.

Create The Minion VM Folder
---------------------------

Create a folder in which you will store your minion's VM. In this tutorial,
it's going to be a minion folder in the $home directory.

.. code-block:: bash

    cd $home
    mkdir minion

Initialize Vagrant
------------------

From the minion folder, type

.. code-block:: bash

    vagrant init

This command creates a default Vagrantfile configuration file. This
configuration file will be used to pass configuration parameters to the Salt
provisioner in Step 3.

Import Precise64 Ubuntu Box
---------------------------

.. code-block:: bash

    vagrant box add precise64 http://files.vagrantup.com/precise64.box

.. note::

    This box is added at the global Vagrant level. You only need to do it
    once as each VM will use this same file.

Modify the Vagrantfile
----------------------

Modify ./minion/Vagrantfile to use th precise64 box. Change the ``config.vm.box``
line to:

.. code-block:: yaml

    config.vm.box = "precise64"

Uncomment the line creating a host-only IP. This is the ip of your minion
(you can change it to something else if that IP is already in use):

.. code-block:: yaml

    config.vm.network :private_network, ip: "192.168.33.10"


At this point you should have a VM that can run, although there won't be much
in it. Let's check that.

Checking The VM
---------------

From the $home/minion folder type:

.. code-block:: bash

    vagrant up

A log showing the VM booting should be present. Once it's done you'll be back
to the terminal:

.. code-block:: bash

    ping 192.168.33.10

The VM should respond to your ping request.

Now log into the VM in ssh using Vagrant again:

.. code-block:: bash

    vagrant ssh

You should see the shell prompt change to something similar to
``vagrant@precise64:~$`` meaning you're inside the VM. From there, enter the
following:

.. code-block:: bash

    ping 10.0.2.2

.. note::

    That ip is the ip of your VM host (the Mac OS X OS). The number is a
    VirtualBox default and is displayed in the log after the Vagrant ssh
    command. We'll use that IP to tell the minion where the Salt master is.
    Once you're done, end the ssh session by typing ``exit``.

It's now time to connect the VM to the salt master

Step 3 - Connecting Master and Minion
=====================================

Creating The Minion Configuration File
--------------------------------------

Create the ``/etc/salt/minion`` file. In that file, put the
following lines, giving the ID for this minion, and the IP of the master:

.. code-block:: yaml

    master: 10.0.2.2
    id: 'minion1'
    file_client: remote

Minions authenticate with the master using keys. Keys are generated
automatically if you don't provide one and can accept them later on. However,
this requires accepting the minion key every time the minion is destroyed or
created (which could be quite often). A better way is to create those keys in
advance, feed them to the minion, and authorize them once.

Preseed minion keys
-------------------

From the minion folder on your Mac run:

.. code-block:: bash

    sudo salt-key --gen-keys=minion1

This should create two files: minion1.pem, and minion1.pub.
Since those files have been created using sudo, but will be used by vagrant,
you need to change ownership:

.. code-block:: bash

    sudo chown youruser:yourgroup minion1.pem
    sudo chown youruser:yourgroup minion1.pub

Then copy the .pub file into the list of accepted minions:

.. code-block:: bash

    sudo cp minion1.pub /etc/salt/pki/master/minions/minion1


Modify Vagrantfile to Use Salt Provisioner
------------------------------------------

Let's now modify the Vagrantfile used to provision the Salt VM. Add the
following section in the Vagrantfile (note: it should be at the same
indentation level as the other properties):

.. code-block:: yaml

    # salt-vagrant config
    config.vm.provision :salt do |salt|
        salt.run_highstate = true
        salt.minion_config = "/etc/salt/minion"
        salt.minion_key = "./minion1.pem"
        salt.minion_pub = "./minion1.pub"
    end


Now destroy the vm and recreate it from the /minion folder:

.. code-block:: bash

    vagrant destroy
    vagrant up

If everything is fine you should see the following message:

.. code-block:: bash

    "Bootstrapping Salt... (this may take a while)
    Salt successfully configured and installed!"

Checking Master-Minion Communication
------------------------------------

To make sure the master and minion are talking to each other, enter the
following:

.. code-block:: bash

    sudo salt '*' test.ping

You should see your minion answering the ping. It's now time to do some
configuration.

Step 4 - Configure Services to Install On the Minion
====================================================

In this step we'll use the Salt master to instruct our minion to install
Nginx.

Checking the system's original state
------------------------------------

First, make sure that an HTTP server is not installed on our minion.
When opening a browser directed at ``http://192.168.33.10/`` You should get an
error saying the site cannot be reached.

Initialize the top.sls file
---------------------------

System configuration is done in ``/srv/salt/top.sls`` (and subfiles/folders),
and then applied by running the :py:func:`state.apply
<salt.modules.state.apply_>` function to have the Salt master order its minions
to update their instructions and run the associated commands.

First Create an empty file on your Salt master (Mac OS X machine):

.. code-block:: bash

    touch /srv/salt/top.sls

When the file is empty, or if no configuration is found for our minion
an error is reported:

.. code-block:: bash

    sudo salt 'minion1' state.apply

This should return an error stating: **No Top file or external nodes data
matches found**.

Create The Nginx Configuration
------------------------------

Now is finally the time to enter the real meat of our server's configuration.
For this tutorial our minion will be treated as a web server that needs to
have Nginx installed.

Insert the following lines into ``/srv/salt/top.sls`` (which should current be
empty).

.. code-block:: yaml

    base:
      'minion1':
        - bin.nginx

Now create ``/srv/salt/bin/nginx.sls`` containing the following:

.. code-block:: yaml

    nginx:
      pkg.installed:
        - name: nginx
      service.running:
        - enable: True
        - reload: True

Check Minion State
------------------

Finally, run the :py:func:`state.apply <salt.modules.state.apply_>` function
again:

.. code-block:: bash

    sudo salt 'minion1' state.apply

You should see a log showing that the Nginx package has been installed
and the service configured. To prove it, open your browser and navigate to
http://192.168.33.10/, you should see the standard Nginx welcome page.

Congratulations!

Where To Go From Here
---------------------

A full description of configuration management within Salt (sls files among
other things) is available here:
http://docs.saltstack.com/en/latest/index.html#configuration-management
