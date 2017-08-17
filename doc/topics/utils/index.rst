.. _writing-utility-modules:

==============================================
Utility Modules - Code Reuse in Custom Modules
==============================================

.. versionadded:: 2015.5.0
.. versionchanged:: 2016.11.0
    These can now be synced to the Master for use in custom Runners, and in
    custom execution modules called within Pillar SLS files.

When extending Salt by writing custom (:ref:`state modules
<writing-state-modules>`), :ref:`execution modules
<writing-execution-modules>`, etc., sometimes there is a need for a function to
be available to more than just one kind of custom module. For these cases, Salt
supports what are called "utility modules". These modules are like normal
execution modules, but instead of being invoked in Salt code using
``__salt__``, the ``__utils__`` prefix is used instead.

For example, assuming the following simple utility module, saved to
``salt://_utils/foo.py``

.. code-block:: python

    # -*- coding: utf-8 -*-
    '''
    My utils module
    ---------------

    This module contains common functions for use in my other custom types.
    '''

    def bar():
        return 'baz'

Once synced to a minion, this function would be available to other custom Salt
types like so:

.. code-block:: python

    # -*- coding: utf-8 -*-
    '''
    My awesome execution module
    ---------------------------
    '''

    def observe_the_awesomeness():
        '''
        Prints information from my utility module

        CLI Example:

        .. code-block:: bash

            salt '*' mymodule.observe_the_awesomeness
        '''
        return __utils__['foo.bar']()

Utility modules, like any other kind of Salt extension, support using a
:ref:`__virtual__ function <modules-virtual-name>` to conditionally load them,
or load them under a different namespace. For instance, if the utility module
above were named ``salt://_utils/mymodule.py`` it could be made to be loaded as
the ``foo`` utility module with a ``__virtual__`` function.

.. code-block:: python

    # -*- coding: utf-8 -*-
    '''
    My utils module
    ---------------

    This module contains common functions for use in my other custom types.
    '''

    def __virtual__():
        '''
        Load as a different name
        '''
        return 'foo'

    def bar():
        return 'baz'

Also you could even write your utility modules in object oriented fashion:

.. code-block:: python

    # -*- coding: utf-8 -*-
    '''
    My utils module
    ---------------

    This module contains common functions for use in my other custom types.
    '''

    class Foo(object):

        def __init__(self):
            pass

        def bar(self):
            return 'baz'

And import them into other custom modules:

.. code-block:: python

    # -*- coding: utf-8 -*-
    '''
    My awesome execution module
    ---------------------------
    '''

    import mymodule

    def observe_the_awesomeness():
        '''
        Prints information from my utility module

        CLI Example:

        .. code-block:: bash

            salt '*' mymodule.observe_the_awesomeness
        '''
        foo = mymodule.Foo()
        return foo.bar()

These are, of course, contrived examples, but they should serve to show some of
the possibilities opened up by writing utility modules. Keep in mind though
that states still have access to all of the execution modules, so it is not
necessary to write a utility module to make a function available to both a
state and an execution module. One good use case for utility modules is one
where it is necessary to invoke the same function from a custom :ref:`outputter
<all-salt.output>`/returner, as well as an execution module.

Utility modules placed in ``salt://_utils/`` will be synced to the minions when
any of the following Salt functions are called:

* :mod:`state.apply <salt.modules.state.apply_>`
* :mod:`saltutil.sync_utils <salt.modules.saltutil.sync_utils>`
* :mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>`

To sync to the Master, use either of the following:

* :mod:`saltutil.sync_utils <salt.runners.saltutil.sync_utils>`
* :mod:`saltutil.sync_all <salt.runners.saltutil.sync_all>`
