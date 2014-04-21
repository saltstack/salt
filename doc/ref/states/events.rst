==========
Events
==========

The State events system is used to trigger events based on states changing.
This defaults to sending to the minions event socket.

.. code-block:: yaml

    git:
      pkg.installed:
        - event:
          - target: master
          - tag: git/package
          - data:
              target: myapp
              action: deploy


This is the output from the above block when the state changes.

::

    # python salt/tests/eventlisten.py -n minion $(hostname)
    ipc:///var/run/salt/minion/minion_event_<hostname_hash>_pub.ipc
    Event fired at Sun Apr 20 01:24:54 2014
    *************************
    Tag: fire_master
    Data:
    {'_stamp': '2014-04-20T01:24:53.377716',
     'data': {'action': 'deploy', 'target': 'myapp'},
     'events': None,
     'pretag': None,
     'tag': 'state/event/git/package'}
