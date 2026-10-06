.. _resources-authoring-execution:

==========================
Execution module overrides
==========================

The ``modules/`` directory under a resource type holds **execution
module overrides**. Each file replaces one slot in the standard Salt
execution-module surface — the file's name (minus ``.py``) becomes the
slot, so ``modules/cmd.py`` overrides the ``cmd`` virtualname,
``modules/pkg.py`` overrides ``pkg``, and so on.

When a publish dispatches to a resource of this type, ``__salt__``
first looks in ``<rtype>/modules/`` and falls back to ``salt/modules/``
for anything not overridden. This is the whole point of the framework
— you can give your type its own ``cmd.run`` (or ``pkg.installed``,
or anything else) without forking the standard modules and without
touching ``__virtual__``.


When to add an override
=======================

Add an override when "the standard ``cmd.run`` would do the wrong
thing on this resource". Typically that means:

* The resource isn't a local machine — ``cmd.run`` needs to dispatch
  over SSH, an API, a serial connection, etc.
* The "package manager" semantics differ — a Kubernetes resource's
  ``pkg.installed`` is really ``kubectl apply``.
* The standard module assumes filesystem layout that doesn't exist
  on the resource — ``file.managed`` writing to ``/etc/`` of a thing
  that has no ``/etc/``.

Don't add an override when:

* Your type-specific operation has a fundamentally new name. Just put
  it as a function in ``__init__.py`` (or in your own
  ``modules/widget.py``) — the framework loads everything you put
  under ``modules/``, not just slots that exist in core.


Dunders inside an override module
=================================

The same loader dunders as a connection module, plus a few resource
specifics:

``__resource__``
   Always set in execution-module code — every call goes through the
   per-resource dispatch path. ``{"type": ..., "id": ...}``.

``__grains__``
   The **resource's** grain dict — what ``grains()`` returned for
   *this* resource. Not the managing minion's grains.

``__resource_funcs__``
   The connection module's namespace, indexed by ``<rtype>.<fname>``.
   So if the connection module defines ``def ping()``, you can call
   it from inside ``modules/test.py`` as
   ``__resource_funcs__["widget.ping"]()``. This is the canonical way
   to reach the connection module's helpers from an override.

``__minion__``
   The **managing minion's** standard execution-module loader. Use
   this when an override genuinely needs to reach the host (read a
   file on disk, run a local command, query the managing minion's
   grains). For most overrides you won't need it.

``__salt__``
   In an override, ``__salt__`` is the **merged per-resource loader**
   — overrides for slots that exist plus standard modules for slots
   that don't. Calling ``__salt__["cmd.run"]`` inside ``modules/pkg.py``
   dispatches to ``modules/cmd.py`` if you've overridden ``cmd``, or
   to the standard ``salt.modules.cmdmod.run`` if you haven't.


Pattern: override one function in a standard module
====================================================

You want ``pkg.install`` to actually do something for your resource
type, but the rest of the ``pkg.*`` surface (``pkg.list_pkgs``,
``pkg.version``) is fine running on the managing minion. Put just the
function you need in ``modules/pkg.py``::

    def install(name=None, pkgs=None, **kwargs):
        return __resource_funcs__["widget.package_install"](name=name)

Nothing else. Standard ``salt.modules.aptpkg`` continues to provide
the rest of the ``pkg.*`` surface for this resource.

The slot precedence is per-function: directory order picks the
override if the function exists in the override module, otherwise the
standard module fills the slot.


Pattern: re-export the standard module
======================================

The reverse case — you want **most** of an override slot to mirror
the standard module, but the standard module is the one that needs to
run with the *per-resource* loader context. Use
:py:func:`salt.utils.functools.namespaced_function` to re-export
without copying::

    # modules/state.py
    import salt.utils.functools
    import salt.modules.state as _src

    sls       = salt.utils.functools.namespaced_function(_src.sls, globals())
    apply_    = salt.utils.functools.namespaced_function(_src.apply_, globals())
    highstate = salt.utils.functools.namespaced_function(_src.highstate, globals())
    single    = salt.utils.functools.namespaced_function(_src.single, globals())

    __func_alias__ = {"apply_": "apply"}

``namespaced_function`` copies the function object into your module's
globals so ``__salt__``, ``__opts__``, and friends resolve to the
*per-resource* loader at call time. A naive ``from salt.modules.state
import sls`` keeps the original module's globals and runs against the
managing minion's loader — which is what you don't want.

The :py:mod:`salt.resources.ssh.modules.state` module ships with Salt
as a worked example.


Pattern: delegate to the connection module
==========================================

The simplest override is one line each, forwarding to functions you
wrote in ``__init__.py``::

    # modules/test.py
    def ping():
        return __resource_funcs__["widget.ping"]()

    def echo(text):
        return __resource_funcs__["widget.echo"](text)

This keeps the actual connection logic in one place (the connection
module) and the override file purely about *slot binding*.


Mistakes to avoid
=================

* **Importing globals at module load time**. Dunders like ``__salt__``
  and ``__resource__`` are :py:class:`~salt.loader.context.NamedLoaderContext`
  proxies; they're only valid inside function bodies. Don't capture
  them at import time.
* **Re-defining** ``__virtualname__``. The file's location enforces
  the slot — overriding the virtualname will only confuse the loader.
  Just name the file after the slot you want.
* **Bypassing the loader.** ``import salt.modules.cmdmod`` and calling
  ``cmdmod.run()`` directly skips the dunder injection and the
  per-resource context. Always go through ``__salt__["cmd.run"]``
  inside an override.
* **Forgetting to forward kwargs.** State engines pass ``__pub_*``
  dunders into module calls; pure forwarding overrides should accept
  ``**kwargs`` and pass them along.
