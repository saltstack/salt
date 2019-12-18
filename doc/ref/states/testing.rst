=============
State Testing
=============

Executing a Salt state run can potentially change many aspects of a system and
it may be desirable to first see what a state run is going to change before
applying the run.

Salt has a test interface to report on exactly what will be changed, this
interface can be invoked on any of the major state run functions:

.. code-block:: bash

    salt '*' state.apply test=True
    salt '*' state.apply mysls test=True
    salt '*' state.single test=True

The test run is mandated by adding the ``test=True`` option to the states. The
return information will show states that will be applied in yellow and the
result is reported as ``None``.

Default Test
============

If the value ``test`` is set to ``True`` in the minion configuration file then
states will default to being executed in test mode. If this value is set then
states can still be run by calling test=False:

.. code-block:: bash

    salt '*' state.apply test=False
    salt '*' state.apply mysls test=False
    salt '*' state.single test=False
