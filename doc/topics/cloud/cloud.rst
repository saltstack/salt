============================
Writing Cloud Driver Modules
============================

Salt Cloud runs on a module system similar to the main Salt project. The
modules inside saltcloud exist in the ``salt/cloud/clouds`` directory of the
salt source.

There are two basic types of cloud modules. If a cloud host is supported by
libcloud, then using it is the fastest route to getting a module written. The
Apache Libcloud project is located at:

http://libcloud.apache.org/

Not every cloud host is supported by libcloud. Additionally, not every
feature in a supported cloud host is necessarily supported by libcloud. In
either of these cases, a module can be created which does not rely on libcloud.

All Driver Modules
==================
The following functions are required by all driver modules, whether or not they are
based on libcloud.

The __virtual__() Function
--------------------------
This function determines whether or not to make this cloud module available
upon execution. Most often, it uses ``get_configured_provider()`` to determine
if the necessary configuration has been set up. It may also check for necessary
imports, to decide whether to load the module. In most cases, it will return a
``True`` or ``False`` value. If the name of the driver used does not match the
filename, then that name should be returned instead of ``True``. An example of
this may be seen in the Azure module:

https://github.com/saltstack/salt/tree/|repo_primary_branch|/salt/cloud/clouds/msazure.py

The get_configured_provider() Function
--------------------------------------
This function uses ``config.is_provider_configured()`` to determine whether
all required information for this driver has been configured. The last value
in the list of required settings should be followed by a comma.


Libcloud Based Modules
======================
Writing a cloud module based on libcloud has two major advantages. First of all,
much of the work has already been done by the libcloud project. Second, most of
the functions necessary to Salt have already been added to the Salt Cloud
project.

The create() Function
---------------------
The most important function that does need to be manually written is the
``create()`` function. This is what is used to request a virtual machine to be
created by the cloud host, wait for it to become available, and then
(optionally) log in and install Salt on it.

A good example to follow for writing a cloud driver module based on libcloud
is the module provided for Linode:

https://github.com/saltstack/salt/tree/|repo_primary_branch|/salt/cloud/clouds/linode.py

The basic flow of a ``create()`` function is as follows:

* Send a request to the cloud host to create a virtual machine.
* Wait for the virtual machine to become available.
* Generate kwargs to be used to deploy Salt.
* Log into the virtual machine and deploy Salt.
* Return a data structure that describes the newly-created virtual machine.

At various points throughout this function, events may be fired on the Salt
event bus. Four of these events, which are described below, are required. Other
events may be added by the user, where appropriate.

When the ``create()`` function is called, it is passed a data structure called
``vm_``. This dict contains a composite of information describing the virtual
machine to be created. A dict called ``__opts__`` is also provided by Salt,
which contains the options used to run Salt Cloud, as well as a set of
configuration and environment variables.

The first thing the ``create()`` function must do is fire an event stating that
it has started the create process. This event is tagged
``salt/cloud/<vm name>/creating``. The payload contains the names of the VM,
profile, and provider.

A set of kwargs is then usually created, to describe the parameters required
by the cloud host to request the virtual machine.

An event is then fired to state that a virtual machine is about to be requested.
It is tagged as ``salt/cloud/<vm name>/requesting``. The payload contains most
or all of the parameters that will be sent to the cloud host. Any private
information (such as passwords) should not be sent in the event.

After a request is made, a set of deploy kwargs will be generated. These will
be used to install Salt on the target machine. Windows options are supported
at this point, and should be generated, even if the cloud host does not
currently support Windows. This will save time in the future if the host
does eventually decide to support Windows.

An event is then fired to state that the deploy process is about to begin. This
event is tagged ``salt/cloud/<vm name>/deploying``. The payload for the event
will contain a set of deploy kwargs, useful for debugging purposed. Any private
data, including passwords and keys (including public keys) should be stripped
from the deploy kwargs before the event is fired.

If any Windows options have been passed in, the
``salt.utils.cloud.deploy_windows()`` function will be called. Otherwise, it
will be assumed that the target is a Linux or Unix machine, and the
``salt.utils.cloud.deploy_script()`` will be called.

Both of these functions will wait for the target machine to become available,
then the necessary port to log in, then a successful login that can be used to
install Salt. Minion configuration and keys will then be uploaded to a temporary
directory on the target by the appropriate function. On a Windows target, the
Windows Minion Installer will be run in silent mode. On a Linux/Unix target, a
deploy script (``bootstrap-salt.sh``, by default) will be run, which will
auto-detect the operating system, and install Salt using its native package
manager. These do not need to be handled by the developer in the cloud module.

The ``salt.utils.cloud.validate_windows_cred()`` function has been extended to
take the number of retries and retry_delay parameters in case a specific cloud
host has a delay between providing the Windows credentials and the
credentials being available for use.  In their ``create()`` function, or as
a sub-function called during the creation process, developers should use the
``win_deploy_auth_retries`` and ``win_deploy_auth_retry_delay`` parameters from
the provider configuration to allow the end-user the ability to customize the
number of tries and delay between tries for their particular host.

After the appropriate deploy function completes, a final event is fired
which describes the virtual machine that has just been created. This event is
tagged ``salt/cloud/<vm name>/created``. The payload contains the names of the
VM, profile, and provider.

Finally, a dict (queried from the provider) which describes the new virtual
machine is returned to the user. Because this data is not fired on the event
bus it can, and should, return any passwords that were returned by the cloud
host. In some cases (for example, Rackspace), this is the only time that
the password can be queried by the user; post-creation queries may not contain
password information (depending upon the host).

The libcloudfuncs Functions
---------------------------
A number of other functions are required for all cloud hosts. However, with
libcloud-based modules, these are all provided for free by the libcloudfuncs
library. The following two lines set up the imports:

.. code-block:: python

    from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
    import salt.utils.functools

And then a series of declarations will make the necessary functions available
within the cloud module.

.. code-block:: python

    get_size = salt.utils.functools.namespaced_function(get_size, globals())
    get_image = salt.utils.functools.namespaced_function(get_image, globals())
    avail_locations = salt.utils.functools.namespaced_function(avail_locations, globals())
    avail_images = salt.utils.functools.namespaced_function(avail_images, globals())
    avail_sizes = salt.utils.functools.namespaced_function(avail_sizes, globals())
    script = salt.utils.functools.namespaced_function(script, globals())
    destroy = salt.utils.functools.namespaced_function(destroy, globals())
    list_nodes = salt.utils.functools.namespaced_function(list_nodes, globals())
    list_nodes_full = salt.utils.functools.namespaced_function(list_nodes_full, globals())
    list_nodes_select = salt.utils.functools.namespaced_function(list_nodes_select, globals())
    show_instance = salt.utils.functools.namespaced_function(show_instance, globals())

If necessary, these functions may be replaced by removing the appropriate
declaration line, and then adding the function as normal.

These functions are required for all cloud modules, and are described in detail
in the next section.


Non-Libcloud Based Modules
==========================
In some cases, using libcloud is not an option. This may be because libcloud has
not yet included the necessary driver itself, or it may be that the driver that
is included with libcloud does not contain all of the necessary features
required by the developer. When this is the case, some or all of the functions
in ``libcloudfuncs`` may be replaced. If they are all replaced, the libcloud
imports should be absent from the Salt Cloud module.

A good example of a non-libcloud driver is the DigitalOcean driver:

https://github.com/saltstack/salt/tree/|repo_primary_branch|/salt/cloud/clouds/digitalocean.py

The ``create()`` Function
-------------------------
The ``create()`` function must be created as described in the libcloud-based
module documentation.

The get_size() Function
-----------------------
This function is only necessary for libcloud-based modules, and does not need
to exist otherwise.

The get_image() Function
------------------------
This function is only necessary for libcloud-based modules, and does not need
to exist otherwise.

The avail_locations() Function
------------------------------
This function returns a list of locations available, if the cloud host uses
multiple data centers. It is not necessary if the cloud host uses only one
data center. It is normally called using the ``--list-locations`` option.

.. code-block:: bash

    salt-cloud --list-locations my-cloud-provider

The avail_images() Function
---------------------------
This function returns a list of images available for this cloud provider. There
are not currently any known cloud providers that do not provide this
functionality, though they may refer to images by a different name (for example,
"templates"). It is normally called using the ``--list-images`` option.

.. code-block:: bash

    salt-cloud --list-images my-cloud-provider

The avail_sizes() Function
--------------------------
This function returns a list of sizes available for this cloud provider.
Generally, this refers to a combination of RAM, CPU, and/or disk space. This
functionality may not be present on some cloud providers. For example, the
Parallels module breaks down RAM, CPU, and disk space into separate options,
whereas in other providers, these options are baked into the image. It is
normally called using the ``--list-sizes`` option.

.. code-block:: bash

    salt-cloud --list-sizes my-cloud-provider

The script() Function
---------------------
This function builds the deploy script to be used on the remote machine.  It is
likely to be moved into the ``salt.utils.cloud`` library in the near future, as
it is very generic and can usually be copied wholesale from another module. An
excellent example is in the Azure driver.

The destroy() Function
----------------------
This function irreversibly destroys a virtual machine on the cloud provider.
Before doing so, it should fire an event on the Salt event bus. The tag for this
event is ``salt/cloud/<vm name>/destroying``. Once the virtual machine has been
destroyed, another event is fired. The tag for that event is
``salt/cloud/<vm name>/destroyed``.

This function is normally called with the ``-d`` options:

.. code-block:: bash

    salt-cloud -d myinstance

The list_nodes() Function
-------------------------
This function returns a list of nodes available on this cloud provider, using
the following fields:

* id (str)
* image (str)
* size (str)
* state (str)
* private_ips (list)
* public_ips (list)

No other fields should be returned in this function, and all of these fields
should be returned, even if empty. The private_ips and public_ips fields should
always be of a list type, even if empty, and the other fields should always be
of a str type. This function is normally called with the ``-Q`` option:

.. code-block:: bash

    salt-cloud -Q

The list_nodes_full() Function
------------------------------
All information available about all nodes should be returned in this function.
The fields in the list_nodes() function should also be returned, even if they
would not normally be provided by the cloud provider. This is because some
functions both within Salt and 3rd party will break if an expected field is not
present. This function is normally called with the ``-F`` option:

.. code-block:: bash

    salt-cloud -F

The list_nodes_select() Function
--------------------------------
This function returns only the fields specified in the ``query.selection``
option in ``/etc/salt/cloud``. Because this function is so generic, all of the
heavy lifting has been moved into the ``salt.utils.cloud`` library.

A function to call ``list_nodes_select()`` still needs to be present. In
general, the following code can be used as-is:

.. code-block:: python

    def list_nodes_select(call=None):
        '''
        Return a list of the VMs that are on the provider, with select fields
        '''
        return salt.utils.cloud.list_nodes_select(
            list_nodes_full('function'), __opts__['query.selection'], call,
        )

However, depending on the cloud provider, additional variables may be required.
For instance, some modules use a ``conn`` object, or may need to pass other
options into ``list_nodes_full()``. In this case, be sure to update the function
appropriately:

.. code-block:: python

    def list_nodes_select(conn=None, call=None):
        '''
        Return a list of the VMs that are on the provider, with select fields
        '''
        if not conn:
            conn = get_conn()   # pylint: disable=E0602

        return salt.utils.cloud.list_nodes_select(
            list_nodes_full(conn, 'function'),
            __opts__['query.selection'],
            call,
        )

This function is normally called with the ``-S`` option:

.. code-block:: bash

    salt-cloud -S

The show_instance() Function
----------------------------
This function is used to display all of the information about a single node
that is available from the cloud provider. The simplest way to provide this is
usually to call ``list_nodes_full()``, and return just the data for the
requested node. It is normally called as an action:

.. code-block:: bash

    salt-cloud -a show_instance myinstance


Actions and Functions
=====================
Extra functionality may be added to a cloud provider in the form of an
``--action`` or a ``--function``. Actions are performed against a cloud
instance/virtual machine, and functions are performed against a cloud provider.

Actions
-------
Actions are calls that are performed against a specific instance or virtual
machine. The ``show_instance`` action should be available in all cloud modules.
Actions are normally called with the ``-a`` option:

.. code-block:: bash

    salt-cloud -a show_instance myinstance

Actions must accept a ``name`` as a first argument, may optionally support any
number of kwargs as appropriate, and must accept an argument of ``call``, with
a default of ``None``.

Before performing any other work, an action should normally verify that it has
been called correctly. It may then perform the desired feature, and return
useful information to the user. A basic action looks like:

.. code-block:: python

    def show_instance(name, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    return _get_node(name)

Please note that generic kwargs, if used, are passed through to actions as
``kwargs`` and not ``**kwargs``. An example of this is seen in the Functions
section.

Functions
---------
Functions are called that are performed against a specific cloud provider. An
optional function that is often useful is ``show_image``, which describes an
image in detail. Functions are normally called with the ``-f`` option:

.. code-block:: bash

    salt-cloud -f show_image my-cloud-provider image='Ubuntu 13.10 64-bit'

A function may accept any number of kwargs as appropriate, and must accept an
argument of ``call`` with a default of ``None``.

Before performing any other work, a function should normally verify that it has
been called correctly. It may then perform the desired feature, and return
useful information to the user. A basic function looks like:

.. code-block:: python

    def show_image(kwargs, call=None):
        '''
        Show the details from EC2 concerning an AMI
        '''
        if call != 'function':
            raise SaltCloudSystemExit(
                'The show_image action must be called with -f or --function.'
            )

        params = {'ImageId.1': kwargs['image'],
                  'Action': 'DescribeImages'}
        result = query(params)
        log.info(result)

        return result

Take note that generic kwargs are passed through to functions as ``kwargs`` and
not ``**kwargs``.
