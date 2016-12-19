# -*- coding: utf-8 -*-,
'''
Dell FX2 chassis
================

.. versionadded:: 2015.8.2

Proxy minion interface module for managing Dell FX2 chassis (Dell
Chassis Management Controller version 1.2 and above, iDRAC8 version 2.00
and above)

Dependencies
------------

- :mod:`iDRAC Remote execution module (salt.modules.dracr) <salt.modules.dracr>`
- :mod:`Chassis command shim (salt.modules.chassis) <salt.modules.chassis>`
- :mod:`Dell Chassis States (salt.states.dellchassis) <salt.states.dellchassis>`
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
:ref:`in the Proxy Minion section <proxy-minion>` of
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
      fallback_admin_username: <username to try if the first fails>
      passwords:
        - first_password
        - second_password
        - third-password
      proxytype: fx2

The ``proxytype`` line above is critical, it tells Salt which interface to load
from the ``proxy`` directory in Salt's install hierarchy, or from ``/srv/salt/_proxy``
on the salt-master (if you have created your own proxy module, for example).

The proxy integration will try the passwords listed in order.  It is
configured this way so you can have a regular password, a potential
fallback password, and the third password can be the one you intend
to change the chassis to use.  This way, after it is changed, you
should not need to restart the proxy minion--it should just pick up the
third password in the list.  You can then change pillar at will to
move that password to the front and retire the unused ones.

Beware, many Dell CMC and iDRAC units are configured to lockout
IP addresses or users after too many failed password attempts.  This can
generate user panic in the form of "I no longer know what the password is!!!".
To mitigate panic try the web interface from a different IP, or setup a
emergency administrator user in the CMC before doing a wholesale
password rotation.

The automatic lockout can be disabled via Salt with the following:

.. code-block:: bash

    salt <cmc> chassis.cmd set_general cfgRacTuning cfgRacTuneIpBlkEnable 0

and then verified with

.. code-block:: bash

    salt <cmc> chassis.cmd get_general cfgRacTuning cfgRacTuneIpBlkEnable



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
:mod:`Salt.modules.dracr <salt.modules.dracr>` is a standard Salt execution
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
look in :mod:`salt.modules.dracr <salt.modules.dracr>` instead
of :mod:`salt.modules.chassis <salt.modules.chassis>`.

States
------

Associated states are thoroughly documented in :mod:`salt.states.dellchassis <salt.states.dellchassis>`.
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
    This function gets called when the proxy starts up.
    We check opts to see if a fallback user and password are supplied.
    If they are present, and the primary credentials don't work, then
    we try the backup before failing.

    Whichever set of credentials works is placed in the persistent
    DETAILS dictionary and will be used for further communication with the
    chassis.
    '''
    if 'host' not in opts['proxy']:
        log.critical('No "host" key found in pillar for this proxy')
        return False

    DETAILS['host'] = opts['proxy']['host']

    (username, password) = find_credentials()


def admin_username():
    '''
    Return the admin_username in the DETAILS dictionary, or root if there
    is none present
    '''
    return DETAILS.get('admin_username', 'root')


def admin_password():
    '''
    Return the admin_password in the DETAILS dictionary, or 'calvin'
    (the Dell default) if there is none present
    '''
    if 'admin_password' not in DETAILS:
        log.info('proxy.fx2: No admin_password in DETAILS, returning Dell default')
        return 'calvin'

    return DETAILS.get('admin_password', 'calvin')


def host():
    return DETAILS['host']


def _grains(host, user, password):
    '''
    Get the grains from the proxied device
    '''
    r = __salt__['dracr.system_info'](host=host,
                                      admin_username=user,
                                      admin_password=password)
    if r.get('retcode', 0) == 0:
        GRAINS_CACHE = r
    else:
        GRAINS_CACHE = {}
    return GRAINS_CACHE


def grains():
    '''
    Get the grains from the proxied device
    '''
    if not GRAINS_CACHE:
        return _grains(DETAILS['host'],
                       DETAILS['admin_username'],
                       DETAILS['admin_password'])

    return GRAINS_CACHE


def grains_refresh():
    '''
    Refresh the grains from the proxied device
    '''
    GRAINS_CACHE = {}
    return grains()


def find_credentials():
    '''
    Cycle through all the possible credentials and return the first one that
    works
    '''
    usernames = []
    usernames.append(__pillar__['proxy'].get('admin_username', 'root'))
    if 'fallback_admin_username' in __pillar__.get('proxy'):
        usernames.append(__pillar__['proxy'].get('fallback_admin_username'))

    for user in usernames:
        for pwd in __pillar__['proxy']['passwords']:
            r = __salt__['dracr.get_chassis_name'](host=__pillar__['proxy']['host'],
                                                   admin_username=user,
                                                   admin_password=pwd)
            # Retcode will be present if the chassis_name call failed
            try:
                if r.get('retcode', None) is None:
                    DETAILS['admin_username'] = user
                    DETAILS['admin_password'] = pwd
                    __opts__['proxy']['admin_username'] = user
                    __opts__['proxy']['admin_password'] = pwd
                    return (user, pwd)
            except AttributeError:
                # Then the above was a string, and we can return the username
                # and password
                DETAILS['admin_username'] = user
                DETAILS['admin_password'] = pwd
                __opts__['proxy']['admin_username'] = user
                __opts__['proxy']['admin_password'] = pwd
                return (user, pwd)

    log.debug('proxy fx2.find_credentials found no valid credentials, using Dell default')
    return ('root', 'calvin')


def chconfig(cmd, *args, **kwargs):
    '''
    This function is called by the :mod:`salt.modules.chassis.cmd <salt.modules.chassis.cmd>`
    shim.  It then calls whatever is passed in ``cmd``
    inside the :mod:`salt.modules.dracr <salt.modules.dracr>`
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

    # Catch password reset
    if 'dracr.'+cmd not in __salt__:
        ret = {'retcode': -1, 'message': 'dracr.' + cmd + ' is not available'}
    else:
        ret = __salt__['dracr.'+cmd](*args, **kwargs)

    if cmd == 'change_password':
        if 'username' in kwargs:
            __opts__['proxy']['admin_username'] = kwargs['username']
            DETAILS['admin_username'] = kwargs['username']
        if 'password' in kwargs:
            __opts__['proxy']['admin_password'] = kwargs['password']
            DETAILS['admin_password'] = kwargs['password']

    return ret


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
