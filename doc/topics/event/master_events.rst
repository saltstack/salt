.. _event-master_events:

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


    .. note:: Minions fire auth events on fairly regular basis for a number
              of reasons.  Writing reactors to respond to events through
              the auth cycle can lead to infinite reactor event loops
              (minion tries to auth, reactor responds by doing something
              that generates another auth event, minion sends auth event,
              etc.).  Consider reacting to ``salt/key`` or ``salt/minion/<MID>/start``
              or firing a custom event tag instead.

Start events
============

.. salt:event:: salt/minion/<MID>/start

    Fired every time a minion connects to the Salt master.

    :var id: The minion ID.

Key events
==========

.. salt:event:: salt/key

    Fired when accepting and rejecting minions keys on the Salt master.

    :var id: The minion ID.
    :var act: The new status of the minion key: ``accept``, ``pend``,
              ``reject``.

.. warning:: If a master is in :conf_master:`auto_accept mode`, ``salt/key`` events
             will not be fired when the keys are accepted.  In addition, pre-seeding
             keys (like happens through :ref:`Salt-Cloud<salt-cloud>`) will not cause
             firing of these events.



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

.. salt:event:: salt/job/<JID>/prog/<MID>/<RUN NUM>

    Fired each time a each function in a state run completes execution. Must be
    enabled using the :conf_master:`state_events` option.

    :var data: The data returned from the state module function.
    :var id: The minion ID.
    :var jid: The job ID.

.. _event-master_presence:

Presence events
===============

.. salt:event:: salt/presence/present

    Events fired on a regular interval about currently connected, newly
    connected, or recently disconnected minions. Requires the
    :conf_master:`presence_events` setting to be enabled.

    :var present: A list of minions that are currently connected to the Salt
        master.

.. salt:event:: salt/presence/change

    Fired when the Presence system detects new minions connect or disconnect.

    :var new: A list of minions that have connected since the last presence
        event.
    :var lost: A list of minions that have disconnected since the last
        presence event.

Cloud Events
============

Unlike other Master events, ``salt-cloud`` events are not fired on behalf of a
Salt Minion. Instead, ``salt-cloud`` events are fired on behalf of a VM. This
is because the minion-to-be may not yet exist to fire events to or also may have
been destroyed.

This behavior is reflected by the ``name`` variable in the event data for
``salt-cloud`` events as compared to the ``id`` variable for Salt
Minion-triggered events.

.. salt:event:: salt/cloud/<VM NAME>/creating

    Fired when salt-cloud starts the VM creation process.

    :var name: the name of the VM being created.
    :var event: description of the event.
    :var provider: the cloud provider of the VM being created.
    :var profile: the cloud profile for the VM being created.

.. salt:event:: salt/cloud/<VM NAME>/deploying

    Fired when the VM is available and salt-cloud begins deploying Salt to the
    new VM.

    :var name: the name of the VM being created.
    :var event: description of the event.
    :var kwargs: options available as the deploy script is invoked:
        ``conf_file``, ``deploy_command``, ``display_ssh_output``, ``host``,
        ``keep_tmp``, ``key_filename``, ``make_minion``, ``minion_conf``,
        ``name``, ``parallel``, ``preseed_minion_keys``, ``script``,
        ``script_args``, ``script_env``, ``sock_dir``, ``start_action``,
        ``sudo``, ``tmp_dir``, ``tty``, ``username``

.. salt:event:: salt/cloud/<VM NAME>/requesting

    Fired when salt-cloud sends the request to create a new VM.

    :var event: description of the event.
    :var location: the location of the VM being requested.
    :var kwargs: options available as the VM is being requested:
        ``Action``, ``ImageId``, ``InstanceType``, ``KeyName``, ``MaxCount``,
        ``MinCount``, ``SecurityGroup.1``

.. salt:event:: salt/cloud/<VM NAME>/querying

    Fired when salt-cloud queries data for a new instance.

    :var event: description of the event.
    :var instance_id: the ID of the new VM.

.. salt:event:: salt/cloud/<VM NAME>/tagging

    Fired when salt-cloud tags a new instance.

    :var event: description of the event.
    :var tags: tags being set on the new instance.

.. salt:event:: salt/cloud/<VM NAME>/waiting_for_ssh

    Fired while the salt-cloud deploy process is waiting for ssh to become
    available on the new instance.

    :var event: description of the event.
    :var ip_address: IP address of the new instance.

.. salt:event:: salt/cloud/<VM NAME>/deploy_script

    Fired once the deploy script is finished.

    :var event: description of the event.

.. salt:event:: salt/cloud/<VM NAME>/created

    Fired once the new instance has been fully created.

    :var name: the name of the VM being created.
    :var event: description of the event.
    :var instance_id: the ID of the new instance.
    :var provider: the cloud provider of the VM being created.
    :var profile: the cloud profile for the VM being created.

.. salt:event:: salt/cloud/<VM NAME>/destroying

    Fired when salt-cloud requests the destruction of an instance.

    :var name: the name of the VM being created.
    :var event: description of the event.
    :var instance_id: the ID of the new instance.

.. salt:event:: salt/cloud/<VM NAME>/destroyed

    Fired when an instance has been destroyed.

    :var name: the name of the VM being created.
    :var event: description of the event.
    :var instance_id: the ID of the new instance.
