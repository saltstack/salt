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

.. salt:event:: salt/minion/<MID>/start

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

Cloud Events
============

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
