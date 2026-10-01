.. _cloud-events-reference:

===========================
Salt Cloud Events Reference
===========================

This page is the canonical reference for the events Salt Cloud fires on the
Salt event bus. Reactors can subscribe to any of these tags to take action
when an instance is created, destroyed, resized, or otherwise acted upon.

Event tags follow the pattern::

    salt/cloud/<resource>/<task>

where ``<resource>`` is normally the VM name, but may also be the name of a
shared resource (a disk, a load balancer, a snapshot, an IP address, etc.)
when the event describes a non-VM operation.

For background on using these tags with the Salt Reactor system, see
:ref:`salt-cloud-with-reactor`. For the general Salt event bus event reference,
see :ref:`event-master_events`.

Lifecycle Events
================

These tags are fired during the normal create / destroy lifecycle of a VM and
are emitted by the majority of cloud drivers.

.. salt:event:: salt/cloud/<vm_name>/creating

    Fired when ``salt-cloud`` begins the VM creation process. No work has
    been done against the cloud provider yet.

    :var name: name of the VM being created.
    :var profile: the cloud profile selected for the VM.
    :var provider: the cloud provider configured for that profile.
    :var driver: the cloud driver name (e.g. ``ec2``, ``vmware``).

.. salt:event:: salt/cloud/<vm_name>/requesting

    Fired immediately before the create-VM request is sent to the cloud
    provider. The payload contains the kwargs that will be passed to the
    provider API, with passwords, keys, and other sensitive values stripped.

    :var kwargs: dictionary of provider-specific create parameters. Common
        keys include ``name``, ``image``, ``size``, ``location``,
        ``ImageId``, ``InstanceType``, ``KeyName``.

.. salt:event:: salt/cloud/<vm_name>/requesting/failed

    Fired when the create request is sent but the provider returns an error
    before an instance ID is allocated. Currently emitted by the EC2 driver
    when a spot instance request fails.

    :var error: the error message returned by the provider.

.. salt:event:: salt/cloud/<vm_name>/waiting_for_spot

    Fired by the EC2 driver after a spot-instance request has been submitted
    and ``salt-cloud`` is waiting for the spot request to be fulfilled.

.. salt:event:: salt/cloud/<vm_name>/querying

    Fired when ``salt-cloud`` begins polling the cloud provider for the
    instance's network address(es) after a successful create request.

    :var instance_id: the provider-assigned ID of the new instance.

.. salt:event:: salt/cloud/<vm_name>/tagging

    Fired when ``salt-cloud`` applies tags to a newly-created instance.
    Emitted by drivers that tag instances at create time (e.g. EC2, packet).

    :var tags: dictionary of tags being applied.

.. salt:event:: salt/cloud/<vm_name>/waiting_for_ssh

    Fired once the instance has an IP address and ``salt-cloud`` begins
    waiting for SSH to become available so that the deploy script can be
    uploaded.

    :var ip_address: the IP address ``salt-cloud`` will connect to.

.. salt:event:: salt/cloud/<vm_name>/deploying

    Fired immediately before the deploy script (``bootstrap-salt.sh`` by
    default) or the Windows installer is uploaded and executed on the
    instance.

    :var kwargs: the deploy keyword arguments. Sensitive keys
        (``password``, ``private_key``, ``minion_pem``, ``minion_pub``,
        etc.) are stripped before the event is fired.

.. salt:event:: salt/cloud/<vm_name>/deploy_script

    Fired once the Linux/Unix deploy script has finished executing on the
    new instance.

.. salt:event:: salt/cloud/<vm_name>/deploy_windows

    Fired once the Windows installer has finished executing on the new
    instance.

.. salt:event:: salt/cloud/<vm_name>/created

    Fired once the instance has been fully created and (when applicable)
    Salted. This is the final tag fired by the create path.

    :var name: name of the VM that was created.
    :var profile: the cloud profile used.
    :var provider: the cloud provider used.
    :var instance_id: the provider-assigned ID of the instance.

.. salt:event:: salt/cloud/<vm_name>/destroying

    Fired when ``salt-cloud`` requests destruction of an instance.

    :var name: name of the VM being destroyed.
    :var instance_id: the provider-assigned ID of the instance.

.. salt:event:: salt/cloud/<vm_name>/destroyed

    Fired once the instance has been destroyed.

    :var name: name of the VM that was destroyed.
    :var instance_id: the provider-assigned ID of the instance.

Power-State Events
==================

These tags are fired by drivers that support pausing, starting, stopping,
rebooting, or resizing existing instances through ``salt-cloud -a``.

.. salt:event:: salt/cloud/<vm_name>/starting

    Fired when ``salt-cloud`` requests that a stopped instance be started.

.. salt:event:: salt/cloud/<vm_name>/started

    Fired once the instance has been started.

.. salt:event:: salt/cloud/<vm_name>/stopping

    Fired when ``salt-cloud`` requests that a running instance be stopped.

.. salt:event:: salt/cloud/<vm_name>/stopped

    Fired once the instance has been stopped.

.. salt:event:: salt/cloud/<vm_name>/rebooting

    Fired when ``salt-cloud`` requests that an instance be rebooted.

.. salt:event:: salt/cloud/<vm_name>/rebooted

    Fired once the reboot has been requested. This event marks the request
    completing; the instance may still be in the process of restarting.

.. salt:event:: salt/cloud/<vm_name>/resizing

    Fired when ``salt-cloud`` requests that an instance be resized.

.. salt:event:: salt/cloud/<vm_name>/resized

    Fired once the resize has completed.

.. salt:event:: salt/cloud/<vm_name>/deleting

    Fired by drivers that distinguish a "delete" call from a "destroy"
    (e.g. Hetzner) when ``salt-cloud`` requests deletion of a resource.

.. salt:event:: salt/cloud/<vm_name>/deleted

    Fired by drivers that distinguish a "delete" call from a "destroy"
    once the delete operation has completed.

Reactor Hook Events
===================

These tags are emitted by the cloud cache subsystem when running
``salt-cloud --full-query`` (or the ``cloud.full_query`` runner) and are
intended for use with the ``salt-cloud-reactor`` formula. See the
`salt-cloud-reactor`_ formula for example reactors.

.. _salt-cloud-reactor: https://github.com/saltstack-formulas/salt-cloud-reactor

.. salt:event:: salt/cloud/<vm_name>/query_reactor

    Fired by ``salt-cloud --full-query`` when a node is observed and the
    reactor cache is enabled.

.. salt:event:: salt/cloud/<vm_name>/ssh_ready_reactor

    Fired when the cloud cache subsystem detects that SSH on an instance is
    ready to receive connections.

.. salt:event:: salt/cloud/<node>/cache_node_new

    Fired the first time a node is observed during a full-query refresh.

.. salt:event:: salt/cloud/<node>/cache_node_missing

    Fired when a node that was previously cached is no longer reported by
    the cloud provider during a full-query refresh.

.. salt:event:: salt/cloud/<node>/cache_node_diff

    Fired when a node's cached data has changed since the previous
    full-query refresh.

Resource Events
===============

Several drivers expose function calls that create, delete, attach, or detach
non-VM resources such as block volumes, load balancers, snapshots, public
IPs, networks, and firewalls. The general pattern is
``salt/cloud/<resource>/<verb>`` where ``<resource>`` is the resource type
or the resource's name, not a VM name.

Volume / disk events
--------------------

.. salt:event:: salt/cloud/<vm_name>/attaching_volumes

    Fired by the EC2 driver when one or more EBS volumes are being attached
    during VM creation.

.. salt:event:: salt/cloud/disk/creating
.. salt:event:: salt/cloud/disk/created
.. salt:event:: salt/cloud/disk/deleting
.. salt:event:: salt/cloud/disk/deleted
.. salt:event:: salt/cloud/disk/attaching
.. salt:event:: salt/cloud/disk/attached
.. salt:event:: salt/cloud/disk/detaching
.. salt:event:: salt/cloud/disk/detached

    Fired by the GCE driver around persistent-disk operations.

.. salt:event:: salt/cloud/<volume_name>/destroying
.. salt:event:: salt/cloud/<volume_name>/destroyed
.. salt:event:: salt/cloud/<volume_name>/detaching
.. salt:event:: salt/cloud/<volume_name>/detached

    Fired by the OpenStack driver around block-volume destroy and detach
    operations.

.. salt:event:: salt/cloud/block_volume_<volume_id>/tagging

    Fired by the EC2 driver when block-volume tags are applied as part of
    instance creation.

Snapshot events
---------------

.. salt:event:: salt/cloud/snapshot/creating
.. salt:event:: salt/cloud/snapshot/created
.. salt:event:: salt/cloud/snapshot/deleting
.. salt:event:: salt/cloud/snapshot/deleted

    Fired by the GCE driver around snapshot operations.

Network events
--------------

.. salt:event:: salt/cloud/net/creating
.. salt:event:: salt/cloud/net/created
.. salt:event:: salt/cloud/net/deleting
.. salt:event:: salt/cloud/net/deleted
.. salt:event:: salt/cloud/subnet/creating
.. salt:event:: salt/cloud/subnet/created
.. salt:event:: salt/cloud/subnet/deleting
.. salt:event:: salt/cloud/subnet/deleted

    Fired by the GCE driver around VPC network and subnet operations.

.. salt:event:: salt/cloud/address/creating
.. salt:event:: salt/cloud/address/created
.. salt:event:: salt/cloud/address/deleting
.. salt:event:: salt/cloud/address/deleted

    Fired by the GCE driver around static external-IP operations.

.. salt:event:: salt/cloud/firewall/creating
.. salt:event:: salt/cloud/firewall/created
.. salt:event:: salt/cloud/firewall/deleting
.. salt:event:: salt/cloud/firewall/deleted

    Fired by the GCE driver around firewall-rule operations.

Load balancer / health check events
-----------------------------------

.. salt:event:: salt/cloud/loadbalancer/creating
.. salt:event:: salt/cloud/loadbalancer/created
.. salt:event:: salt/cloud/loadbalancer/deleting
.. salt:event:: salt/cloud/loadbalancer/deleted
.. salt:event:: salt/cloud/loadbalancer/attaching
.. salt:event:: salt/cloud/loadbalancer/attached
.. salt:event:: salt/cloud/loadbalancer/detaching
.. salt:event:: salt/cloud/loadbalancer/detached

    Fired by the GCE driver around load-balancer pool operations and
    backend attachment.

.. salt:event:: salt/cloud/healthcheck/creating
.. salt:event:: salt/cloud/healthcheck/created
.. salt:event:: salt/cloud/healthcheck/deleting
.. salt:event:: salt/cloud/healthcheck/deleted

    Fired by the GCE driver around HTTP health-check operations.

Spot-instance events
--------------------

.. salt:event:: salt/cloud/spot_request_<request_id>/tagging

    Fired by the EC2 driver when a spot-instance request is tagged.

Filtering Event Payloads
========================

The keys included in each event payload can be filtered using the
``filter_events`` block in the master configuration. See
:ref:`salt-cloud-with-reactor` for examples and the list of tags supported
by the filter mechanism.
