=================
Logging Internals
=================

You can call the logger from custom modules to write messages to the minion
logs. The following code snippet demonstrates getting access to the logger:

.. code-block:: python
    import logging

    log = logging.getLogger(__name__)

    log.info('here is some information')
    log.warning('you should not do that')
    log.error('it is busted')

For example, to write data to the minion log from a custom state:

1. Place the snippet above in a file called ``/srv/salt/_states/my_state.py``
2. Sync states to your minion, ``salt <minion> saltutil.sync_states``.
3. Apply the state, ``salt <minion> state.apply my_state``. This prints the
   messages to the minion logs.
