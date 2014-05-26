==================
Salt Master Events
==================

These events are fired on the Salt Master event bus. This list is **not**
comprehensive.

Authentication events
=====================

.. salt:event:: salt/auth

    Fired when a minion performs an authentication check with the master.

    :var id: The minion ID.
    :var act: The current status of the minion key: ``accept``, ``pend``,
        ``reject``.
    :var pub: The minion public key.

.. salt:event:: salt/minion/jerry/start

    Fired every time a minion connects to the Salt master.

    :var id: The minion ID.

Job events
==========

.. salt:event:: salt/job/<JID>/new

    Fired as a new job is sent out to minions.

    :var jid: The job ID.
    :var tgt: The target of the job: ``*``, a minion ID,
        ``G@os_family:RedHat``, etc.
    :var tgt_type: The type of targeting used: ``glob``, ``grain``,
        ``compound``, etc.
    :var fun: The function to run on minions: ``test.ping``,
        ``network.interfaces``, etc.
    :var arg: A list of arguments to pass to the function that will be
        called.
    :var minions: A list of minion IDs that Salt expects will return data for
        this job.
    :var user: The name of the user that ran the command as defined in Salt's
        Client ACL or external auth.

.. salt:event:: salt/job/<JID>/ret/<MID>

    Fired each time a minion returns data for a job.

    :var id: The minion ID.
    :var jid: The job ID.
    :var retcode: The return code for the job.
    :var fun: The function the minion ran. E.g., ``test.ping``.
    :var return: The data returned from the execution module.

Presence events
===============

.. salt:event:: salt/presence/present

    Fired on a set schedule.

    :var present: A list of minions that are currently connected to the Salt
        master.

.. salt:event:: salt/presence/change

    Fired when the Presence system detects new minions connect or disconnect.

    :var new: A list of minions that have connected since the last presence
        event.
    :var lost: A list of minions that have disconnected since the last
        presence event.
