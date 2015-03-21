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
version of its name (ie. ``File``, ``Service``, ``User``, etc), and these
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
core of how to use pyobjects to write states.

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


Importing from other state files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Like any Python project that grows you will likely reach a point where you want
to create reusability in your state tree and share objects between state files,
Map Data (described below) is a perfect example of this.

To facilitate this Python's ``import`` statement has been augmented to allow
for a special case when working with a Salt state tree. If you specify a Salt
url (``salt://...``) as the target for importing from then the pyobjects
renderer will take care of fetching the file for you, parsing it with all of
the pyobjects features available and then place the requested objects in the
global scope of the template being rendered.

This works for both types of import statements, ``import X`` and
``from X import Y``.

.. code-block:: python
   :linenos:

    #!pyobjects

    import salt://myfile.sls
    from salt://something/data.sls import Object


See the Map Data section for a more practical use.

Caveats:

* You cannot use the ``as`` syntax, you can only import objects using their
  existing name.

* Imported objects are ALWAYS put into the global scope of your template,
  regardless of where your import statement is.

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

Pillar, grain, mine & config data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Pyobjects provides shortcut functions for calling ``pillar.get``,
``grains.get``, ``mine.get`` & ``config.get`` on the ``__salt__`` object. This
helps maintain the readability of your state files.

Each type of data can be access by a function of the same name: ``pillar()``,
``grains()``, ``mine()`` and ``config()``.

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

    value = config('foo:bar:baz', 'qux')
    value = __salt__['config.get']('foo:bar:baz', 'qux')


Map Data
^^^^^^^^
When building complex states or formulas you often need a way of building up a
map of data based on grain data. The most common use of this is tracking the
package and service name differences between distributions.

To build map data using pyobjects we provide a class named Map that you use to
build your own classes with inner classes for each set of values for the
different grain matches.

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

To use this new data you can import it into your state file and then access
your attributes. To access the data in the map you simply access the attribute
name on the base class that is extending Map. Assuming the above Map was in the
file ``samba/map.sls``, you could do the following.

.. code-block:: python
   :linenos:

    #!pyobjects

    from salt://samba/map.sls import Samba

    with Pkg.installed("samba", names=[Samba.server, Samba.client]):
        Service.running("samba", name=Samba.service)

TODO
^^^^
* Interface for working with reactor files
'''

import logging
import re
import sys

import salt.utils
from salt.loader import _create_loader
from salt.fileclient import get_file_client
from salt.utils.pyobjects import Registry, StateFactory, SaltObject, Map

# our import regexes
FROM_RE = r'^\s*from\s+(salt:\/\/.*)\s+import (.*)$'
IMPORT_RE = r'^\s*import\s+(salt:\/\/.*)$'

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


def render(template, saltenv='base', sls='', salt_data=True, **kwargs):
    if 'pyobjects_states' not in __context__:
        load_states()

    # these hold the scope that our sls file will be executed with
    _globals = {}

    # create our StateFactory objects
    mod_globals = {'StateFactory': StateFactory}
    for mod in __context__['pyobjects_states']:
        mod_locals = {}
        mod_camel = ''.join([
            part.capitalize()
            for part in mod.split('_')
        ])
        valid_funcs = "','".join(
            __context__['pyobjects_states'][mod]
        )
        mod_cmd = "{0} = StateFactory('{1!s}', valid_funcs=['{2}'])".format(
            mod_camel,
            mod,
            valid_funcs
        )
        if sys.version_info[0] > 2:
            # in py3+ exec is a function
            exec(mod_cmd, mod_globals, mod_locals)
        else:
            # prior to that it is a statement
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
            'config': __salt__['config.get'],

            # the "dunder" formats are still available for direct use
            '__salt__': __salt__,
            '__pillar__': __pillar__,
            '__grains__': __grains__
        })
    except NameError:
        pass

    # if salt_data is not True then we just return the global scope we've
    # built instead of returning salt data from the registry
    if not salt_data:
        return _globals

    # this will be used to fetch any import files
    client = get_file_client(__opts__)

    # process our sls imports
    #
    # we allow pyobjects users to use a special form of the import statement
    # so that they may bring in objects from other files. while we do this we
    # disable the registry since all we're looking for here is python objects,
    # not salt state data
    template_data = []
    Registry.enabled = False
    for line in template.readlines():
        line = line.rstrip('\r\n')
        matched = False
        for RE in (IMPORT_RE, FROM_RE):
            matches = re.match(RE, line)
            if not matches:
                continue

            import_file = matches.group(1).strip()
            try:
                imports = matches.group(2).split(',')
            except IndexError:
                # if we don't have a third group in the matches object it means
                # that we're importing everything
                imports = None

            state_file = client.cache_file(import_file, saltenv)
            if not state_file:
                raise ImportError("Could not find the file {0!r}".format(import_file))

            with salt.utils.fopen(state_file) as f:
                state_contents = f.read()

            state_locals = {}
            if sys.version_info[0] > 2:
                # in py3+ exec is a function
                exec(state_contents, _globals, state_locals)
            else:
                # prior to that it is a statement
                exec state_contents in _globals, state_locals

            if imports is None:
                imports = state_locals.keys()

            for name in imports:
                name = name.strip()
                if name not in state_locals:
                    raise ImportError("{0!r} was not found in {1!r}".format(
                        name,
                        import_file
                    ))
                _globals[name] = state_locals[name]

            matched = True
            break

        if not matched:
            template_data.append(line)

    final_template = "\n".join(template_data)

    # re-enable the registry
    Registry.enabled = True

    # now exec our template using our created scopes
    if sys.version_info[0] > 2:
        # in py3+ exec is a function
        exec(final_template, _globals)
    else:
        # prior to that it is a statement
        exec final_template in _globals

    return Registry.salt_data()
