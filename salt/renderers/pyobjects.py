# -*- coding: utf-8 -*-
'''
:maintainer: Evan Borgstrom <evan@borgstrom.ca>

Python renderer that includes a Pythonic Object based interface

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
using the built-in Python renderer with the exception that pyobjects takes
care of creating an object for each of the available states on the minion.
Each state is represented by an object that is the capitalized version of it's
name (ie. ``File``, ``Service``, ``User``, etc), and these objects expose all
of their available state functions (ie. ``File.managed``,  ``Service.running``,
etc).

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

To include other states use the Include() function. It takes one name per
state to include.

To extend another state use the Extend() function on the name when creating
a state.

.. code-block:: python
   :linenos:
    #!pyobjects

    Include('http', 'ssh')

    Service.running(Extend('apache'),
                    watch=[{'file': '/etc/httpd/extra/httpd-vhosts.conf'}])
'''

import logging

from salt.loader import states
from salt.utils.pyobjects import StateFactory, StateRegistry

log = logging.getLogger(__name__)


def render(template, saltenv='base', sls='',
           tmplpath=None, rendered_sls=None,
           _states=None, **kwargs):

    _registry = StateRegistry()
    if _states is None:
        _states = states(__opts__, __salt__)

    # build our list of states and functions
    _st_funcs = {}
    for func in _states:
        (mod, func) = func.split(".")
        if mod not in _st_funcs:
            _st_funcs[mod] = []
        _st_funcs[mod].append(func)

    # create our StateFactory objects
    for mod in _st_funcs:
        _st_funcs[mod].sort()
        mod_upper = mod.capitalize()
        mod_cmd = "%s = StateFactory('%s', registry=_registry, valid_funcs=['%s'])" % (
            mod_upper, mod,
            "','".join(_st_funcs[mod])
        )
        exec(mod_cmd)

    # add our Include and Extend functions
    Include = _registry.include
    Extend = _registry.make_extend

    # for convenience
    try:
        pillar = __pillar__
        grains = __grains__
        salt = __salt__
    except NameError:
        pass

    exec(template.read())

    return _registry.salt_data()
