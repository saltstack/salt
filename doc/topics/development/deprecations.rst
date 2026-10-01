.. _deprecations:

================
Deprecating Code
================

Salt aims to be backwards compatible across release branches. When a feature
or API must be removed, deprecate it first - announce it in the docs, emit a
warning at runtime, and give users at least two feature releases to migrate
before deleting the code.

This page describes the three things to do every time you deprecate
something:

1. Mark it in the source docstring with ``.. deprecated::``.
2. Emit a runtime deprecation warning that pins a removal version.
3. Add a ``.deprecated.md`` changelog fragment.

The next release is named after the next element in the Periodic Table -
``master`` today is Potassium. Each tagged release branch (``3006.x``,
``3007.x``, ``3008.x``) carries the codename for that line.


Step 1: Mark the docstring
==========================

Add ``.. deprecated::`` to the docstring of the function, class, or module
being deprecated, and include the release number that introduced the
deprecation. State what to use instead.

.. code-block:: python

    def old_helper(value):
        """
        Return ``value`` capitalized.

        .. deprecated:: 3008.0
           Use :py:func:`new_helper` instead. ``old_helper`` will be removed
           in Salt 3010.0.
        """
        return new_helper(value)

The Sphinx output renders the directive as a yellow admonition so it is
visually obvious in the rendered docs.

If a single argument of an otherwise stable function is being deprecated,
note it in the argument's docstring section:

.. code-block:: python

    def configure(name, *, foo=None, bar=None):
        """
        Configure a thing.

        :param foo:
            .. deprecated:: 3008.0
               Use ``bar`` instead.
        """

For a brand new replacement, pair the ``.. deprecated::`` on the old API
with a matching ``.. versionadded::`` on the new one so readers can find the
crossover.


Step 2: Emit a runtime warning
==============================

The Salt project ships
:func:`salt.utils.versions.warn_until <salt.utils.versions.warn_until>` for
this. It logs a ``DeprecationWarning`` until Salt reaches the version you
pass; once that version ships, ``warn_until`` raises ``RuntimeError`` to
force developers to actually delete the code.

.. code-block:: python

    import salt.utils.versions


    def old_helper(value, *, legacy_mode=None):
        if legacy_mode is not None:
            salt.utils.versions.warn_until(
                3010,
                "The 'legacy_mode' argument to old_helper has been deprecated "
                "and will be removed in Salt {version}. Use new_helper(value) "
                "instead.",
            )
        return new_helper(value)

Conventions for the warning:

- Pass the **removal version** as the first argument, not the deprecation
  version. ``warn_until(3010, ...)`` means "this code must be gone by
  3010.0".
- Allow at least two feature releases between deprecation and removal. If
  you deprecate something in 3008.0, ``warn_until(3010, ...)`` is the
  minimum; more time is appropriate for invasive changes.
- The message text appears in user logs - write it for them, not for
  developers. Tell them what to do instead.

When the removal version ships, ``warn_until`` will raise on import or first
call. That is your signal to delete the deprecated code and the
``warn_until`` itself in the same PR.


Step 3: Add a changelog fragment
================================

Use the ``deprecated`` type:

.. code-block:: bash

    cat > changelog/12345.deprecated.md <<'EOF'
    The ``legacy_mode`` argument to ``old_helper`` is deprecated and will be
    removed in Salt 3010.0. Use ``new_helper`` instead.
    EOF

When the code is finally removed two releases later, that follow-up PR adds
a ``.removed.md`` fragment instead.

See :ref:`changelog-types` for the rest of the changelog vocabulary.


Silencing the runtime warning
=============================

If the warnings are noisy in a test environment, set ``PYTHONWARNINGS=ignore``
or use Python's ``warnings.filterwarnings`` machinery. Do **not** suppress
the warnings inside the Salt code itself; users need to see them.
