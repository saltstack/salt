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
using the built-in Python renderer with the exception that the NaCl renderer
takes care of creating an object for each of the available states on the minion.
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
'''

import logging
import traceback

from salt.exceptions import SaltRenderError

log = logging.getLogger("pyobjects")


def render(template, saltenv='base', sls='',
           tmplpath=None, rendered_sls=None, **kwargs):

    from salt.loader import states
    from salt.utils.pyobjects import StateFactory, StateRegistry

    _registry = StateRegistry()
    try:
        _states = states(__opts__, __salt__)
    except NameError:
        log.warning("__opts__ and __salt__ are not defined, "
                    "setting up a local config & minion")

        # this happens during testing, set it up
        from salt.config import minion_config
        from salt.loader import states
        from salt.minion import SMinion
        _config = minion_config(None)
        _config['file_client'] = 'local'
        _minion = SMinion(_config)
        _states = states(_config, _minion.functions)

        __pillar__ = {}
        __grains__ = {}
        __salt__ = {}

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

    try:
        # for convenience
        pillar = __pillar__
        grains = __grains__
        salt = __salt__

        exec(template.read())
    except Exception:
        trb = traceback.format_exc()
        raise SaltRenderError(trb)

    return _registry.salt_data()
