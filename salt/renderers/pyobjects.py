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
                    watch=[{'file': '/etc/httpd/extra/httpd-vhosts.conf'}])

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


TODO
^^^^
* Interface for working with reactor files
'''

import logging
import sys

from salt.utils.pyobjects import StateRegistry, StateFactory, SaltObject

log = logging.getLogger(__name__)


def render(template, saltenv='base', sls='',
           tmplpath=None, rendered_sls=None,
           _states=None, **kwargs):

    _globals = {}
    _locals = {}

    _registry = StateRegistry()
    if _states is None:
        try:
            _states = __states__
        except NameError:
            from salt.loader import states
            __opts__['grains'] = __grains__
            __opts__['pillar'] = __pillar__
            _states = states(__opts__, __salt__)

    # build our list of states and functions
    _st_funcs = {}
    for func in _states:
        (mod, func) = func.split(".")
        if mod not in _st_funcs:
            _st_funcs[mod] = []
        _st_funcs[mod].append(func)

    # create our StateFactory objects
    _st_globals = {'StateFactory': StateFactory, '_registry': _registry}
    for mod in _st_funcs:
        _st_locals = {}
        _st_funcs[mod].sort()
        mod_camel = ''.join([
            part.capitalize()
            for part in mod.split('_')
        ])
        mod_cmd = "%s = StateFactory('%s', registry=_registry, valid_funcs=['%s'])" % (
            mod_camel, mod,
            "','".join(_st_funcs[mod])
        )
        if sys.version > 3:
            exec(mod_cmd, _st_globals, _st_locals)
        else:
            exec mod_cmd in _st_globals, _st_locals
        _globals[mod_camel] = _st_locals[mod_camel]

    # add our Include and Extend functions
    _globals['include'] = _registry.include
    _globals['extend'] = _registry.make_extend

    # for convenience
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

    if sys.version > 3:
        exec(template.read(), _globals, _locals)
    else:
        exec template.read() in _globals, _locals

    return _registry.salt_data()
