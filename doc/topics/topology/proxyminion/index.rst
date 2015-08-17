===============================
Salt Proxy Minion Documentation
===============================

Proxy minions are a developing Salt feature that enables controlling devices
that, for whatever reason, cannot run a standard salt-minion.  Examples include
network gear that has an API but runs a proprietary OS, devices with limited
CPU or memory, or devices that could run a minion, but for security reasons,
will not.

*Proxy minions are not an "out of the box" feature*.  Because there are an
infinite number of controllable devices, you will most likely have to write the
interface yourself. Fortunately, this is only as difficult as the actual
interface to the proxied device.  Devices that have an existing Python module
(PyUSB for example) would be relatively simple to interface.  Code to control a
device that has an HTML REST-based interface should be easy.  Code to control
your typical housecat would be excellent source material for a PhD thesis.

Salt proxy-minions provide the 'plumbing' that allows device enumeration
and discovery, control, status, remote execution, and state management.

Getting Started
---------------

The following diagram may be helpful in understanding the structure of a Salt
installation that includes proxy-minions:

.. image:: /_static/proxy_minions.png

The key thing to remember is the left-most section of the diagram.  Salt's
nature is to have a minion connect to a master, then the master may control
the minion.  However, for proxy minions, the target device cannot run a minion,
and thus must rely on a separate minion to fire up the proxy-minion and make the
initial and persistent connection.

After the proxy minion is started and initiates its connection to the 'dumb'
device, it connects back to the salt-master and ceases to be affiliated in
any way with the minion that started it.

To create support for a proxied device one needs to create four things:

1. The `proxy_connection_module`_ (located in salt/proxy).
2. The `grains support code`_ (located in salt/grains).
3. :ref:`Salt modules <all-salt.modules>` specific to the controlled
   device.
4. :ref:`Salt states <all-salt.states>` specific to the controlled device.


Configuration parameters on the master
######################################

Proxy minions require no configuration parameters in /etc/salt/master.

Salt's Pillar system is ideally suited for configuring proxy-minions.  Proxies
can either be designated via a pillar file in pillar_roots, or through an
external pillar.  External pillars afford the opportunity for interfacing with
a configuration management system, database, or other knowledgeable system that
that may already contain all the details of proxy targets.  To use static files
in pillar_roots, pattern your files after the following examples, which are
based on the diagram above:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      minioncontroller1:
        - networkswitches
      minioncontroller2:
        - reallydumbdevices
      minioncontroller3:
        - smsgateway


``/srv/pillar/networkswitches.sls``

.. code-block:: yaml

    proxy:
      dumbdevice1:
        proxytype: networkswitch
        host: 172.23.23.5
        username: root
        passwd: letmein
      dumbdevice2:
        proxytype: networkswitch
        host: 172.23.23.6
        username: root
        passwd: letmein
      dumbdevice3:
        proxytype: networkswitch
        host: 172.23.23.7
        username: root
        passwd: letmein

``/srv/pillar/reallydumbdevices.sls``

.. code-block:: yaml

    proxy:
      dumbdevice4:
        proxytype: i2c_lightshow
        i2c_address: 1
      dumbdevice5:
        proxytype: i2c_lightshow
        i2c_address: 2
      dumbdevice6:
        proxytype: 433mhz_wireless

``/srv/pillar/smsgateway.sls``

.. code-block:: yaml

    proxy:
      minioncontroller3:
        dumbdevice7:
          proxytype: sms_serial
          deventry: /dev/tty04

Note the contents of each minioncontroller key may differ widely based on
the type of device that the proxy-minion is managing.

In the above example

- dumbdevices 1, 2, and 3 are network switches that have a management
  interface available at a particular IP address.

- dumbdevices 4 and 5 are very low-level devices controlled over an i2c bus.
  In this case the devices are physically connected to machine
  'minioncontroller2', and are addressable on the i2c bus at their respective
  i2c addresses.

- dumbdevice6 is a 433 MHz wireless transmitter, also physically connected to
  minioncontroller2

- dumbdevice7 is an SMS gateway connected to machine minioncontroller3 via a
  serial port.

Because of the way pillar works, each of the salt-minions that fork off the
proxy minions will only see the keys specific to the proxies it will be
handling.  In other words, from the above example, only minioncontroller1 will
see the connection information for dumbdevices 1, 2, and 3.  Minioncontroller2
will see configuration data for dumbdevices 4, 5, and 6, and minioncontroller3
will be privy to dumbdevice7.

Also, in general, proxy-minions are lightweight, so the machines that run them
could conceivably control a large number of devices.  The example above is just
to illustrate that it is possible for the proxy services to be spread across
many machines if necessary, or intentionally run on machines that need to
control devices because of some physical interface (e.g. i2c and serial above).
Another reason to divide proxy services might be security.  In more secure
environments only certain machines may have a network path to certain devices.

Now our salt-minions know if they are supposed to spawn a proxy-minion process
to control a particular device.  That proxy-minion process will initiate
a connection back to the master to enable control.


.. _proxy_connection_module:

Proxymodules
############

A proxy module encapsulates all the code necessary to interface with a device.
Proxymodules are located inside the salt.proxy module.  At a minimum
a proxymodule object must implement the following functions:

``__virtual__()``: This function performs the same duty that it does for other
types of Salt modules.  Logic goes here to determine if the module can be
loaded, checking for the presence of Python modules on which the proxy deepends.
Returning ``False`` will prevent the module from loading.

``init(opts)``: Perform any initialization that the device needs.  This is
a good place to bring up a persistent connection to a device, or authenticate
to create a persistent authorization token.

``id(opts)``: Returns a unique, unchanging id for the controlled device.  This is
the "name" of the device, and is used by the salt-master for targeting and key
authentication.

``shutdown()``: Code to cleanly shut down or close a connection to
a controlled device goes here.  This function must exist, but can contain only
the keyword ``pass`` if there is no shutdown logic required.

``ping()``: While not required, it is highly recommended that this function also
be defined in the proxymodule. The code for ``ping`` should contact the
controlled device and make sure it is really available.

Here is an example proxymodule used to interface to a *very* simple REST
server.  Code for the server is in the `salt-contrib GitHub repository <https://github.com/saltstack/salt-contrib/proxyminion_rest_example>`_

This proxymodule enables "service" enumration, starting, stopping, restarting,
and status; "package" installation, and a ping.

.. code-block:: python


    # -*- coding: utf-8 -*-
    '''
    This is a simple proxy-minion designed to connect to and communicate with
    the bottle-based web service contained in 
    https://github.com/saltstack/salt-contrib/proxyminion_rest_example
    '''
    from __future__ import absolute_import

    # Import python libs
    import logging
    import salt.utils.http

    HAS_REST_EXAMPLE = True

    # This must be present or the Salt loader won't load this module
    __proxyenabled__ = ['rest_sample']


    # Variables are scoped to this module so we can have persistent data
    # across calls to fns in here.
    GRAINS_CACHE = {}
    DETAILS = {}

    # Want logging!
    log = logging.getLogger(__file__)


    # This does nothing, it's here just as an example and to provide a log
    # entry when the module is loaded.
    def __virtual__():
        '''
        Only return if all the modules are available
        '''
        log.debug('rest_sample proxy __virtual__() called...')
        return True

    # Every proxy module needs an 'init', though you can 
    # just put a 'pass' here if it doesn't need to do anything.
    def init(opts):
        log.debug('rest_sample proxy init() called...')

        # Save the REST URL 
        DETAILS['url'] = opts['proxy']['url']

        # Make sure the REST URL ends with a '/'
        if not DETAILS['url'].endswith('/'):
            DETAILS['url'] += '/'


    def id(opts):
        '''
        Return a unique ID for this proxy minion.  This ID MUST NOT CHANGE.
        If it changes while the proxy is running the salt-master will get 
        really confused and may stop talking to this minion
        '''
        r = salt.utils.http.query(opts['proxy']['url']+'id', decode_type='json', decode=True)
        return r['dict']['id'].encode('ascii', 'ignore')


    def grains():
        '''
        Get the grains from the proxied device
        '''
        if not GRAINS_CACHE:
            r = salt.utils.http.query(DETAILS['url']+'info', decode_type='json', decode=True)
            GRAINS_CACHE = r['dict']
        return GRAINS_CACHE


    def grains_refresh():
        '''
        Refresh the grains from the proxied device
        '''
        GRAINS_CACHE = {}
        return grains()


    def service_start(name):
        '''
        Start a "service" on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'service/start/'+name, decode_type='json', decode=True)
        return r['dict']


    def service_stop(name):
        '''
        Stop a "service" on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'service/stop/'+name, decode_type='json', decode=True)
        return r['dict']


    def service_restart(name):
        '''
        Restart a "service" on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'service/restart/'+name, decode_type='json', decode=True)
        return r['dict']


    def service_list():
        '''
        List "services" on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'service/list', decode_type='json', decode=True)
        return r['dict']


    def service_status(name):
        '''
        Check if a service is running on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'service/status/'+name, decode_type='json', decode=True)
        return r['dict']


    def package_list():
        '''
        List "packages" installed on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'package/list', decode_type='json', decode=True)
        return r['dict']


    def package_install(name, **kwargs):
        '''
        Install a "package" on the REST server
        '''
        cmd = DETAILS['url']+'package/install/'+name
        if 'version' in kwargs:
            cmd += '/'+kwargs['version']
        else:
            cmd += '/1.0'
        r = salt.utils.http.query(cmd, decode_type='json', decode=True)


    def package_remove(name):

        '''
        Remove a "package" on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'package/remove/'+name, decode_type='json', decode=True)
        return r['dict']


    def package_status(name):
        '''
        Check the installation status of a package on the REST server
        '''
        r = salt.utils.http.query(DETAILS['url']+'package/status/'+name, decode_type='json', decode=True)
        return r['dict']


    def ping():
        '''
        Is the REST server up?
        '''
        r = salt.utils.http.query(DETAILS['url']+'ping', decode_type='json', decode=True)
        try:
            return r['dict'].get('ret', False)
        except Exception:
            return False


    def shutdown(opts):
        '''
        For this proxy shutdown is a no-op
        '''
        log.debug('rest_sample proxy shutdown() called...')
        pass


.. _grains support code:

Grains are data about minions.  Most proxied devices will have a paltry amount
of data as compared to a typical Linux server.  By default, a proxy minion will
have no grains set at all.  Salt core code requires values for ``kernel``,
``os``, and ``os_family``.  To add them (and others) to your proxy minion for
a particular device, create a file in salt/grains named [proxytype].py and place
inside it the different functions that need to be run to collect the data you
are interested in.  Here's an example:


.. code: python::

    # -*- coding: utf-8 -*-
    '''
    Generate baseline proxy minion grains
    '''
    __proxyenabled__ = ['rest_sample']

    __virtualname__ = 'rest_sample'


    def __virtual__():
        if 'proxy' not in __opts__:
            return False
        else:
            return __virtualname__

    def kernel():
        return {'kernel':'proxy'}

    def os():
        return {'os':'proxy'}

    def location():
        return {'location': 'In this darn virtual machine.  Let me out!'}


    def os_family():
        return {'os_family': 'proxy'}


    def os_data():
        return {'os_data': 'funkyHttp release 1.0.a.4.g'}


The __proxyenabled__ directive
------------------------------

Salt execution moduless, by, and large, cannot "automatically" work
with proxied devices.  Execution modules like ``pkg`` or ``sqlite3`` have no
meaning on a network switch or a housecat.  For an execution module to be
available to a proxy-minion, the ``__proxyenabled__`` variable must be defined
in the module as an array containing the names of all the proxytypes that this
module can support.  The array can contain the special value ``*`` to indicate
that the module supports all proxies.

If no ``__proxyenabled__`` variable is defined, then by default, the
execution module is unavailable to any proxy.

Here is an excerpt from a module that was modified to support proxy-minions:

.. code-block:: python

   __proxyenabled__ = ['*']
   
   [...]

    def ping():

        if 'proxymodule' in __opts__:
            if 'ping' in __opts__['proxyobject'].__attr__():
                return __opts['proxyobject'].ping()
            else:
                return False
        else:
            return True

And then in salt.proxy.rest_sample.py we find

.. code-block:: python

    def ping():
        '''
        Is the REST server up?
        '''
        r = salt.utils.http.query(DETAILS['url']+'ping', decode_type='json', decode=True)
        try:
            return r['dict'].get('ret', False)
        except Exception:
            return False


