.. _deprecations:

================
Deprecating Code
================

Salt should remain backwards compatible, though sometimes, this backwards
compatibility needs to be broken because a specific feature and/or solution is
no longer necessary or required.  At first one might think, let me change this
code, it seems that it's not used anywhere else so it should be safe to remove.
Then, once there's a new release, users complain about functionality which was
removed and they where using it, etc. This should, at all costs, be avoided,
and, in these cases, *that* specific code should be deprecated.

In order to give users enough time to migrate from the old code behavior to the
new behavior, the deprecation time frame should be carefully determined based
on the significance and complexity of the changes required by the user.

Salt feature releases are based on the Periodic Table. Any new features going
into the ``master`` branch will be named after the next element in the Periodic
Table. For example, Magnesium was the feature release name associated with the
``v3002`` tag. At that point in time, any new features going into the
``master`` branch, after ``v3002`` was tagged, were part of the Aluminium feature
release.

A deprecation warning should be in place for at least two major releases before
the deprecated code and its accompanying deprecation warning are removed.  More
time should be given for more complex changes.  For example, if the current
release under development is ``3001``, the deprecated code and associated
warnings should remain in place and warn for at least ``Aluminium``.

To help in this deprecation task, salt provides
:func:`salt.utils.versions.warn_until <salt.utils.versions.warn_until>`. The
idea behind this helper function is to show the deprecation warning to the user
until salt reaches the provided version. Once that provided version is equaled
:func:`salt.utils.versions.warn_until <salt.utils.versions.warn_until>` will
raise a :py:exc:`RuntimeError` making salt stop its execution. This stoppage is
unpleasant and will remind the developer that the deprecation limit has been
reached and that the code can then be safely removed.

Consider the following example:

.. code-block:: python

    def some_function(bar=False, foo=None):
        if foo is not None:
            salt.utils.versions.warn_until(
                "Aluminium",
                "The 'foo' argument has been deprecated and its "
                "functionality removed, as such, its usage is no longer "
                "required.",
            )

Development begins on ``Aluminium``, or ``v3003``, after the ``v3002`` tag is
applied to the ``master`` branch.  Once this occurs, all uses of the
``warn_until`` function targeting ``Aluminium``, along with the code they are
warning about should be removed from the code.


Silence Deprecation Warnings
----------------------------

If you set the `PYTHONWARNINGS` environment variable to `ignore` Salt will
not print the deprecation warnings.
