.. _resources-authoring-packaging:

=================================
Packaging as a Salt extension
=================================

Once your resource type is more than a quick experiment, ship it as a
Salt extension rather than carrying it inside core Salt. The framework
is designed so an extension's resource types are
indistinguishable-at-runtime from in-tree ones: same loader, same
targeting, same merge semantics.


Layout
======

Mirror the in-tree layout under your extension's package path. Given an
extension called ``saltext-widgets``::

    saltext-widgets/
        pyproject.toml
        src/
            saltext/
                widgets/
                    __init__.py
                    resources/
                        __init__.py
                        widget/
                            __init__.py            ← connection module
                            modules/
                                __init__.py
                                test.py
                            states/
                                __init__.py
                                widget.py
                            grains/
                                __init__.py
                                widget.py

Every directory containing Python files needs an ``__init__.py`` so
:py:func:`setuptools.find_packages` discovers them. Empty
``__init__.py`` is fine.


pyproject.toml entry point
==========================

The loader discovers extensions via the ``salt.loader`` entry point::

    [project]
    name = "saltext-widgets"
    version = "0.1.0"
    requires-python = ">=3.10"
    dependencies = ["salt>=3008"]

    [project.entry-points."salt.loader"]
    saltext.widgets = "saltext.widgets"

Salt's loader walks every package registered under ``salt.loader``,
looks for a ``resources/`` subdir, and includes any
``<package>/resources/<rtype>/{modules,states,grains}/`` directories
in its loader search path *ahead of* the standard salt locations.

No extra registration step. No "tell Salt about my type". Drop the
package on the managing minion, restart, and the type is discoverable.


Where the package gets installed
================================

Resource extensions need to be importable by **the managing minion's
Python interpreter** — the same one running ``salt-minion``. For an
onedir installation that's the bundled interpreter; for a system
install it's whatever ``salt-minion`` is shebanged with.

* Onedir: ``salt-pip install saltext-widgets``
* System: ``pip install saltext-widgets`` in the same environment as
  ``salt-minion``
* Container: bake the extension into your minion image; don't expect
  ``saltutil.pillar_refresh`` to install new types at runtime.


Discovering what shipped
========================

Once installed, the managing minion will load the type the next time
its pillar refresh discovers a matching entry. On the master,
``salt-run resource.list_grains`` confirms the minion registered
resources of the new type.


Distribution checklist
======================

When publishing the extension:

* ``pyproject.toml`` lists ``salt>=3008`` as a dependency.
* Each resource type ships at least one execution test — the dummy
  type is a fine template.
* The README documents the pillar shape the type expects (key names,
  required vs optional fields).
* If your type talks to a remote service, document the credentials
  model and how to wire pillar so secrets are decrypted at compile
  time, not stored in plaintext.


Working example
===============

`saltext-opsdev <https://github.com/saltstack/saltext-opsdev>`_ is the
canonical real-world example: it ships two resource types
(``starting_state``, ``nimbus_testbed``), per-type execution and state
overrides, and integration tests. Mirror its layout when in doubt.
