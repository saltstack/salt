# -*- coding: utf-8 -*-
'''
Proxy Minion interface module for managing VMWare ESXi hosts.

.. versionadded:: 2015.8.4

**Special Note: SaltStack thanks** `Adobe Corporation <http://adobe.com/>`_
**for their support in creating this Proxy Minion integration.**

This proxy minion enables VMware ESXi (hereafter referred to as simply 'ESXi')
hosts to be treated individually like a Salt Minion.

Since the ESXi host may not necessarily run on an OS capable of hosting a
Python stack, the ESXi host can't run a Salt Minion directly. Salt's
"Proxy Minion" functionality enables you to designate another machine to host
a minion process that "proxies" communication from the Salt Master. The master
does not know nor care that the target is not a "real" Salt Minion.

More in-depth conceptual reading on Proxy Minions can be found in the
:doc:`Proxy Minion </topics/proxyminion/index>` section of Salt's
documentation.


Dependencies
============

- pyVmomi Python Module
- ESXCLI


pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.

ESXCLI
------

Currently, about a third of the functions used in the vSphere Execution Module require
the ESXCLI package be installed on the machine running the Proxy Minion process.

The ESXCLI package is also referred to as the VMware vSphere CLI, or vCLI. VMware
provides vCLI package installation instructions for `vSphere 5.5`_ and
`vSphere 6.0`_.

.. _vSphere 5.5: http://pubs.vmware.com/vsphere-55/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html
.. _vSphere 6.0: http://pubs.vmware.com/vsphere-60/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html

Once all of the required dependencies are in place and the vCLI package is
installed, you can check to see if you can connect to your ESXi host or vCenter
server by running the following command:

.. code-block:: bash

    esxcli -s <host-location> -u <username> -p <password> system syslog config get

If the connection was successful, ESXCLI was successfully installed on your system.
You should see output related to the ESXi host's syslog configuration.


Configuration
=============
To use this integration proxy module, please configure the following:

Pillar
------

Proxy minions get their configuration from Salt's Pillar. Every proxy must
have a stanza in Pillar and a reference in the Pillar top-file that matches
the ID. At a minimum for communication with the ESXi host, the pillar should
look like this:

.. code-block:: yaml

    proxy:
      proxytype: esxi
      host: <ip or dns name of esxi host>
      username: <ESXi username>
      passwords:
        - first_password
        - second_password
        - third_password

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

This also allows you to use any number of potential fallback passwords.

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
alternate protocol. Default is ``https``.

port
^^^^
If the ESXi host is not using the default port, set this value to an
alternate port. Default is ``443``.


Salt Proxy
----------

After your pillar is in place, you can test the proxy. The proxy can run on
any machine that has network connectivity to your Salt Master and to the
ESXi host in question. SaltStack recommends that the machine running the
salt-proxy process also run a regular minion, though it is not strictly
necessary.

On the machine that will run the proxy, make sure there is an ``/etc/salt/proxy``
file with at least the following in it:

.. code-block:: yaml

    master: <ip or hostname of salt-master>

You can then start the salt-proxy process with:

.. code-block:: bash

    salt-proxy --proxyid <id you want to give the host>

You may want to add ``-l debug`` to run the above in the foreground in
debug mode just to make sure everything is OK.

Next, accept the key for the proxy on your salt-master, just like you
would for a regular minion:

.. code-block:: bash

    salt-key -a <id you gave the esxi host>

You can confirm that the pillar data is in place for the proxy:

.. code-block:: bash

    salt <id> pillar.items

And now you should be able to ping the ESXi host to make sure it is
responding:

.. code-block:: bash

    salt <id> test.ping

At this point you can execute one-off commands against the host. For
example, you can get the ESXi host's system information:

.. code-block:: bash

    salt <id> esxi.cmd system_info

Note that you don't need to provide credentials or an ip/hostname. Salt
knows to use the credentials you stored in Pillar.

It's important to understand how this particular proxy works.
:doc:`Salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>` is a
standard Salt execution module. If you pull up the docs for it you'll see
that almost every function in the module takes credentials and a target
host. When credentials and a host aren't passed, Salt runs commands
through ``pyVmomi`` against the local machine. If you wanted, you could run
functions from this module on any host where an appropriate version of
``pyVmomi`` is installed, and that host would reach out over the network
and communicate with the ESXi host.

``esxi.cmd`` acts as a "shim" between the execution module and the proxy. Its
first parameter is always the function from salt.modules.vsphere. If the
function takes more positional or keyword arguments you can append them to the
call. It's this shim that speaks to the ESXi host through the proxy, arranging
for the credentials and hostname to be pulled from the Pillar section for this
Proxy Minion.

Because of the presence of the shim, to lookup documentation for what
functions you can use to interface with the ESXi host, you'll want to
look in :doc:`salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>`
instead of :doc:`salt.modules.esxi </ref/modules/all/salt.modules.esxi>`.


States
------

Associated states are thoroughly documented in
:doc:`salt.states.esxi </ref/states/all/salt.states.esxi>`. Look there
to find an example structure for Pillar as well as an example ``.sls`` file
for standing up an ESXi host from scratch.

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import SaltSystemExit

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ['esxi']


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {}

# Set up logging
log = logging.getLogger(__file__)

# Define the module's virtual name
__virtualname__ = 'esxi'


def __virtual__():
    '''
    Only load if the ESXi execution module is available.
    '''
    if 'vsphere.system_info' in __salt__:
        return __virtualname__

    return False, 'The ESXi Proxy Minion module did not load.'


def init(opts):
    '''
    This function gets called when the proxy starts up. For
    ESXi devices, the host, login credentials, and, if configured,
    the protocol and port are cached.
    '''
    if 'host' not in opts['proxy']:
        log.critical('No \'host\' key found in pillar for this proxy.')
        return False
    if 'username' not in opts['proxy']:
        log.critical('No \'username\' key found in pillar for this proxy.')
        return False
    if 'passwords' not in opts['proxy']:
        log.critical('No \'passwords\' key found in pillar for this proxy.')
        return False

    host = opts['proxy']['host']

    # Get the correct login details
    try:
        username, password = find_credentials(host)
    except SaltSystemExit as err:
        log.critical('Error: {0}'.format(err))
        return False

    # Set configuration details
    DETAILS['host'] = host
    DETAILS['username'] = username
    DETAILS['password'] = password
    DETAILS['protocol'] = opts['proxy'].get('protocol')
    DETAILS['port'] = opts['proxy'].get('port')


def grains():
    '''
    Get the grains from the proxy device.
    '''
    if not GRAINS_CACHE:
        return _grains(DETAILS['host'],
                       DETAILS['protocol'],
                       DETAILS['port'])
    return GRAINS_CACHE


def grains_refresh():
    '''
    Refresh the grains from the proxy device.
    '''
    GRAINS_CACHE = {}
    return grains()


def ping():
    '''
    Check to see if the host is responding. Returns False if the host didn't
    respond, True otherwise.

    CLI Example:

    .. code-block:: bash

        salt esxi-host test.ping
    '''
    find_credentials(DETAILS['host'])
    try:
        __salt__['vsphere.system_info'](host=DETAILS['host'],
                                        username=DETAILS['username'],
                                        password=DETAILS['password'])
    except SaltSystemExit as err:
        log.warning(err)
        return False

    return True


def shutdown():
    '''
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    '''
    log.debug('ESXi proxy shutdown() called...')


def ch_config(cmd, *args, **kwargs):
    '''
    This function is called by the
    :doc:`salt.modules.esxi.cmd </ref/modules/all/salt.modules.esxi>` shim.
    It then calls whatever is passed in ``cmd`` inside the
    :doc:`salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>` module.
    Passes the return through from the vsphere module.

    cmd
        The command to call inside salt.modules.vsphere

    args
        Arguments that need to be passed to that command.

    kwargs
        Keyword arguments that need to be passed to that command.

    '''
    # Strip the __pub_ keys...is there a better way to do this?
    for k in kwargs.keys():
        if k.startswith('__pub_'):
            kwargs.pop(k)

    if 'vsphere.' + cmd not in __salt__:
        return {'retcode': -1, 'message': 'vsphere.' + cmd + ' is not available.'}
    else:
        return __salt__['vsphere.' + cmd](*args, **kwargs)


def find_credentials(host):
    '''
    Cycle through all the possible credentials and return the first one that
    works.
    '''
    user_names = [__pillar__['proxy'].get('username', 'root')]
    passwords = __pillar__['proxy']['passwords']
    for user in user_names:
        for password in passwords:
            try:
                # Try to authenticate with the given user/password combination
                ret = __salt__['vsphere.system_info'](host=host,
                                                      username=user,
                                                      password=password)
            except SaltSystemExit:
                # If we can't authenticate, continue on to try the next password.
                continue
            # If we have data returned from above, we've successfully authenticated.
            if ret:
                DETAILS['username'] = user
                DETAILS['password'] = password
                return user, password
    # We've reached the end of the list without successfully authenticating.
    raise SaltSystemExit('Cannot complete login due to an incorrect user name or password.')


def _grains(host, protocol=None, port=None):
    '''
    Helper function to the grains from the proxied device.
    '''
    username, password = find_credentials(DETAILS['host'])
    ret = __salt__['vsphere.system_info'](host=host,
                                          username=username,
                                          password=password,
                                          protocol=protocol,
                                          port=port)
    GRAINS_CACHE.update(ret)
    return GRAINS_CACHE
