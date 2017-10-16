=======================================
Using Salt Cloud with the Event Reactor
=======================================

One of the most powerful features of the Salt framework is the Event Reactor.
As the Reactor was in development, Salt Cloud was regularly updated to take
advantage of the Reactor upon completion. As such, various aspects of both the
creation and destruction of instances with Salt Cloud fire events to the Salt
Master, which can be used by the Event Reactor.


Event Structure
===============

As of this writing, all events in Salt Cloud have a tag, which includes the ID
of the instance being managed, and a payload which describes the task that is
currently being handled. A Salt Cloud tag looks like:

.. code-block:: yaml

    salt/cloud/<minion_id>/<task>

For instance, the first event fired when creating an instance named ``web1``
would look like:

.. code-block:: yaml

    salt/cloud/web1/creating

Assuming this instance is using the ``ec2-centos`` profile, which is in turn
using the ``ec2-config`` provider, the payload for this tag would look like:

.. code-block:: python

    {'name': 'web1',
     'profile': 'ec2-centos',
     'provider': 'ec2-config:ec2'}

Available Events
================

When an instance is created in Salt Cloud, whether by map, profile, or directly
through an API, a minimum of five events are normally fired. More may be
available, depending upon the cloud provider being used. Some of the common
events are described below.

salt/cloud/<minion_id>/creating
-------------------------------

This event states simply that the process to create an instance has begun. At
this point in time, no actual work has begun. The payload for this event
includes:

name
profile
provider

salt/cloud/<minion_id>/requesting
---------------------------------

Salt Cloud is about to make a request to the cloud provider to create an
instance. At this point, all of the variables required to make the request have
been gathered, and the payload of the event will reflect those variables which
do not normally pose a security risk. What is returned here is dependent upon
the cloud provider. Some common variables are:

name
image
size
location

salt/cloud/<minion_id>/querying
-------------------------------

The instance has been successfully requested, but the necessary information to
log into the instance (such as IP address) is not yet available. This event
marks the beginning of the process to wait for this information.

The payload for this event normally only includes the ``instance_id``.

salt/cloud/<minion_id>/waiting_for_ssh
--------------------------------------

The information required to log into the instance has been retrieved, but the
instance is not necessarily ready to be accessed. Following this event, Salt
Cloud will wait for the IP address to respond to a ping, then wait for the
specified port (usually 22) to respond to a connection, and on Linux systems,
for SSH to become available. Salt Cloud will attempt to issue the ``date``
command on the remote system, as a means to check for availability. If no
``ssh_username`` has been specified, a list of usernames (starting with
``root``) will be attempted. If one or more usernames was configured for
``ssh_username``, they will be added to the beginning of the list, in order.

The payload for this event normally only includes the ``ip_address``.

salt/cloud/<minion_id>/deploying
--------------------------------

The necessary port has been detected as available, and now Salt Cloud can log
into the instance, upload any files used for deployment, and run the deploy
script. Once the script has completed, Salt Cloud will log back into the
instance and remove any remaining files.

A number of variables are used to deploy instances, and the majority of these
will be available in the payload. Any keys, passwords or other sensitive data
will be scraped from the payload. Most of the variables returned will be
related to the profile or provider config, and any default values that could
have been changed in the profile or provider, but weren't.

salt/cloud/<minion_id>/created
------------------------------

The deploy sequence has completed, and the instance is now available, Salted,
and ready for use. This event is the final task for Salt Cloud, before returning
instance information to the user and exiting.

The payload for this event contains little more than the initial ``creating``
event. This event is required in all cloud providers.


Configuring the Event Reactor
=============================

The Event Reactor is built into the Salt Master process, and as such is
configured via the master configuration file. Normally this will be a YAML
file located at ``/etc/salt/master``. Additionally, master configuration items
can be stored, in YAML format, inside the ``/etc/salt/master.d/`` directory.

These configuration items may be stored in either location; however, they may
only be stored in one location. For organizational and security purposes, it
may be best to create a single configuration file, which contains only Event
Reactor configuration, at ``/etc/salt/master.d/reactor``.

The Event Reactor uses a top-level configuration item called ``reactor``. This
block contains a list of tags to be watched for, each of which also includes a
list of ``sls`` files. For instance:

.. code-block:: yaml

    reactor:
      - 'salt/minion/*/start':
        - '/srv/reactor/custom-reactor.sls'
      - 'salt/cloud/*/created':
        - '/srv/reactor/cloud-alert.sls'
      - 'salt/cloud/*/destroyed':
        - '/srv/reactor/cloud-destroy-alert.sls'

The above configuration configures reactors for three different tags: one which
is fired when a minion process has started and is available to receive commands,
one which is fired when a cloud instance has been created, and one which is
fired when a cloud instance is destroyed.

Note that each tag contains a wildcard (``*``) in it. For each of these tags,
this will normally refer to a ``minion_id``. This is not required of event tags,
but is very common.

Reactor SLS Files
=================

Reactor ``sls`` files should be placed in the ``/srv/reactor/`` directory for
consistency between environments, but this is not currently enforced by Salt.

Reactor ``sls`` files follow a similar format to other ``sls`` files in
Salt. By default they are written in YAML and can be templated using Jinja, but
since they are processed through Salt's rendering system, any available
renderer (JSON, Mako, Cheetah, etc.) can be used.

As with other ``sls`` files, each stanza will start with a declaration ID,
followed by the function to run, and then any arguments for that function. For
example:

.. code-block:: yaml

    # /srv/reactor/cloud-alert.sls
    new_instance_alert:
      cmd.pagerduty.create_event:
        - tgt: alertserver
        - kwarg:
            description: "New instance: {{ data['name'] }}"
            details: "New cloud instance created on {{ data['provider'] }}"
            service_key: 1626dead5ecafe46231e968eb1be29c4
            profile: my-pagerduty-account

When the Event Reactor receives an event notifying it that a new instance has
been created, this ``sls`` will create a new incident in PagerDuty, using the
configured PagerDuty account.

The declaration ID in this example is ``new_instance_alert``. The function
called is ``cmd.pagerduty.create_event``. The ``cmd`` portion of this function
specifies that an execution module and function will be called, in this case,
the ``pagerduty.create_event`` function.

Because an execution module is specified, a target (``tgt``) must be specified
on which to call the function. In this case, a minion called ``alertserver``
has been used. Any arguments passed through to the function are declared in the
``kwarg`` block.

Example: Reactor-Based Highstate
================================

When Salt Cloud creates an instance, by default it will install the Salt Minion
onto the instance, along with any specified minion configuration, and
automatically accept that minion's keys on the master. One of the configuration
options that can be specified is ``startup_states``, which is commonly set to
``highstate``. This will tell the minion to immediately apply a :ref:`highstate
<running-highstate>`, as soon as it is able to do so.

This can present a problem with some system images on some cloud hosts. For
instance, Salt Cloud can be configured to log in as either the ``root`` user, or
a user with ``sudo`` access. While some hosts commonly use images that
lock out remote ``root`` access and require a user with ``sudo`` privileges to
log in (notably EC2, with their ``ec2-user`` login), most cloud hosts fall
back to ``root`` as the default login on all images, including for operating
systems (such as Ubuntu) which normally disallow remote ``root`` login.

For users of these operating systems, it is understandable that a
:ref:`highstate <running-highstate>` would include configuration to block
remote ``root`` logins again. However, Salt Cloud may not have finished
cleaning up its deployment files by the time the minion process has started,
and kicked off a :ref:`highstate <running-highstate>` run. Users have reported
errors from Salt Cloud getting locked out while trying to clean up after
itself.

The goal of a startup state may be achieved using the Event Reactor. Because a
minion fires an event when it is able to receive commands, this event can
effectively be used inside the reactor system instead. The following will point
the reactor system to the right ``sls`` file:

.. code-block:: yaml

    reactor:
      - 'salt/cloud/*/created':
        - '/srv/reactor/startup_highstate.sls'

And the following ``sls`` file will start a :ref:`highstate
<running-highstate>` run on the target minion:

.. code-block:: yaml

    # /srv/reactor/startup_highstate.sls
    reactor_highstate:
      cmd.state.apply:
        - tgt: {{ data['name'] }}

Because this event will not be fired until Salt Cloud has cleaned up after
itself, the :ref:`highstate <running-highstate>` run will not step on
salt-cloud's toes. And because every file on the minion is configurable,
including ``/etc/salt/minion``, the ``startup_states`` can still be configured
for future minion restarts, if desired.
