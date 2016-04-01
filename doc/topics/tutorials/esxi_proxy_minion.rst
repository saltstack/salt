.. _tutorial-esxi-proxy:

=================
ESXi Proxy Minion
=================

.. versionadded:: 2015.8.4

.. note::

    This tutorial assumes basic knowledge of Salt. To get up to speed, check
    out the :doc:`Salt Walkthrough </topics/tutorials/walkthrough>`.

    This tutorial also assumes a basic understanding of Salt Proxy Minions. If
    you're unfamiliar with Salt's Proxy Minion system, please read the
    :doc:`Salt Proxy Minion </topics/proxyminion/index>` documentation and the
    :doc:`Salt Proxy Minion End-to-End Example </topics/proxyminion/demo>`
    tutorial.

    The third assumption that this tutorial makes is that you also have a
    basic understanding of ESXi hosts. You can learn more about ESXi hosts on
    `VMware's various resources`_.

.. _VMware's various resources: https://www.vmware.com/products/esxi-and-esx/overview

Salt's ESXi Proxy Minion allows a VMware ESXi host to be treated as an individual
Salt Minion, without installing a Salt Minion on the ESXi host.

Since an ESXi host may not necessarily run on an OS capable of hosting a Python
stack, the ESXi host can't run a regular Salt Minion directly. Therefore, Salt's
Proxy Minion functionality enables you to designate another machine to host a
proxy process that "proxies" communication from the Salt Master to the ESXi host.
The master does not know or care that the ESXi target is not a "real" Salt Minion.

More in-depth conceptual reading on Proxy Minions can be found in the
:doc:`Proxy Minion </topics/proxyminion/index>` section of Salt's documentation.

Salt's ESXi Proxy Minion was added in the 2015.8.4 release of Salt.

.. note::

    Be aware that some functionality for the ESXi Proxy Minion may depend on the
    type of license attached the ESXi host(s).

    For example, certain services are only available to manipulate service state
    or policies with a VMware vSphere Enterprise or Enterprise Plus license, while
    others are available with a Standard license. The ``ntpd`` service is restricted
    to an Enterprise Plus license, while ``ssh`` is available via the Standard
    license.

    Please see the `vSphere Comparison`_ page for more information.

.. _vSphere Comparison: https://www.vmware.com/products/vsphere/compare


Dependencies
============

Manipulation of the ESXi host via a Proxy Minion requires the machine running
the Proxy Minion process to have the ESXCLI package (and all of it's dependencies)
and the pyVmomi Python Library to be installed.

ESXi Password
-------------

The ESXi Proxy Minion uses VMware's API to perform tasks on the host as if it was
a regular Salt Minion. In order to access the API that is already running on the
ESXi host, the ESXi host must have a username and password that is used to log
into the host. The username is usually ``root``. Before Salt can access the ESXi
host via VMware's API, a default password *must* be set on the host.

pyVmomi
-------

The pyVmomi Python library must be installed on the machine that is running the
proxy process. pyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, the machine that you
    are running the proxy minion process from must have either Python 2.6,
    Python 2.7.9, or newer. This is due to an upstream dependency in pyVmomi 6.0
    that is not supported in Python version 2.7 to 2.7.8. If the
    version of Python running the proxy process is not in the supported range, you
    will need to install an earlier version of pyVmomi. See `Issue #29537`_ for
    more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that the original ESXi Proxy Minion
was developed against.

ESXCLI
------

Currently, about a third of the functions used for the ESXi Proxy Minion require
the ESXCLI package be installed on the machine running the Proxy Minion process.

The ESXCLI package is also referred to as the VMware vSphere CLI, or vCLI. VMware
provides vCLI package installation instructions for `vSphere 5.5`_ and
`vSphere 6.0`_.

.. _vSphere 5.5: http://pubs.vmware.com/vsphere-55/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html
.. _vSphere 6.0: http://pubs.vmware.com/vsphere-60/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html

Once all of the required dependencies are in place and the vCLI package is
installed, you can check to see if you can connect to your ESXi host by running
the following command:

.. code-block:: bash

    esxcli -s <host-location> -u <username> -p <password> system syslog config get

If the connection was successful, ESXCLI was successfully installed on your system.
You should see output related to the ESXi host's syslog configuration.


Configuration
=============

There are several places where various configuration values need to be set in
order for the ESXi Proxy Minion to run and connect properly.

Proxy Config File
-----------------

On the machine that will be running the Proxy Minon process(es), a proxy config
file must be in place. This file should be located in the ``/etc/salt/`` directory
and should be named ``proxy``. If the file is not there by default, create it.

This file should contain the location of your Salt Master that the Salt Proxy
will connect to.

.. note::

    If you're running your ESXi Proxy Minion on version of Salt that is 2015.8.4
    or newer, you also need to set ``add_proxymodule_to_opts: False`` in your
    proxy config file. The need to specify this configuration will be removed with
    Salt ``Boron``, the next major feature release. See the `New in 2015.8.2`_
    section of the Proxy Minion documentation for more information.

.. _New in 2015.8.2: https://docs.saltstack.com/en/latest/topics/proxyminion/index.html#new-in-2015-8-2


Example Proxy Config File:

.. code-block:: yaml

    # /etc/salt/proxy

    master: <salt-master-location>
    add_proxymodule_to_opts: False


Pillar Profiles
---------------

Proxy minions get their configuration from Salt's Pillar. Every proxy must
have a stanza in Pillar and a reference in the Pillar top-file that matches
the Proxy ID. At a minimum for communication with the ESXi host, the pillar
should look like this:

.. code-block:: yaml

    proxy:
      proxytype: esxi
      host: <ip or dns name of esxi host>
      username: <ESXi username>
      passwords:
        - first_password
        - second_password
        - third_password

Some other optional settings are ``protocol`` and ``port``. These can be added
to the pillar configuration.

proxytype
^^^^^^^^^
The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this ESXi Proxy Module, set this to
``esxi``.

host
^^^^
The location, or ip/dns, of the ESXi host. Required.

username
^^^^^^^^
The username used to login to the ESXi host, such as ``root``. Required.

passwords
^^^^^^^^^
A list of passwords to be used to try and login to the ESXi host. At least
one password in this list is required.

The proxy integration will try the passwords listed in order. It is
configured this way so you can have a regular password and the password you
may be updating for an ESXi host either via the
:doc:`vsphere.update_host_password </ref/modules/all/salt.modules.vsphere>`
execution module function or via the
:doc:`esxi.password_present </ref/modules/all/salt.states.esxi>` state
function. This way, after the password is changed, you should not need to
restart the proxy minion--it should just pick up the the new password
provided in the list. You can then change pillar at will to move that
password to the front and retire the unused ones.

Use-case/reasoning for using a list of passwords: You are setting up an
ESXi host for the first time, and the host comes with a default password.
You know that you'll be changing this password during your initial setup
from the default to a new password. If you only have one password option,
and if you have a state changing the password, any remote execution commands
or states that run after the password change will not be able to run on the
host until the password is updated in Pillar and the Proxy Minion process is
restarted.

This allows you to use any number of potential fallback passwords.

.. note::

    When a password is changed on the host to one in the list of possible
    passwords, the further down on the list the password is, the longer
    individual commands will take to return. This is due to the nature of
    pyVmomi's login system. We have to wait for the first attempt to fail
    before trying the next password on the list.

    This scenario is especially true, and even slower, when the proxy
    minion first starts. If the correct password is not the first password
    on the list, it may take up to a minute for ``test.ping`` to respond
    with a ``True`` result. Once the initial authorization is complete, the
    responses for commands will be a little faster.

    To avoid these longer waiting periods, SaltStack recommends moving the
    correct password to the top of the list and restarting the proxy minion
    at your earliest convenience.

protocol
^^^^^^^^
If the ESXi host is not using the default protocol, set this value to an
alternate protocol. Default is ``https``. For example:

port
^^^^
If the ESXi host is not using the default port, set this value to an
alternate port. Default is ``443``.

Example Configuration Files
---------------------------

An example of all of the basic configurations that need to be in place before
starting the Proxy Minion processes includes the Proxy Config File, Pillar
Top File, and any individual Proxy Minion Pillar files.

In this example, we'll assuming there are two ESXi hosts to connect to. Therefore,
we'll be creating two Proxy Minion config files, one config for each ESXi host.

Proxy Config File:

.. code-block:: yaml

    # /etc/salt/proxy

    master: <salt-master-location>
    add_proxymodule_to_opts: False

Pillar Top File:

.. code-block:: yaml

    # /srv/pillar/top.sls

    base:
      'esxi-1':
        - esxi-1
      'esxi-2':
        - esxi-2

Pillar Config File for the first ESXi host, esxi-1:

.. code-block:: yaml

    # /srv/pillar/esxi-1.sls

    proxy:
      proxytype: esxi
      host: esxi-1.example.com
      username: 'root'
      passwords:
        - bad-password-1
        - backup-bad-password-1

Pillar Config File for the second ESXi host, esxi-2:

.. code-block:: yaml

    # /srv/pillar/esxi-2.sls

    proxy:
      proxytype: esxi
      host: esxi-2.example.com
      username: 'root'
      passwords:
        - bad-password-2
        - backup-bad-password-2


Starting the Proxy Minion
=========================

Once all of the correct configuration files are in place, it is time to start the
proxy processes!

#. First, make sure your Salt Master is running.
#. Start the first Salt Proxy, in debug mode, by giving the Proxy Minion process
   and ID that matches the config file name created in the `Configuration`_ section.

.. code-block:: bash

    salt-proxy --proxyid='esxi-1' -l debug

#. Accept the ``esxi-1`` Proxy Minion's key on the Salt Master:

.. code-block:: bash

    # salt-key -L
    Accepted Keys:
    Denied Keys:
    Unaccepted Keys:
    esxi-1
    Rejected Keys:
    #
    # salt-key -a esxi-1
    The following keys are going to be accepted:
    Unaccepted Keys:
    esxi-1
    Proceed? [n/Y] y
    Key for minion esxi-1 accepted.

#. Repeat for the second Salt Proxy, this time we'll run the proxy process as a
   daemon, as an example.

.. code-block:: bash

    salt-proxy --proxyid='esxi-2' -d

#. Accept the ``esxi-2`` Proxy Minion's key on the Salt Master:

.. code-block:: bash

    # salt-key -L
    Accepted Keys:
    esxi-1
    Denied Keys:
    Unaccepted Keys:
    esxi-2
    Rejected Keys:
    #
    # salt-key -a esxi-1
    The following keys are going to be accepted:
    Unaccepted Keys:
    esxi-2
    Proceed? [n/Y] y
    Key for minion esxi-1 accepted.

#. Check and see if your Proxy Minions are responding:

.. code-block:: bash

    # salt 'esxi-*' test.ping
    esxi-1:
        True
    esxi-3:
        True


Executing Commands
==================

Now that you've configured your Proxy Minions and have them responding successfully
to a ``test.ping``, we can start executing commands against the ESXi hosts via Salt.

It's important to understand how this particular proxy works, and there are a couple
of important pieces to be aware of in order to start running remote execution and
state commands against the ESXi host via a Proxy Minion: the
`vSphere Execution Module`_, the `ESXi Execution Module`_, and the `ESXi State Module`_.


vSphere Execution Module
------------------------

The :doc:`Salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>` is a
standard Salt execution module that does the bulk of the work for the ESXi Proxy
Minion. If you pull up the docs for it you'll see that almost every function in
the module takes credentials (``username`` and ``password``) and a target ``host``
argument. When credentials and a host aren't passed, Salt runs commands
through ``pyVmomi`` or ``ESXCLI`` against the local machine. If you wanted,
you could run functions from this module on any machine where an appropriate
version of ``pyVmomi`` and ``ESXCLI`` are installed, and that machine would reach
out over the network and communicate with the ESXi host.

You'll notice that most of the functions in the vSphere module require a ``host``,
``username``, and ``password``. These parameters are contained in the Pillar files and
passed through to the function via the proxy process that is already running. You don't
need to provide these parameters when you execute the commands. See the
`Running Remote Execution Commands`_ section below for an example.


ESXi Execution Module
---------------------

In order for the Pillar information set up in the `Configuration`_ section above to
be passed to the function call in the vSphere Execution Module, the
:doc:`salt.modules.esxi </ref/modules/all/salt.modules.esxi>` execution module acts
as a "shim" between the vSphere execution module functions and the proxy process.

The "shim" takes the authentication credentials specified in the Pillar files and
passes them through to the ``host``, ``username``, ``password``, and optional
``protocol`` and ``port`` options required by the vSphere Execution Module functions.

If the function takes more positional, or keyword, arguments you can append them
to the call. It's this shim that speaks to the ESXi host through the proxy, arranging
for the credentials and hostname to be pulled from the Pillar section for the ESXi
Proxy Minion.

Because of the presence of the shim, to lookup documentation for what
functions you can use to interface with the ESXi host, you'll want to
look in :doc:`salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>`
instead of :doc:`salt.modules.esxi </ref/modules/all/salt.modules.esxi>`.


Running Remote Execution Commands
---------------------------------

To run commands from the Salt Master to execute, via the ESXi Proxy Minion, against
the ESXi host, you use the ``esxi.cmd <vsphere-function-name>`` syntax to call
functions located in the vSphere Execution Module. Both args and kwargs needed
for various vsphere execution module functions must be passed through in a kwarg-
type manor. For example:

.. code-block:: bash

    salt 'esxi-*' esxi.cmd system_info
    salt 'exsi-*' esxi.cmd get_service_running service_name='ssh'


ESXi State Module
-----------------

The ESXi State Module functions similarly to other state modules. The "shim" provided
by the `ESXi Execution Module`_ passes the necessary ``host``, ``username``, and
``password`` credentials through, so those options don't need to be provided in the
state. Other than that, state files are written and executed just like any other
Salt state. See the :doc:`salt.modules.esxi </ref/states/all/salt.states.esxi>` state
for ESXi state functions.

The follow state file is an example of how to configure various pieces of an ESXi host
including enabling SSH, uploading and SSH key, configuring a coredump network config,
syslog, ntp, enabling VMotion, resetting a host password, and more.

.. code-block:: yaml

    # /srv/salt/configure-esxi.sls

    configure-host-ssh:
      esxi.ssh_configured:
        - service_running: True
        - ssh_key_file: /etc/salt/ssh_keys/my_key.pub
        - service_policy: 'automatic'
        - service_restart: True
        - certificate_verify: True

    configure-host-coredump:
      esxi.coredump_configured:
        - enabled: True
        - dump_ip: 'my-coredump-ip.example.com'

    configure-host-syslog:
      esxi.syslog_configured:
        - syslog_configs:
            loghost: ssl://localhost:5432,tcp://10.1.0.1:1514
            default-timeout: 120
        - firewall: True
        - reset_service: True
        - reset_syslog_config: True
        - reset_configs: loghost,default-timeout

    configure-host-ntp:
      esxi.ntp_configured:
        - service_running: True
        - ntp_servers:
          - 192.174.1.100
          - 192.174.1.200
        - service_policy: 'automatic'
        - service_restart: True

    configure-vmotion:
      esxi.vmotion_configured:
        - enabled: True

    configure-host-vsan:
      esxi.vsan_configured:
        - enabled: True
        - add_disks_to_vsan: True

    configure-host-password:
      esxi.password_present:
        - password: 'new-bad-password'

States are called via the ESXi Proxy Minion just as they would on a regular minion.
For example:

.. code-block:: bash

    salt 'esxi-*' state.sls configure-esxi test=true
    salt 'esxi-*' state.sls configure-esxi


Relevant Salt Files and Resources
=================================

- :mod:`ESXi Proxy Minion <salt.proxy.esxi>`
- :mod:`ESXi Execution Module <salt.modules.esxi>`
- :mod:`ESXi State Module <salt.states.esxi>`
- :doc:`Salt Proxy Minion Docs </topics/proxyminion/index>`
- :doc:`Salt Proxy Minion End-to-End Example </topics/proxyminion/demo>`
- :mod:`vSphere Execution Module <salt.modules.vsphere>`

