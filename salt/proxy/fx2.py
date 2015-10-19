# -*- coding: utf-8 -*-
'''
======
fx2.py
======

.. versionadded:: 2015.8.2

Proxy minion interface module for managing Dell FX2 chassis (Dell
Chassis Management Controller version 1.2 and above, iDRAC8 version 2.00
and above)

Dependencies
------------

- :doc:`iDRAC Remote execution module (salt.modules.dracr) </ref/modules/all/salt.modules.dracr>`
- :doc:`Chassis command shim (salt.modules.chassis) </ref/modules/all/salt.modules.chassis>`
- :doc:`Dell Chassis States (salt.states.dellchassis) </ref/states/all/salt.states.dellchassis>`
- Dell's ``racadm`` command line interface to CMC and iDRAC devices.


**Special Note: SaltStack thanks** `Adobe Corporation <http://adobe.com/>`_
**for their support in creating this proxy minion integration.**

This proxy minion enables Dell FX2 and FX2s (hereafter referred to as
simply "chassis", "CMC", or "FX2") chassis to be treated individually
like a salt-minion.

Since the CMC embedded in the chassis does not run an OS capable of hosting a
Python stack, the chassis can't run a minion directly.  Salt's "Proxy Minion"
functionality enables you to designate another machine to host a minion
process that "proxies" communication from the salt-master.  The master does not
know nor care that the target is not a real minion.

More in-depth conceptual reading on Proxy Minions can be found
:doc:`in the Proxy Minion section </topics/proxyminion/index>` of
Salt's documentation.

To configure this integration, follow these steps:

Pillar
------

Proxy minions get their configuration from Salt's Pillar.  Every proxy must
have a stanza in Pillar, and a reference in the Pillar topfile that matches
the ID.  At a minimum for communication with the chassis the pillar should
look like this:

.. code-block:: yaml

    proxy:
      host: <ip or dns name of chassis controller>
      admin_username: <iDRAC username for the CMC, usually 'root'>
      admin_password: <iDRAC password.  Dell default is 'calvin'>
      proxytype: fx2

The ``proxytype`` line above is critical, it tells Salt which interface to load
from the ``proxy`` directory in Salt's install hierarchy, or from ``/srv/salt/_proxy``
on the salt-master (if you have created your own proxy module, for example).

salt-proxy
----------

After your pillar is in place, you can test the proxy.  The proxy can run on
any machine that has network connectivity to your salt-master and to the chassis in question.
SaltStack recommends that this machine also run a regular minion, though
it is not strictly necessary.

On the machine that will run the proxy, make sure there is an ``/etc/salt/proxy``
file with at least the following in it:

.. code-block:: yaml

    master: <ip or hostname of salt-master>

You can start the proxy with

.. code-block:: bash

    salt-proxy --proxyid <id you want to give the chassis>

You may want to add ``-l debug`` to run the above in the foreground in debug
mode just to make sure everything is OK.

Next, accept the key for the proxy on your salt-master, just like you would
for a regular minion:

.. code-block:: bash

    salt-key -a <id you want to give the chassis>

You can confirm that the pillar data is in place for the proxy:

.. code-block:: bash

    salt <id> pillar.items

And now you should be able to ping the chassis to make sure it is responding:

.. code-block:: bash

    salt <id> test.ping

At this point you can execute one-off commands against the chassis.  For
example, you can get the chassis inventory:

.. code-block:: bash

    salt <id> chassis.cmd inventory

Note that you don't need to provide credentials or an ip/hostname.  Salt knows
to use the credentials you stored in Pillar.

It's important to understand how this particular proxy works.
:doc:`Salt.modules.dracr </ref/modules/all/salt.modules.dracr>` is a standard Salt execution
module.  If you pull up the docs for it you'll see that almost every function
in the module takes credentials and a target host.  When credentials and a host
aren't passed, Salt runs ``racadm`` against the local machine.  If you wanted
you could run functions from this module on any host where an appropriate
version of ``racadm`` is installed, and that host would reach out over the network
and communicate with the chassis.

``Chassis.cmd`` acts as a "shim" between the execution module and the proxy.  It's
first parameter is always the function from salt.modules.dracr to execute.  If the
function takes more positional or keyword arguments you can append them to the call.
It's this shim that speaks to the chassis through the proxy, arranging for the
credentials and hostname to be pulled from the pillar section for this proxy minion.

Because of the presence of the shim, to lookup documentation for what
functions you can use to interface with the chassis, you'll want to
look in :doc:`salt.modules.dracr </ref/modules/all/salt.modules.dracr>` instead
of :doc:`salt.modules.chassis </ref/modules/all/salt.modules.chassis>`.

States
------

Associated states are thoroughly documented in :doc:`salt.states.dellchassis </ref/states/all/salt.states.dellchassis>`.
Look there to find an example structure for pillar as well as an example
``.sls`` file for standing up a Dell Chassis from scratch.

'''
from __future__ import absolute_import

# Import python libs
import logging
import salt.utils
import salt.utils.http

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ['fx2']


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {}

# Want logging!
log = logging.getLogger(__file__)


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not salt.utils.which('racadm'):
        log.critical('fx2 proxy minion needs "racadm" to be installed.')
        return False

    return True


def init(opts):
    '''
    This function gets called when the proxy starts up.  For
    FX2 devices we just cache the credentials and hostname.
    '''
    # Save the login details
    DETAILS['admin_username'] = opts['proxy']['admin_username']
    DETAILS['admin_password'] = opts['proxy']['admin_password']
    DETAILS['host'] = opts['proxy']['host']


def grains():
    '''
    Get the grains from the proxied device
    '''
    if not GRAINS_CACHE:
        r = __salt__['dracr.system_info'](host=DETAILS['host'],
                                          admin_username=DETAILS['admin_username'],
                                          admin_password=DETAILS['admin_password'])
        GRAINS_CACHE = r
    return GRAINS_CACHE


def grains_refresh():
    '''
    Refresh the grains from the proxied device
    '''
    GRAINS_CACHE = {}
    return grains()


def chconfig(cmd, *args, **kwargs):
    '''
    This function is called by the :doc:`salt.modules.chassis.cmd </ref/modules/all/salt.modules.chassis>`
    shim.  It then calls whatever is passed in ``cmd``
    inside the :doc:`salt.modules.dracr </ref/modules/all/salt.modules.dracr>`
    module.

    :param cmd: The command to call inside salt.modules.dracr
    :param args: Arguments that need to be passed to that command
    :param kwargs: Keyword arguments that need to be passed to that command
    :return: Passthrough the return from the dracr module.

    '''
    # Strip the __pub_ keys...is there a better way to do this?
    for k in kwargs.keys():
        if k.startswith('__pub_'):
            kwargs.pop(k)
    if 'dracr.'+cmd not in __salt__:
        return {'retcode': -1, 'message': 'dracr.' + cmd + ' is not available'}
    else:
        return __salt__['dracr.'+cmd](*args, **kwargs)


def ping():
    '''
    Is the chassis responding?

    :return: Returns False if the chassis didn't respond, True otherwise.

    '''
    r = __salt__['dracr.system_info'](host=DETAILS['host'],
                                      admin_username=DETAILS['admin_username'],
                                      admin_password=DETAILS['admin_password'])
    if r.get('retcode', 0) == 1:
        return False
    else:
        return True
    try:
        return r['dict'].get('ret', False)
    except Exception:
        return False


def shutdown(opts):
    '''
    Shutdown the connection to the proxied device.
    For this proxy shutdown is a no-op.
    '''
    log.debug('fx2 proxy shutdown() called...')
