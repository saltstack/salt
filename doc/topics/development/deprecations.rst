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

A deprecation warning should be in place for at least two major releases before
the deprecated code and its accompanying deprecation warning are removed.  More
time should be given for more complex changes.  For example, if the current
release under development is ``Sodium``, the deprecated code and associated
warnings should remain in place and warn for at least ``Aluminum``.

To help in this deprecation task, salt provides :func:`salt.utils.warn_until
<salt.utils.warn_until>`. The idea behind this helper function is to show the
deprecation warning to the user until salt reaches the provided version. Once
that provided version is equaled :func:`salt.utils.warn_until
<salt.utils.warn_until>` will raise a :py:exc:`RuntimeError` making salt stop
its execution. This stoppage is unpleasant and will remind the developer that
the deprecation limit has been reached and that the code can then be safely
removed.

Consider the following example:

.. code-block:: python

    def some_function(bar=False, foo=None):
        if foo is not None:
            salt.utils.warn_until(
                'Aluminum',
                'The \'foo\' argument has been deprecated and its '
                'functionality removed, as such, its usage is no longer '
                'required.'
            )

Development begins on the ``Aluminum`` release when the ``Magnesium`` branch is
forked from the develop branch.  Once this occurs, all uses of the
``warn_until`` function targeting ``Aluminum``, along with the code they are
warning about should be removed from the code.
