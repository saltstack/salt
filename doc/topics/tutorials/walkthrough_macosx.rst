The MacOS X (Maverick) developper step by step guide to salt installation
=========================================================================

This document provides a step by step guide to installing a salt cluster (one master, one minion running on a local VM) on Mac OS X to start playing with salt. It is aimed at developers, so it may be a little too slow for experienced admins. At the end of it, you will have installed a bare nginx on a minion using the master.
The official (linux) walkthrough can be found `here
<http://docs.saltstack.com/topics/tutorials/walkthrough.html>`_.



5 cents intro to salt
---------------------

Since you're here you've probably already heard about salt, so you already know salts lets you configure and run commands on hordes of servers easily. Here's a brief overview of a salt cluter.

- Salt works by having a "master" server sending commands to one or multiple "minion" servers [#]_. The master server is the "command center". It is going to be the place where you store your configuration files, aka : "which server is the db, which is the www server, and what libraries and software should they have installed". The minions receive orders from the master. Minions are the servers actually performing work for your business.

- Salt has two types of configuration files :

  1. the "salt communication channels" or "meta"  or "config" configuration files (not official names) : one for the master (usually is /etc/salt/master, **on the master server**), and one for minions (default is /etc/salt/minion or /etc/salt/minion.conf, **on the minion servers**). Those files are used to determine things like master ip , port, salt folder locations, etc.. If those are misconfigured, your minions will probably not be able to receive orders from the master, or the master will not know which software a given minion should install.

  2. the "business" or "service" configuration files (once again, not an official name) : those are configuration files, ending with ".tls" extension, that describe which software should run on which server, along with particular configuration properties for those software. Those files should be created in the /srv/salt folder by default, but their location can be changed using ... /etc/salt/master configuration file !

.. note:: this tutorial contains a third important configuration file, not to be confused with the previous two : the virtual machine provisioning configuration file. This, in itself, is not specifically tied to salt, but it also contains some salt configuration. More on that in step 3. Also note that all configuration files are YAML files. So indentation matters a lot.

.. [#] : salt also works with "masterless" configuration where a minion is autonomous (in which case salt can be seen as a local configuration tool), or in
  "multiple master" configuration. See the documentation for more on that.



Before digging in : architecture of the salt cluster
---------------------------------------------------

Salt-master
+++++++++++
The "salt-master" server is going to be the mac os machine, directly. Command will be ran from a terminal app, so salt will need to be installed on the mac. This is going to be more convenient for toying around with configuration files.

Salt-minion
+++++++++++
We'll only have one "salt minion" server. It is going to be running on a Virtual Machine running on the mac, using VirtualBox. It will run an Ubuntu distribution.


STEP 1 : Configuring salt-master on your mac :
=========================================================================

`official documentation
<http://docs.saltstack.com/topics/installation/osx.html>`_

Because salt has a lot of dependencies that are not built in Mac Os X, we will use homebrew to install salt. Homebrew is a package manager for Mac, it's great, use it. Some people spend a lot of time installing libs by hand for learning, and realize how useful a package manager is once they've on a brand new machine and have to do it all over again. It also lets you *uninstall* things easily.

.. note::
  brew is a ruby program (ruby is installed by default with your mac). brew downloads, compile and link software. The linking phase is when compiled software are deployed on your machine. It may conflict with previously manually installed software, especially in the /usr/local directory. It's ok, remove them then restart the link by typing brew link thepackage. 
  Brew has a "brew doctor" command that help you troubleshoot. It's a great command, use it often.
  brew requires xcode command line tools. When you run brew the first time, it asks you to install them if they're not already on your system.
  brew installs softwares in /usr/local/bin (system bins are in /usr/bin). In order to use those bins you need your $PATH to search there first. Brew tells you if your $PATH needs to be fixed.

.. tip:: Keyboard shortcut "cmd + shift + comma" in the "open" Mac OS X dialog box to display hidden files and folders, such as .profile.


Install homebrew
----------------
Install homebrew here http://brew.sh/
Or just type

.. code-block:: bash

    ruby -e "$(curl -fsSL https://raw.github.com/mxcl/homebrew/go)"


Now type the following commands in your terminal  (you may want to type brew doctor after each to make sure everything's fine) :

.. code-block:: bash

    brew install python
    brew install swig
    brew install zmq

.. note:: zmq is zero mq. It's a fantastic library used for server to server network communication and is at the core of salt efficiency.

Install salt
------------

you should now have everything ready to launch this command : 

.. code-block:: bash

    pip install salt

.. note:: there should be no need for sudo pip install salt. Brew installed python for your user, so you should have all the access. In case of a doubt, type "which python" to check that it's /usr/local/bin/python, and "which pip" which should be /usr/local/bin/pip.

Now type "python" in a terminal then "import salt". There should be no error. (and type "exit()" to quit python like a gentleman instead of hammering ctrl-c :))

Create master configuration
---------------------------
- if no default /etc/salt/master configuration file was created, copy-paste it from here : http://docs.saltstack.com/ref/configuration/examples.html#configuration-examples-master (note that in "/etc/salt/master", master is the file itself, not a folder).

- Salt-master customizations. Salt master needs a few customization to be able to run on Mac OS X :

.. code-block:: bash

    sudo launchctl limit maxfiles 4096 8192

- In the /etc/salt/master file, change max_open_files to 8192 (or just add the line : "max_open_files: 8192" (no quote) if it doesn't already exists)

You should now be able to launch salt-master typing

.. code-block:: bash

    sudo salt-master --log-level=all

and there should be no error.

.. note:: this command is supposed to be a daemon, but for toying around, we'll keep it running on a terminal to monitor the activity.


Now that the master is set, let's configure a minion on a VM

STEP2 : Configuring the minion's VM
=========================================================================

Minion is going to run on a Virtual Machine. There are a lot of software that lets you run virtual machines on a mac, but a really good one is free : Virtualbox. In addition to virtualbox, we will use Vagrant, that lets you create base VM configuration.

Vagrant lets you build ready to use VM images, starting from a base OS image and customizing it using "provisionners".
In our case, we'll use it to:

* Download the base ubuntu image
* Install salt on that ubuntu image (salt is going to be the "provisionner" for the vm).
* Launch the vm
* SSH into the vm to debug
* Stop the vm once you're done.

Install Virtualbox
------------------
Go get it here : https://www.virtualbox.org/wiki/Downloads (click on VirtualBox for OS X hosts => x86/amd64)

Install Vagrant
---------------
Go get it here : http://downloads.vagrantup.com/ choose to latest version (1.3.5 at time of writing), then the .dmg file. double-click install it.
Make sure vagrant command is found in the terminal. Type "vagrant". It should display the list of commands.

Create the minion VM folder
---------------------------
Create a folder in which you will store your minion's VM. In this tutorial, it's going to be a minion folder in the $home directory.

.. code-block:: bash

    cd $home
    mkdir minion


Init Vagrant
------------
From the minion folder, type

.. code-block:: bash

    vagrant init

That command creates a default Vagrantfile configuration file. This configuration file will be used to pass configuration parameters to the salt provisionner in STEP 3.

Import Precise64 Ubuntu Box
---------------------------

.. code-block:: bash

    vagrant box add precise64 http://files.vagrantup.com/precise64.box

.. note:: This box is added at the global vagrant level. You only need to do it once, not once for each VM you may want to create.

Modify Vagrantfile
------------------

- Modify ./minion/Vagrantfile to use that box. Change the line to :

.. code-block:: yaml

    config.vm.box = "precise64"

- Uncomment the line creating a host-only ip : this is the ip of your minion (you can change it to something else if that ip is already used).

.. code-block:: yaml

    config.vm.network :private_network, ip: "192.168.33.10"


At that point you should have a VM that can run, although without much in it. Let's check that :

Checking the VM
----------------

From the $home/minion folder type

.. code-block:: bash

    vagrant up

=> you should have a log showing the VM booting. Once it's done you'll be back to the terminal.

.. code-block:: bash

    ping 192.168.33.10

=> The VM should be answering.

Now log inside the VM in ssh using vagrant again :

.. code-block:: bash

    vagrant ssh

=> You should see the shell prompt changing to something like "vagrant@precise64:~$" meaning you're inside the VM.
From there, type

.. code-block::

    ping 10.0.2.2

=> That ip is the ip of your VM host (the Mac OS X OS). The number is a virtualBox default and is displayed in the log after the vagrant ssh command. We'll use that IP to tell the minion where the salt master is. Once you're done, end the ssh session typing "exit".

It's now time to connect the VM to the salt master

STEP 3 : Connecting master and minion
=========================================================================

Creating minion.conf
--------------------
Create a "minion.conf" file in the minion directory. In that file, put those three lines, giving the id for this minion, and the ip of the master :

.. code-block::

    master: 10.0.2.2
    id: 'minion1'
    file_client: remote

Minions authenticate themselves to the master using keys. Keys are generated automatically if you don't provide one, and you can accept them later on. But this requires you to accept the minion key every time you destroy and recreate a minion (which could be quite often). A better way is to create those keys in advance, feed them to the minion, and autorise them once for all. To do that : 

Preseed minion keys
-------------------
From the minion folder run

.. code-block:: bash

    sudo salt-key --gen-keys=minion1

This should create two files : minion1.pem and minion1.pub 
Since those files have been created by sudo, but will be used by vagrant, you need to change ownership :

.. code-block:: bash

    sudo chown youruser minion1.pem
    sudo chown youruser minion1.pub

Then copy the .pub file into the list of accepted minions :

.. code-block:: bash

    sudo cp minion1.pub /etc/salt/pki/master/minions/minion1


Modify Vagrantfile to use salt provisionner
-------------------------------------------
Let's now modify the Vagrantfile to provision the VM using salt.
Add the following section in the Vagrantfile (note : it should be as the same indentation level as the other properties):

.. code-block:: yaml

    # salt-vagrant config
    config.vm.provision :salt do |salt|
        salt.run_highstate = true
        salt.minion_config = "./minion.conf"
        salt.minion_key = "./minion1.pem"
        salt.minion_pub = "./minion1.pub"
    end


Now destroy the vm and recreate it, from the /minion folder.

.. code-block:: bash

    vagrant destroy
    vagrant up

If everything is fine, you should see a message at some point saying

.. code-block:: bash

    "Bootstrapping Salt... (this may take a while)
    Salt successfully configured and installed!"

Checking master-minion communication
------------------------------------
To make sure master and minion are talking to each other, type this command

.. code-block:: bash

    sudo salt '*' test.ping

=>You should see your minion answering the ping.

It's now time to do some configuration

STEP 4 : Configure services to install on the minion
=========================================================================

In the step we'll use salt-master to instruct our minion to install nginx.

Checking original state
-----------------------
First, make sure no http server is installed in our minion.
Open a browser at http://192.168.33.10/
=> Can not reach site.

Initialize top.sls file
-----------------------
Service configuration is done in the /srv/salt/top.sls file (and subfiles/folder), and then running the state.highstate command to have salt-master give orders to minions to update their states.

First Create an empty file.

.. code-block:: bash

    touch /srv/salt/top.sls

When the file is empty, or if no configuration is found for our minion, an error message happen :

.. code-block:: bash

    sudo salt 'minion1' state.highstate

    Should get you a "No Top file or external nodes data matches found" error

Create nginx configuration
--------------------------
Now is finally the time to enter the real meat of our servers configuration. We'll suppose our minion is an web server that should have nginx installed.

Insert the following lines to our **top.sls** file (which should have nothing else).

.. code-block:: yaml

    base:
      'minion1':
        - bin.nginx

also create a **/srv/salt/bin/nginx.sls** file containing the following :

.. code-block:: yaml

    nginx:
      pkg.installed:
        - name: nginx
      service.running:
        - enable: True
        - reload: True

Check minion state
------------------
Finally launch the state.highstate command again :

.. code-block:: bash

    sudo salt 'minion1' state.highstate

=>You should see a log showing that the nginx package has been installed and the service configured.
To prove it, open your browser at http://192.168.33.10/ and see the Welcome to nginx message.

Congratulations !

STEP 5  where to go from there ?
=========================================================================
A full description of configuration management (tls files among other things) is here : http://docs.saltstack.com/index.html#configuration-management

Enjoy !


