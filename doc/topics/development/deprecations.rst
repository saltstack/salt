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

Depending on the complexity and usage of a specific piece of code, the 
deprecation time frame should be properly evaluated. As an example, a 
deprecation warning which is shown for 2 major releases, for example `0.17.0` 
and `0.18.0`, gives users enough time to stop using the deprecated code and 
adapt to the new one.

For example, if you're deprecating the usage of a keyword argument to a 
function, that specific keyword argument should remain in place for the full 
deprecation time frame and if that keyword argument is used, a deprecation 
warning should be shown to the user.

To help in this deprecation task, salt provides :func:`salt.utils.warn_until 
<salt.utils.warn_until>`. The idea behind this helper function is to show the 
deprecation warning until salt reaches the provided version. Once that provided 
version is equaled :func:`salt.utils.warn_until <salt.utils.warn_until>` will 
raise a :py:exc:`RuntimeError` making salt stop its execution. This stoppage 
is unpleasant and will remind the developer that the deprecation limit has been 
reached and that the code can then be safely removed.

Consider the following example:

.. code-block:: python

    def some_function(bar=False, foo=None):
        if foo is not None:
            salt.utils.warn_until(
                (0, 18),
                'The \'foo\' argument has been deprecated and its '
                'functionality removed, as such, its usage is no longer '
                'required.'
            )

Consider that the current salt release is ``0.16.0``. Whenever ``foo`` is 
passed a value different from ``None`` that warning will be shown to the user.  
This will happen in versions ``0.16.2`` to ``0.18.0``, after which a 
:py:exc:`RuntimeError` will be raised making us aware that the deprecated code 
should now be removed.
