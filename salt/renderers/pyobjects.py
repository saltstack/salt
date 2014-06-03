# -*- coding: utf-8 -*-
'''
Python renderer that includes a Pythonic Object based interface

:maintainer: Evan Borgstrom <evan@borgstrom.ca>

Let's take a look at how you use pyobjects in a state file. Here's a quick
example that ensures the ``/tmp`` directory is in the correct state.

.. code-block:: python
   :linenos:

    #!pyobjects

    File.managed("/tmp", user='root', group='root', mode='1777')

Nice and Pythonic!

By using the "shebang" syntax to switch to the pyobjects renderer we can now
write our state data using an object based interface that should feel at home
to python developers. You can import any module and do anything that you'd
like (with caution, importing sqlalchemy, django or other large frameworks has
not been tested yet). Using the pyobjects renderer is exactly the same as
using the built-in Python renderer with the exception that pyobjects provides
you with an object based interface for generating state data.

Creating state data
^^^^^^^^^^^^^^^^^^^
Pyobjects takes care of creating an object for each of the available states on
the minion. Each state is represented by an object that is the CamelCase
version of it's name (ie. ``File``, ``Service``, ``User``, etc), and these
objects expose all of their available state functions (ie. ``File.managed``,
``Service.running``, etc).

The name of the state is split based upon underscores (``_``), then each part
is capitalized and finally the parts are joined back together.

Some examples:

* ``postgres_user`` becomes ``PostgresUser``
* ``ssh_known_hosts`` becomes ``SshKnownHosts``

Context Managers and requisites
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
How about something a little more complex. Here we're going to get into the
core of what makes pyobjects the best way to write states.

.. code-block:: python
   :linenos:

    #!pyobjects

    with Pkg.installed("nginx"):
        Service.running("nginx", enable=True)

        with Service("nginx", "watch_in"):
            File.managed("/etc/nginx/conf.d/mysite.conf",
                         owner='root', group='root', mode='0444',
                         source='salt://nginx/mysite.conf')


The objects that are returned from each of the magic method calls are setup to
be used a Python context managers (``with``) and when you use them as such all
declarations made within the scope will **automatically** use the enclosing
state as a requisite!

The above could have also been written use direct requisite statements as.

.. code-block:: python
   :linenos:

    #!pyobjects

    Pkg.installed("nginx")
    Service.running("nginx", enable=True, require=Pkg("nginx"))
    File.managed("/etc/nginx/conf.d/mysite.conf",
                 owner='root', group='root', mode='0444',
                 source='salt://nginx/mysite.conf',
                 watch_in=Service("nginx"))

You can use the direct requisite statement for referencing states that are
generated outside of the current file.

.. code-block:: python
   :linenos:

    #!pyobjects

    # some-other-package is defined in some other state file
    Pkg.installed("nginx", require=Pkg("some-other-package"))

The last thing that direct requisites provide is the ability to select which
of the SaltStack requisites you want to use (require, require_in, watch,
watch_in, use & use_in) when using the requisite as a context manager.

.. code-block:: python
   :linenos:

    #!pyobjects

    with Service("my-service", "watch_in"):
        ...

The above example would cause all declarations inside the scope of the context
manager to automatically have their ``watch_in`` set to
``Service("my-service")``.

Including and Extending
^^^^^^^^^^^^^^^^^^^^^^^

To include other states use the ``include()`` function. It takes one name per
state to include.

To extend another state use the ``extend()`` function on the name when creating
a state.

.. code-block:: python
   :linenos:

    #!pyobjects

    include('http', 'ssh')

    Service.running(extend('apache'),
                    watch=[File('/etc/httpd/extra/httpd-vhosts.conf')])

Salt object
^^^^^^^^^^^
In the spirit of the object interface for creating state data pyobjects also
provides a simple object interface to the ``__salt__`` object.

A function named ``salt`` exists in scope for your sls files and will dispatch
its attributes to the ``__salt__`` dictionary.

The following lines are functionally equivalent:

.. code-block:: python
   :linenos:

    #!pyobjects

    ret = salt.cmd.run(bar)
    ret = __salt__['cmd.run'](bar)

Pillar, grain & mine data
^^^^^^^^^^^^^^^^^^^^^^^^^
Pyobjects provides shortcut functions for calling ``pillar.get``,
``grains.get`` & ``mine.get`` on the ``__salt__`` object. This helps maintain
the readability of your state files.

Each type of data can be access by a function of the same name: ``pillar()``,
``grains()`` and ``mine()``.

The following pairs of lines are functionally equivalent:

.. code-block:: python
   :linenos:

    #!pyobjects

    value = pillar('foo:bar:baz', 'qux')
    value = __salt__['pillar.get']('foo:bar:baz', 'qux')

    value = grains('pkg:apache')
    value = __salt__['grains.get']('pkg:apache')

    value = mine('os:Fedora', 'network.interfaces', 'grain')
    value = __salt__['mine.get']('os:Fedora', 'network.interfaces', 'grain')


Map Data
^^^^^^^^
When building complex states or formulas you often need a way of building up a
map of data based on grain data. The most common use of this is tracking the
package and service name differences between distributions.

To build map data using pyobjects we provide a class named Map that you use to
build your own classes with inner classes for each set of values for the
different grain matches.

To access the data in the map you simply access the attribute name on the base
class that is extending Map.

.. code-block:: python
   :linenos:

    #!pyobjects

    class Samba(Map):
        merge = 'samba:lookup'

        class Debian:
            server = 'samba'
            client = 'samba-client'
            service = 'samba'

        class Ubuntu:
            __grain__ = 'os'
            service = 'smbd'

        class RedHat:
            server = 'samba'
            client = 'samba'
            service = 'smb'


    with Pkg.installed("samba", names=[Samba.server, Samba.client]):
        Service.running("samba", name=Samba.service)

TODO
^^^^
* Interface for working with reactor files
* Allow for imports based on the salt file root
'''

import logging
import sys

from salt.loader import _create_loader
from salt.utils.pyobjects import (Registry, StateFactory, SaltObject, Map)

log = logging.getLogger(__name__)

try:
    __context__['pyobjects_loaded'] = True
except NameError:
    __context__ = {}


def load_states():
    '''
    This loads our states into the salt __context__
    '''
    states = {}

    # the loader expects to find pillar & grian data
    __opts__['grains'] = __grains__
    __opts__['pillar'] = __pillar__

    # we need to build our own loader so that we can process the virtual names
    # in our own way.
    load = _create_loader(__opts__, 'states', 'states')
    load.load_modules()
    for mod in load.modules:
        module_name = mod.__name__.rsplit('.', 1)[-1]

        (virtual_ret, virtual_name) = load.process_virtual(mod, module_name)

        # if the module returned a True value and a new name use that
        # otherwise use the default module name
        if virtual_ret and virtual_name != module_name:
            module_name = virtual_name

        # load our functions from the module, pass None in as the module_name
        # so that our function names come back unprefixed
        states[module_name] = load.load_functions(mod, None)

    __context__['pyobjects_states'] = states


def render(template, saltenv='base', sls='', **kwargs):
    if 'pyobjects_states' not in __context__:
        load_states()

    # these hold the scope that our sls file will be executed with
    _globals = {}
    _locals = {}

    # create our StateFactory objects
    mod_globals = {'StateFactory': StateFactory}
    for mod in __context__['pyobjects_states']:
        mod_locals = {}
        mod_camel = ''.join([
            part.capitalize()
            for part in mod.split('_')
        ])
        mod_cmd = "%s = StateFactory('%s', valid_funcs=['%s'])" % (
            mod_camel, mod,
            "','".join(__context__['pyobjects_states'][mod].keys())
        )
        if sys.version > 3:
            exec(mod_cmd, mod_globals, mod_locals)
        else:
            exec mod_cmd in mod_globals, mod_locals
        _globals[mod_camel] = mod_locals[mod_camel]

    # add our include and extend functions
    _globals['include'] = Registry.include
    _globals['extend'] = Registry.make_extend

    # add our map class
    Map.__salt__ = __salt__
    _globals['Map'] = Map

    # add some convenience methods to the global scope as well as the "dunder"
    # format of all of the salt objects
    try:
        _globals.update({
            # salt, pillar & grains all provide shortcuts or object interfaces
            'salt': SaltObject(__salt__),
            'pillar': __salt__['pillar.get'],
            'grains': __salt__['grains.get'],
            'mine': __salt__['mine.get'],

            # the "dunder" formats are still available for direct use
            '__salt__': __salt__,
            '__pillar__': __pillar__,
            '__grains__': __grains__
        })
    except NameError:
        pass

    # now exec our template using our created scopes
    # in py3+ exec is a function, prior to that it is a statement
    if sys.version > 3:
        exec(template.read(), _globals, _locals)
    else:
        exec template.read() in _globals, _locals

    return Registry.salt_data()
