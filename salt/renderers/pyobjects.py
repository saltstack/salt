# -*- coding: utf-8 -*-
"""
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
-------------------

Pyobjects takes care of creating an object for each of the available states on
the minion. Each state is represented by an object that is the CamelCase
version of its name (i.e. ``File``, ``Service``, ``User``, etc), and these
objects expose all of their available state functions (i.e. ``File.managed``,
``Service.running``, etc).

The name of the state is split based upon underscores (``_``), then each part
is capitalized and finally the parts are joined back together.

Some examples:

* ``postgres_user`` becomes ``PostgresUser``
* ``ssh_known_hosts`` becomes ``SshKnownHosts``

Context Managers and requisites
-------------------------------

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
-----------------------

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
--------------------------------

Like any Python project that grows you will likely reach a point where you want
to create reusability in your state tree and share objects between state files,
Map Data (described below) is a perfect example of this.

To facilitate this Python's ``import`` statement has been augmented to allow
for a special case when working with a Salt state tree. If you specify a Salt
url (``salt://...``) as the target for importing from then the pyobjects
renderer will take care of fetching the file for you, parsing it with all of
the pyobjects features available and then place the requested objects in the
global scope of the template being rendered.

This works for all types of import statements; ``import X``,
``from X import Y``, and ``from X import Y as Z``.

.. code-block:: python
   :linenos:

    #!pyobjects

    import salt://myfile.sls
    from salt://something/data.sls import Object
    from salt://something/data.sls import Object as Other


See the Map Data section for a more practical use.

Caveats:

* Imported objects are ALWAYS put into the global scope of your template,
  regardless of where your import statement is.


Salt object
-----------

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
---------------------------------

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
--------

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
        # NOTE: priority is new to 2017.7.0
        priority = ('os_family', 'os')

        class Ubuntu:
            __grain__ = 'os'
            service = 'smbd'

        class Debian:
            server = 'samba'
            client = 'samba-client'
            service = 'samba'

        class RHEL:
            __match__ = 'RedHat'
            server = 'samba'
            client = 'samba'
            service = 'smb'

.. note::
    By default, the ``os_family`` grain will be used as the target for
    matching. This can be overridden by specifying a ``__grain__`` attribute.

    If a ``__match__`` attribute is defined for a given class, then that value
    will be matched against the targeted grain, otherwise the class name's
    value will be be matched.

    Given the above example, the following is true:

    1. Minions with an ``os_family`` of **Debian** will be assigned the
       attributes defined in the **Debian** class.
    2. Minions with an ``os`` grain of **Ubuntu** will be assigned the
       attributes defined in the **Ubuntu** class.
    3. Minions with an ``os_family`` grain of **RedHat** will be assigned the
       attributes defined in the **RHEL** class.

    That said, sometimes a minion may match more than one class. For instance,
    in the above example, Ubuntu minions will match both the **Debian** and
    **Ubuntu** classes, since Ubuntu has an ``os_family`` grain of **Debian**
    and an ``os`` grain of **Ubuntu**. As of the 2017.7.0 release, the order is
    dictated by the order of declaration, with classes defined later overriding
    earlier ones. Additionally, 2017.7.0 adds support for explicitly defining
    the ordering using an optional attribute called ``priority``.

    Given the above example, ``os_family`` matches will be processed first,
    with ``os`` matches processed after. This would have the effect of
    assigning ``smbd`` as the ``service`` attribute on Ubuntu minions. If the
    ``priority`` item was not defined, or if the order of the items in the
    ``priority`` tuple were reversed, Ubuntu minions would have a ``service``
    attribute of ``samba``, since ``os_family`` matches would have been
    processed second.

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

"""
# TODO: Interface for working with reactor files

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re

import salt.loader
import salt.utils.files

# Import Salt Libs
from salt.ext import six
from salt.fileclient import get_file_client
from salt.utils.pyobjects import Map, Registry, SaltObject, StateFactory

# our import regexes
FROM_RE = re.compile(r"^\s*from\s+(salt:\/\/.*)\s+import (.*)$")
IMPORT_RE = re.compile(r"^\s*import\s+(salt:\/\/.*)$")
FROM_AS_RE = re.compile(r"^(.*) as (.*)$")

log = logging.getLogger(__name__)

try:
    __context__["pyobjects_loaded"] = True
except NameError:
    __context__ = {}


class PyobjectsModule(object):
    """This provides a wrapper for bare imports."""

    def __init__(self, name, attrs):
        self.name = name
        self.__dict__ = attrs

    def __repr__(self):
        return "<module '{0!s}' (pyobjects)>".format(self.name)


def load_states():
    """
    This loads our states into the salt __context__
    """
    states = {}

    # the loader expects to find pillar & grain data
    __opts__["grains"] = salt.loader.grains(__opts__)
    __opts__["pillar"] = __pillar__
    lazy_utils = salt.loader.utils(__opts__)
    lazy_funcs = salt.loader.minion_mods(__opts__, utils=lazy_utils)
    lazy_serializers = salt.loader.serializers(__opts__)
    lazy_states = salt.loader.states(__opts__, lazy_funcs, lazy_utils, lazy_serializers)

    # TODO: some way to lazily do this? This requires loading *all* state modules
    for key, func in six.iteritems(lazy_states):
        if "." not in key:
            continue
        mod_name, func_name = key.split(".", 1)
        if mod_name not in states:
            states[mod_name] = {}
        states[mod_name][func_name] = func

    __context__["pyobjects_states"] = states


def render(template, saltenv="base", sls="", salt_data=True, **kwargs):
    if "pyobjects_states" not in __context__:
        load_states()

    # these hold the scope that our sls file will be executed with
    _globals = {}

    # create our StateFactory objects
    mod_globals = {"StateFactory": StateFactory}
    for mod in __context__["pyobjects_states"]:
        mod_locals = {}
        mod_camel = "".join([part.capitalize() for part in mod.split("_")])
        valid_funcs = "','".join(__context__["pyobjects_states"][mod])
        mod_cmd = "{0} = StateFactory('{1!s}', valid_funcs=['{2}'])".format(
            mod_camel, mod, valid_funcs
        )
        six.exec_(mod_cmd, mod_globals, mod_locals)

        _globals[mod_camel] = mod_locals[mod_camel]

    # add our include and extend functions
    _globals["include"] = Registry.include
    _globals["extend"] = Registry.make_extend

    # add our map class
    Map.__salt__ = __salt__
    _globals["Map"] = Map

    # add some convenience methods to the global scope as well as the "dunder"
    # format of all of the salt objects
    try:
        _globals.update(
            {
                # salt, pillar & grains all provide shortcuts or object interfaces
                "salt": SaltObject(__salt__),
                "pillar": __salt__["pillar.get"],
                "grains": __salt__["grains.get"],
                "mine": __salt__["mine.get"],
                "config": __salt__["config.get"],
                # the "dunder" formats are still available for direct use
                "__salt__": __salt__,
                "__pillar__": __pillar__,
                "__grains__": __grains__,
            }
        )
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
    Registry.enabled = False

    def process_template(template):
        template_data = []
        # Do not pass our globals to the modules we are including and keep the root _globals untouched
        template_globals = dict(_globals)
        for line in template.readlines():
            line = line.rstrip("\r\n")
            matched = False
            for RE in (IMPORT_RE, FROM_RE):
                matches = RE.match(line)
                if not matches:
                    continue

                import_file = matches.group(1).strip()
                try:
                    imports = matches.group(2).split(",")
                except IndexError:
                    # if we don't have a third group in the matches object it means
                    # that we're importing everything
                    imports = None

                state_file = client.cache_file(import_file, saltenv)
                if not state_file:
                    raise ImportError(
                        "Could not find the file '{0}'".format(import_file)
                    )

                with salt.utils.files.fopen(state_file) as state_fh:
                    state_contents, state_globals = process_template(state_fh)
                six.exec_(state_contents, state_globals)

                # if no imports have been specified then we are being imported as: import salt://foo.sls
                # so we want to stick all of the locals from our state file into the template globals
                # under the name of the module -> i.e. foo.MapClass
                if imports is None:
                    import_name = os.path.splitext(os.path.basename(state_file))[0]
                    template_globals[import_name] = PyobjectsModule(
                        import_name, state_globals
                    )
                else:
                    for name in imports:
                        name = alias = name.strip()

                        matches = FROM_AS_RE.match(name)
                        if matches is not None:
                            name = matches.group(1).strip()
                            alias = matches.group(2).strip()

                        if name not in state_globals:
                            raise ImportError(
                                "'{0}' was not found in '{1}'".format(name, import_file)
                            )
                        template_globals[alias] = state_globals[name]

                matched = True
                break

            if not matched:
                template_data.append(line)

        return "\n".join(template_data), template_globals

    # process the template that triggered the render
    final_template, final_globals = process_template(template)
    _globals.update(final_globals)

    # re-enable the registry
    Registry.enabled = True

    # now exec our template using our created scopes
    six.exec_(final_template, _globals)

    return Registry.salt_data()
