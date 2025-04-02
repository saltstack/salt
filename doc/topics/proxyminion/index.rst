.. _proxy-minion:

=================
Salt Proxy Minion
=================

Proxy minions are a developing Salt feature that enables controlling devices
that, for whatever reason, cannot run a standard salt-minion.  Examples include
network gear that has an API but runs a proprietary OS, devices with limited
CPU or memory, or devices that could run a minion, but for security reasons,
will not.

There are some :ref:`proxy modules <all-salt.proxy>` available, but if your device
interface is not currently supported you will most likely have to write the interface
yourself, because there are an infinite number of controllable devices. Fortunately, this
is only as difficult as the actual interface to the proxied device. Devices that have an
existing Python module (PyUSB for example) would be relatively simple to interface.
Code to control a device that has an HTML REST-based interface should be easy.  Code to
control your typical housecat would be excellent source material for a PhD thesis.

Salt proxy-minions provide the 'plumbing' that allows device enumeration
and discovery, control, status, remote execution, and state management.

See the :ref:`Proxy Minion Walkthrough <proxy-minion-end-to-end-example>` for an end-to-end
demonstration of a working REST-based proxy minion.

See the :ref:`Proxy Minion SSH Walkthrough <proxy-minion-ssh-end-to-end-example>` for an end-to-end
demonstration of a working SSH proxy minion.


See :ref:`Proxyminion States <proxy-minion-states>` to configure and
run ``salt-proxy`` on a remote minion. Specify all your master side
proxy (pillar) configuration and use this state to remotely configure proxies on one
or more minions.

See :ref:`Proxyminion Beacon <proxy-minion-beacon>` to help
with easy configuration and management of ``salt-proxy`` processes.

New in 2017.7.0
---------------

The :conf_proxy:`proxy_merge_grains_in_module` configuration variable
introduced in 2016.3, has been changed, defaulting to ``True``.

The connection with the remote device is kept alive by default, when the
module implements the ``alive`` function and :conf_proxy:`proxy_keep_alive`
is set to ``True``. The polling interval is set using the
:conf_proxy:`proxy_keep_alive_interval` option which defaults to 1 minute.

The developers are also able to use the :conf_proxy:`proxy_always_alive`,
when designing a proxy module flexible enough to open the
connection with the remote device only when required.

New in 2016.11.0
----------------

Proxy minions now support configuration files with names ending in '\*.conf'
and placed in /etc/salt/proxy.d.

Proxy minions can now be configured in /etc/salt/proxy or /etc/salt/proxy.d
instead of just pillar.  Configuration format is the same as it would be in pillar.


New in 2016.3
-------------

The deprecated config option ``enumerate_proxy_minions`` has been removed.

As mentioned in earlier documentation, the ``add_proxymodule_to_opts``
configuration variable defaults to ``False`` in this release.  This means if you
have proxymodules or other code looking in ``__opts__['proxymodule']`` you
will need to set this variable in your ``/etc/salt/proxy`` file, or
modify your code to use the `__proxy__` injected variable.

The ``__proxyenabled__`` directive now only applies to grains and proxy modules
themselves.  Standard execution modules and state modules are not prevented
from loading for proxy minions.

Enhancements in grains processing have made the ``__proxyenabled__`` directive
somewhat redundant in dynamic grains code.  It is still required, but best
practices for the ``__virtual__`` function in grains files have changed.  It
is now recommended that the ``__virtual__`` functions check to make sure
they are being loaded for the correct proxytype, example below:

.. code-block:: python

    def __virtual__():
        """
        Only work on proxy
        """
        try:
            if (
                salt.utils.platform.is_proxy()
                and __opts__["proxy"]["proxytype"] == "ssh_sample"
            ):
                return __virtualname__
        except KeyError:
            pass

        return False

The try/except block above exists because grains are processed very early
in the proxy minion startup process, sometimes earlier than the proxy
key in the ``__opts__`` dictionary is populated.

Grains are loaded so early in startup that no dunder dictionaries are
present, so ``__proxy__``, ``__salt__``, etc. are not available.  Custom
grains located in ``/srv/salt/_grains`` and in the salt install grains
directory can now take a single argument, ``proxy``, that is identical
to ``__proxy__``.  This enables patterns like

.. code-block:: python

   def get_ip(proxy):
       """
       Ask the remote device what IP it has
       """
       return {"ip": proxy["proxymodulename.get_ip"]()}


Then the grain ``ip`` will contain the result of calling the ``get_ip()`` function
in the proxymodule called ``proxymodulename``.

Proxy modules now benefit from including a function called ``initialized()``.  This
function should return ``True`` if the proxy's ``init()`` function has been successfully
called.  This is needed to make grains processing easier.

Finally, if there is a function called ``grains`` in the proxymodule, it
will be executed on proxy-minion startup and its contents will be merged with
the rest of the proxy's grains.  Since older proxy-minions might have used other
methods to call such a function and add its results to grains, this is config-gated
by a new proxy configuration option called ``proxy_merge_grains_in_module``.  This
defaults to ``True`` in the **2017.7.0** release.


New in 2015.8.2
---------------

*BREAKING CHANGE*: Adding the `proxymodule` variable  to __opts__ is deprecated.
The `proxymodule` variable has been moved a new globally-injected variable
called `__proxy__`.  A related configuration option called
`add_proxymodule_to_opts` has been added and defaults to `True`.  In the next
major release, 2016.3.0, this variable will default to False.

In the meantime, proxies that functioned under 2015.8.0 and .1 should continue
to work under 2015.8.2.  You should rework your proxy code to use `__proxy__` as
soon as possible.

The `rest_sample` example proxy minion has been updated to use `__proxy__`.

This change was made because proxymodules are a LazyLoader object, but
LazyLoaders cannot be serialized.  `__opts__` gets serialized, and so things
like `saltutil.sync_all` and `state.highstate` would throw exceptions.

Support has been added to Salt's loader allowing custom proxymodules
to be placed in ``salt://_proxy``.  Proxy minions that need these modules
will need to be restarted to pick up any changes.  A corresponding utility function,
``saltutil.sync_proxymodules``, has been added to sync these modules to minions.

In addition, a salt.utils helper function called `is_proxy()` was added to make
it easier to tell when the running minion is a proxy minion. **NOTE: This
function was renamed to salt.utils.platform.is_proxy() for the 2018.3.0
release**

New in 2015.8
-------------

Starting with the 2015.8 release of Salt, proxy processes are no longer forked
off from a controlling minion.  Instead, they have their own script
``salt-proxy`` which takes mostly the same arguments that the standard Salt
minion does with the addition of ``--proxyid``.  This is the id that the
salt-proxy will use to identify itself to the master.  Proxy configurations are
still best kept in Pillar and their format has not changed.

This change allows for better process control and logging.  Proxy processes can
now be listed with standard process management utilities (``ps`` from the
command line).  Also, a full Salt minion is no longer required (though it is
still strongly recommended) on machines hosting proxies.


Getting Started
---------------

The following diagram may be helpful in understanding the structure of a Salt
installation that includes proxy-minions:

.. image:: /_static/proxy_minions.png

The key thing to remember is the left-most section of the diagram.  Salt's
nature is to have a minion connect to a master, then the master may control
the minion.  However, for proxy minions, the target device cannot run a minion.

After the proxy minion is started and initiates its connection to the
device, it connects back to the salt-master and for all intents and purposes
looks like just another minion to the Salt master.

To create support for a proxied device one needs to create four things:

1. The `proxy_connection_module`_ (located in salt/proxy).
2. The `grains support code`_ (located in salt/grains).
3. :ref:`Salt modules <all-salt.modules>` specific to the controlled
   device.
4. :ref:`Salt states <all-salt.states>` specific to the controlled device.


Configuration parameters
########################

Proxy minions require no configuration parameters in /etc/salt/master.

Salt's Pillar system is ideally suited for configuring proxy-minions
(though they can be configured in /etc/salt/proxy as well).  Proxies
can either be designated via a pillar file in pillar_roots, or through an
external pillar.  External pillars afford the opportunity for interfacing with
a configuration management system, database, or other knowledgeable system that
that may already contain all the details of proxy targets.  To use static files
in pillar_roots, pattern your files after the following examples, which are
based on the diagram above:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      net-device1:
        - net-device1
      net-device2:
        - net-device2
      net-device3:
        - net-device3
      i2c-device4:
        - i2c-device4
      i2c-device5:
        - i2c-device5
      433wireless-device6:
        - 433wireless-device6
      smsgate-device7:
        - device7


``/srv/pillar/net-device1.sls``

.. code-block:: yaml

    proxy:
      proxytype: networkswitch
      host: 172.23.23.5
      username: root
      passwd: letmein


``/srv/pillar/net-device2.sls``

.. code-block:: yaml

    proxy:
      proxytype: networkswitch
      host: 172.23.23.6
      username: root
      passwd: letmein


``/srv/pillar/net-device3.sls``

.. code-block:: yaml

    proxy:
      proxytype: networkswitch
      host: 172.23.23.7
      username: root
      passwd: letmein


``/srv/pillar/i2c-device4.sls``

.. code-block:: yaml

    proxy:
      proxytype: i2c_lightshow
      i2c_address: 1


``/srv/pillar/i2c-device5.sls``

.. code-block:: yaml

      proxy:
        proxytype: i2c_lightshow
        i2c_address: 2


``/srv/pillar/433wireless-device6.sls``

.. code-block:: yaml

      proxy:
        proxytype: 433mhz_wireless


``/srv/pillar/smsgate-device7.sls``

.. code-block:: yaml

    proxy:
      proxytype: sms_serial
      deventry: /dev/tty04


Note the contents of each minioncontroller key may differ widely based on
the type of device that the proxy-minion is managing.

In the above example

- net-devices 1, 2, and 3 are network switches that have a management
  interface available at a particular IP address.

- i2c-devices 4 and 5 are very low-level devices controlled over an i2c bus.
  In this case the devices are physically connected to machine
  'minioncontroller2', and are addressable on the i2c bus at their respective
  i2c addresses.

- 433wireless-device6 is a 433 MHz wireless transmitter, also physically connected to
  minioncontroller2

- smsgate-device7 is an SMS gateway connected to machine minioncontroller3 via a
  serial port.

Because of the way pillar works, each of the salt-proxy processes that fork off the
proxy minions will only see the keys specific to the proxies it will be
handling.

Proxies can be configured in /etc/salt/proxy or with files in /etc/salt/proxy.d as of
Salt's 2016.11.0 release.

Also, in general, proxy-minions are lightweight, so the machines that run them
could conceivably control a large number of devices.  To run more than one proxy from
a single machine, simply start an additional proxy process with ``--proxyid``
set to the id to which you want the proxy to bind.
It is possible for the proxy services to be spread across
many machines if necessary, or intentionally run on machines that need to
control devices because of some physical interface (e.g. i2c and serial above).
Another reason to divide proxy services might be security.  In more secure
environments only certain machines may have a network path to certain devices.


.. _proxy_connection_module:

Proxymodules
############

A proxy module encapsulates all the code necessary to interface with a device.
Proxymodules are located inside the salt.proxy module, or can be placed in
the ``_proxy`` directory in your file_roots (default is ``/srv/salt/_proxy``.
At a minimum a proxymodule object must implement the following functions:

``__virtual__()``: This function performs the same duty that it does for other
types of Salt modules.  Logic goes here to determine if the module can be
loaded, checking for the presence of Python modules on which the proxy depends.
Returning ``False`` will prevent the module from loading.

``init(opts)``: Perform any initialization that the device needs.  This is
a good place to bring up a persistent connection to a device, or authenticate
to create a persistent authorization token.

``initialized()``: Returns True if ``init()`` was successfully called.

``shutdown()``: Code to cleanly shut down or close a connection to
a controlled device goes here.  This function must exist, but can contain only
the keyword ``pass`` if there is no shutdown logic required.

``ping()``: While not required, it is highly recommended that this function also
be defined in the proxymodule. The code for ``ping`` should contact the
controlled device and make sure it is really available.

``alive(opts)``: Another optional function, it is used together with the
``proxy_keep_alive`` option (default: ``True``). This function should
return a boolean value corresponding to the state of the connection.
If the connection is down, will try to restart (``shutdown``
followed by ``init``). The polling frequency is controlled using
the ``proxy_keep_alive_interval`` option, in minutes.

``grains()``: Rather than including grains in /srv/salt/_grains or in
the standard install directories for grains, grains can be computed and
returned by this function.  This function will be called automatically
if ``proxy_merge_grains_in_module`` is set to ``True`` in /etc/salt/proxy.
This variable defaults to ``True`` in the release code-named *2017.7.0*.

Pre 2015.8 the proxymodule also must have an ``id()`` function.  2015.8 and following don't use
this function because the proxy's id is required on the command line.

Here is an example proxymodule used to interface to a *very* simple REST
server. Code for the server is in the `salt-contrib GitHub repository`_.

.. _`salt-contrib GitHub repository`: https://github.com/saltstack/salt-contrib/tree/master/proxyminion_rest_example

This proxymodule enables "service" enumeration, starting, stopping, restarting,
and status; "package" installation, and a ping.

.. code-block:: python

    # -*- coding: utf-8 -*-
    """
    This is a simple proxy-minion designed to connect to and communicate with
    the bottle-based web service contained in https://github.com/saltstack/salt-contrib/tree/master/proxyminion_rest_example
    """
    from __future__ import absolute_import

    # Import python libs
    import logging
    import salt.utils.http

    HAS_REST_EXAMPLE = True

    # This must be present or the Salt loader won't load this module
    __proxyenabled__ = ["rest_sample"]


    # Variables are scoped to this module so we can have persistent data
    # across calls to fns in here.
    GRAINS_CACHE = {}
    DETAILS = {}

    # Want logging!
    log = logging.getLogger(__file__)


    # This does nothing, it's here just as an example and to provide a log
    # entry when the module is loaded.
    def __virtual__():
        """
        Only return if all the modules are available
        """
        log.debug("rest_sample proxy __virtual__() called...")
        return True


    def _complicated_function_that_determines_if_alive():
        return True


    # Every proxy module needs an 'init', though you can
    # just put DETAILS['initialized'] = True here if nothing
    # else needs to be done.


    def init(opts):
        log.debug("rest_sample proxy init() called...")
        DETAILS["initialized"] = True

        # Save the REST URL
        DETAILS["url"] = opts["proxy"]["url"]

        # Make sure the REST URL ends with a '/'
        if not DETAILS["url"].endswith("/"):
            DETAILS["url"] += "/"


    def alive(opts):
        """
        This function returns a flag with the connection state.
        It is very useful when the proxy minion establishes the communication
        via a channel that requires a more elaborated keep-alive mechanism, e.g.
        NETCONF over SSH.
        """
        log.debug("rest_sample proxy alive() called...")
        return _complicated_function_that_determines_if_alive()


    def initialized():
        """
        Since grains are loaded in many different places and some of those
        places occur before the proxy can be initialized, return whether
        our init() function has been called
        """
        return DETAILS.get("initialized", False)


    def grains():
        """
        Get the grains from the proxied device
        """
        if not DETAILS.get("grains_cache", {}):
            r = salt.utils.http.query(
                DETAILS["url"] + "info", decode_type="json", decode=True
            )
            DETAILS["grains_cache"] = r["dict"]
        return DETAILS["grains_cache"]


    def grains_refresh():
        """
        Refresh the grains from the proxied device
        """
        DETAILS["grains_cache"] = None
        return grains()


    def fns():
        return {
            "details": "This key is here because a function in "
            "grains/rest_sample.py called fns() here in the proxymodule."
        }


    def service_start(name):
        """
        Start a "service" on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "service/start/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def service_stop(name):
        """
        Stop a "service" on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "service/stop/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def service_restart(name):
        """
        Restart a "service" on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "service/restart/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def service_list():
        """
        List "services" on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "service/list", decode_type="json", decode=True
        )
        return r["dict"]


    def service_status(name):
        """
        Check if a service is running on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "service/status/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def package_list():
        """
        List "packages" installed on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "package/list", decode_type="json", decode=True
        )
        return r["dict"]


    def package_install(name, **kwargs):
        """
        Install a "package" on the REST server
        """
        cmd = DETAILS["url"] + "package/install/" + name
        if kwargs.get("version", False):
            cmd += "/" + kwargs["version"]
        else:
            cmd += "/1.0"
        r = salt.utils.http.query(cmd, decode_type="json", decode=True)
        return r["dict"]


    def fix_outage():
        r = salt.utils.http.query(DETAILS["url"] + "fix_outage")
        return r


    def uptodate(name):
        """
        Call the REST endpoint to see if the packages on the "server" are up to date.
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "package/remove/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def package_remove(name):
        """
        Remove a "package" on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "package/remove/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def package_status(name):
        """
        Check the installation status of a package on the REST server
        """
        r = salt.utils.http.query(
            DETAILS["url"] + "package/status/" + name, decode_type="json", decode=True
        )
        return r["dict"]


    def ping():
        """
        Is the REST server up?
        """
        r = salt.utils.http.query(DETAILS["url"] + "ping", decode_type="json", decode=True)
        try:
            return r["dict"].get("ret", False)
        except Exception:
            return False


    def shutdown(opts):
        """
        For this proxy shutdown is a no-op
        """
        log.debug("rest_sample proxy shutdown() called...")


.. _grains support code:

Grains are data about minions.  Most proxied devices will have a paltry amount
of data as compared to a typical Linux server.  By default, a proxy minion will
have several grains taken from the host.  Salt core code requires values for ``kernel``,
``os``, and ``os_family``--all of these are forced to be ``proxy`` for proxy-minions.

To add others to your proxy minion for
a particular device, create a file in salt/grains named [proxytype].py and place
inside it the different functions that need to be run to collect the data you
are interested in.  Here's an example.  Note the function below called ``proxy_functions``.
It demonstrates how a grains function can take a single argument, which will be
set to the value of ``__proxy__``.  Dunder variables are not yet injected into Salt processes
at the time grains are loaded, so this enables us to get a handle to the proxymodule so we
can cross-call the functions therein used to communicate with the controlled device.

Note that as of 2016.3, grains values can also be calculated in a function called ``grains()``
in the proxymodule itself.  This might be useful if a proxymodule author wants to keep
all the code for the proxy interface in the same place instead of splitting it between
the proxy and grains directories.

This function will only be called automatically if the configuration variable
``proxy_merge_grains_in_module`` is set to True in the proxy configuration file
(default ``/etc/salt/proxy``).  This variable defaults to ``True`` in the
release code-named *2017.7.0*.


.. code: python::

    # -*- coding: utf-8 -*-
    '''
    Generate baseline proxy minion grains
    '''
    from __future__ import absolute_import
    import salt.utils.platform

    __proxyenabled__ = ['rest_sample']

    __virtualname__ = 'rest_sample'


    def __virtual__():
        try:
            if salt.utils.platform.is_proxy() and __opts__['proxy']['proxytype'] == 'rest_sample':
                return __virtualname__
        except KeyError:
            pass

        return False


    def kernel():
        return {'kernel': 'proxy'}


    def proxy_functions(proxy):
        '''
        The loader will execute functions with one argument and pass
        a reference to the proxymodules LazyLoader object.  However,
        grains sometimes get called before the LazyLoader object is setup
        so `proxy` might be None.
        '''
        if proxy:
            return {'proxy_functions': proxy['rest_sample.fns']()}


    def os():
        return {'os': 'RestExampleOS'}


    def location():
        return {'location': 'In this darn virtual machine.  Let me out!'}


    def os_family():
        return {'os_family': 'proxy'}


    def os_data():
        return {'os_data': 'funkyHttp release 1.0.a.4.g'}


The __proxyenabled__ directive
------------------------------

In previous versions of Salt the ``__proxyenabled__`` directive controlled
loading of all Salt modules for proxies (e.g. grains, execution modules, state
modules).  From 2016.3 on, the only modules that respect ``__proxyenabled__``
are grains and proxy modules.  These modules need to be told which proxy they
work with.

``__proxyenabled__`` is a list, and can contain a single '*' to indicate
a grains module works with all proxies.

Example from ``salt/grains/rest_sample.py``:

.. code-block:: python

    # -*- coding: utf-8 -*-
    """
    Generate baseline proxy minion grains
    """
    from __future__ import absolute_import
    import salt.utils.platform

    __proxyenabled__ = ["rest_sample"]

    __virtualname__ = "rest_sample"


    def __virtual__():
        try:
            if (
                salt.utils.platform.is_proxy()
                and __opts__["proxy"]["proxytype"] == "rest_sample"
            ):
                return __virtualname__
        except KeyError:
            pass

        return False

.. toctree::
    :maxdepth: 2
    :glob:

    demo




SSH Proxymodules
----------------

See above for a general introduction to writing proxy modules.
All of the guidelines that apply to REST are the same for SSH.
This sections specifically talks about the SSH proxy module and
explains the working of the example proxy module ``ssh_sample``.

Here is a simple example proxymodule used to interface to a device over SSH.
Code for the SSH shell is in the `salt-contrib GitHub repository`_.

This proxymodule enables "package" installation.

.. code-block:: python

    # -*- coding: utf-8 -*-
    """
    This is a simple proxy-minion designed to connect to and communicate with
    a server that exposes functionality via SSH.
    This can be used as an option when the device does not provide
    an api over HTTP and doesn't have the python stack to run a minion.
    """
    from __future__ import absolute_import

    # Import python libs
    import salt.utils.json
    import logging

    # Import Salt's libs
    from salt.utils.vt_helper import SSHConnection
    from salt.utils.vt import TerminalException

    # This must be present or the Salt loader won't load this module
    __proxyenabled__ = ["ssh_sample"]

    DETAILS = {}

    # Want logging!
    log = logging.getLogger(__file__)


    # This does nothing, it's here just as an example and to provide a log
    # entry when the module is loaded.
    def __virtual__():
        """
        Only return if all the modules are available
        """
        log.info("ssh_sample proxy __virtual__() called...")

        return True


    def init(opts):
        """
        Required.
        Can be used to initialize the server connection.
        """
        try:
            DETAILS["server"] = SSHConnection(
                host=__opts__["proxy"]["host"],
                username=__opts__["proxy"]["username"],
                password=__opts__["proxy"]["password"],
            )
            # connected to the SSH server
            out, err = DETAILS["server"].sendline("help")

        except TerminalException as e:
            log.error(e)
            return False


    def shutdown(opts):
        """
        Disconnect
        """
        DETAILS["server"].close_connection()


    def parse(out):
        """
        Extract json from out.

        Parameter
            out: Type string. The data returned by the
            ssh command.
        """
        jsonret = []
        in_json = False
        for ln_ in out.split("\n"):
            if "{" in ln_:
                in_json = True
            if in_json:
                jsonret.append(ln_)
            if "}" in ln_:
                in_json = False
        return salt.utils.json.loads("\n".join(jsonret))


    def package_list():
        """
        List "packages" by executing a command via ssh
        This function is called in response to the salt command

        .. code-block:: bash

            salt target_minion pkg.list_pkgs

        """
        # Send the command to execute
        out, err = DETAILS["server"].sendline("pkg_list")

        # "scrape" the output and return the right fields as a dict
        return parse(out)


    def package_install(name, **kwargs):
        """
        Install a "package" on the REST server
        """
        cmd = "pkg_install " + name
        if "version" in kwargs:
            cmd += "/" + kwargs["version"]
        else:
            cmd += "/1.0"

        # Send the command to execute
        out, err = DETAILS["server"].sendline(cmd)

        # "scrape" the output and return the right fields as a dict
        return parse(out)


    def package_remove(name):
        """
        Remove a "package" on the REST server
        """
        cmd = "pkg_remove " + name

        # Send the command to execute
        out, err = DETAILS["server"].sendline(cmd)

        # "scrape" the output and return the right fields as a dict
        return parse(out)


Connection Setup
################

The ``init()`` method is responsible for connection setup. It uses the ``host``, ``username`` and ``password`` config variables defined in the pillar data. The ``prompt`` kwarg can be passed to ``SSHConnection`` if your SSH server's prompt differs from the example's prompt ``(Cmd)``. Instantiating the ``SSHConnection`` class establishes an SSH connection to the ssh server (using Salt VT).

Command execution
#################

The ``package_*`` methods use the SSH connection (established in ``init()``) to send commands out to the SSH server. The ``sendline()`` method of ``SSHConnection`` class can be used to send commands out to the server. In the above example we send commands like ``pkg_list`` or ``pkg_install``. You can send any SSH command via this utility.

Output parsing
##############

Output returned by ``sendline()`` is a tuple of strings representing the stdout and the stderr respectively. In the toy example shown we simply scrape the output and convert it to a python dictionary, as shown in the ``parse`` method. You can tailor this method to match your parsing logic.

Connection teardown
###################

The ``shutdown`` method is responsible for calling the ``close_connection()`` method of ``SSHConnection`` class. This ends the SSH connection to the server.

For more information please refer to class `SSHConnection`_.

.. toctree::
    :maxdepth: 2
    :glob:

    ssh
    beacon
    state
    ../tutorials/esxi_proxy_minion

.. _SSHConnection: https://github.com/saltstack/salt/blob/b8271c7512da7e048019ee26422be9e7d6b795ab/salt/utils/vt_helper.py#L28
