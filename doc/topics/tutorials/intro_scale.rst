.. _tutorial-salt-at-scale:

===================
Using Salt at scale
===================

The focus of this tutorial will be building a Salt infrastructure for handling
large numbers of minions. This will include tuning, topology, and best practices.

For how to install the Salt Master please
go here: `Installing saltstack <http://docs.saltstack.com/topics/installation/index.html>`_

.. note::

    This tutorial is intended for large installations, although these same settings
    won't hurt, it may not be worth the complexity to smaller installations.

    When used with minions, the term 'many' refers to at least a thousand
    and 'a few' always means 500.

    For simplicity reasons, this tutorial will default to the standard ports
    used by Salt.

The Master
==========

The most common problems on the Salt Master are:

1. too many minions authing at once
2. too many minions re-authing at once
3. too many minions re-connecting at once
4. too many minions returning at once
5. too few resources (CPU/HDD)

The first three are all "thundering herd" problems. To mitigate these issues
we must configure the minions to back-off appropriately when the Master is
under heavy load.

The fourth is caused by masters with little hardware resources in combination
with a possible bug in ZeroMQ. At least that's what it looks like till today
(`Issue 118651 <https://github.com/saltstack/salt/issues/11865>`_,
`Issue 5948 <https://github.com/saltstack/salt/issues/5948>`_,
`Mail thread <https://groups.google.com/forum/#!searchin/salt-users/lots$20of$20minions/salt-users/WxothArv2Do/t12MigMQDFAJ>`_)

To fully understand each problem, it is important to understand, how Salt works.

Very briefly, the Salt Master offers two services to the minions.

- a job publisher on port 4505
- an open port 4506 to receive the minions returns

All minions are always connected to the publisher on port 4505 and only connect
to the open return port 4506 if necessary. On an idle Master, there will only
be connections on port 4505.

Too many minions authing
------------------------

When the Minion service is first started up, it will connect to its Master's publisher
on port 4505. If too many minions are started at once, this can cause a "thundering herd".
This can be avoided by not starting too many minions at once.

The connection itself usually isn't the culprit, the more likely cause of master-side
issues is the authentication that the Minion must do with the Master. If the Master
is too heavily loaded to handle the auth request it will time it out. The Minion
will then wait `acceptance_wait_time` to retry. If `acceptance_wait_time_max` is
set then the Minion will increase its wait time by the `acceptance_wait_time` each
subsequent retry until reaching `acceptance_wait_time_max`.

Too many minions re-authing
---------------------------

This is most likely to happen in the testing phase of a Salt deployment, when
all Minion keys have already been accepted, but the framework is being tested
and parameters are frequently changed in the Salt Master's configuration
file(s).

The Salt Master generates a new AES key to encrypt its publications at certain
events such as a Master restart or the removal of a Minion key.  If you are
encountering this problem of too many minions re-authing against the Master,
you will need to recalibrate your setup to reduce the rate of events like a
Master restart or Minion key removal (``salt-key -d``).

When the Master generates a new AES key, the minions aren't notified of this
but will discover it on the next pub job they receive. When the Minion
receives such a job it will then re-auth with the Master. Since Salt does
minion-side filtering this means that all the minions will re-auth on the next
command published on the master-- causing another "thundering herd". This can
be avoided by setting the

.. code-block:: yaml

    random_reauth_delay: 60

in the minions configuration file to a higher value and stagger the amount
of re-auth attempts. Increasing this value will of course increase the time
it takes until all minions are reachable via Salt commands.

Too many minions re-connecting
------------------------------

By default the zmq socket will re-connect every 100ms which for some larger
installations may be too quick. This will control how quickly the TCP session is
re-established, but has no bearing on the auth load.

To tune the minions sockets reconnect attempts, there are a few values in
the sample configuration file (default values)

.. code-block:: yaml

    recon_default: 1000
    recon_max: 5000
    recon_randomize: True

- recon_default: the default value the socket should use, i.e. 1000. This value is in
  milliseconds. (1000ms = 1 second)
- recon_max: the max value that the socket should use as a delay before trying to reconnect
  This value is in milliseconds. (5000ms = 5 seconds)
- recon_randomize: enables randomization between recon_default and recon_max

To tune this values to an existing environment, a few decision have to be made.


1. How long can one wait, before the minions should be online and reachable via Salt?

2. How many reconnects can the Master handle without a syn flood?

These questions can not be answered generally. Their answers depend on the
hardware and the administrators requirements.

Here is an example scenario with the goal, to have all minions reconnect
within a 60 second time-frame on a Salt Master service restart.

.. code-block:: yaml

    recon_default: 1000
    recon_max: 59000
    recon_randomize: True

Each Minion will have a randomized reconnect value between 'recon_default'
and 'recon_default + recon_max', which in this example means between 1000ms
and 60000ms (or between 1 and 60 seconds). The generated random-value will
be doubled after each attempt to reconnect (ZeroMQ default behavior).

Lets say the generated random value is 11 seconds (or 11000ms).

.. code-block:: console

    reconnect 1: wait 11 seconds
    reconnect 2: wait 22 seconds
    reconnect 3: wait 33 seconds
    reconnect 4: wait 44 seconds
    reconnect 5: wait 55 seconds
    reconnect 6: wait time is bigger than 60 seconds (recon_default + recon_max)
    reconnect 7: wait 11 seconds
    reconnect 8: wait 22 seconds
    reconnect 9: wait 33 seconds
    reconnect x: etc.

With a thousand minions this will mean

.. code-block:: text

    1000/60 = ~16

round about 16 connection attempts a second. These values should be altered to
values that match your environment. Keep in mind though, that it may grow over
time and that more minions might raise the problem again.

Too many minions returning at once
----------------------------------

This can also happen during the testing phase, if all minions are addressed at
once with

.. code-block:: bash

    $ salt * disk.usage

it may cause thousands of minions trying to return their data to the Salt Master
open port 4506. Also causing a flood of syn-flood if the Master can't handle that many
returns at once.

This can be easily avoided with Salt's batch mode:

.. code-block:: bash

    $ salt * disk.usage -b 50

This will only address 50 minions at once while looping through all addressed
minions.

Too few resources
=================

The masters resources always have to match the environment. There is no way
to give good advise without knowing the environment the Master is supposed to
run in.  But here are some general tuning tips for different situations:

The Master is CPU bound
-----------------------

Salt uses RSA-Key-Pairs on the masters and minions end. Both generate 4096
bit key-pairs on first start. While the key-size for the Master is currently
not configurable, the minions keysize can be configured with different
key-sizes. For example with a 2048 bit key:

.. code-block:: yaml

    keysize: 2048

With thousands of decryptions, the amount of time that can be saved on the
masters end should not be neglected. See here for reference:
`Pull Request 9235 <https://github.com/saltstack/salt/pull/9235>`_ how much
influence the key-size can have.

Downsizing the Salt Master's key is not that important, because the minions
do not encrypt as many messages as the Master does.

In installations with large or with complex pillar files, it is possible
for the master to exhibit poor performance as a result of having to render
many pillar files at once. This exhibit itself in a number of ways, both
as high load on the master and on minions which block on waiting for their
pillar to be delivered to them.

To reduce pillar rendering times, it is possible to cache pillars on the
master. To do this, see the set of master configuration options which
are prefixed with `pillar_cache`.

If many pillars are encrypted using :mod:`gpg <salt.renderers.gpg>` renderer, it
is possible to cache GPG data. To do this, see the set of master configuration
options which are prefixed with `gpg_cache`.

.. note::

    Caching pillars or GPG data on the master may introduce security
    considerations. Be certain to read caveats outlined in the master
    configuration file to understand how pillar caching may affect a master's
    ability to protect sensitive data!

The Master is disk IO bound
---------------------------

By default, the Master saves every Minion's return for every job in its
job-cache. The cache can then be used later, to lookup results for previous
jobs. The default directory for this is:

.. code-block:: yaml

    cachedir: /var/cache/salt

and then in the ``/proc`` directory.

Each job return for every Minion is saved in a single file. Over time this
directory can grow quite large, depending on the number of published jobs. The
amount of files and directories will scale with the number of jobs published and
the retention time defined by

.. code-block:: yaml

    keep_jobs: 24

.. code-block:: text

    250 jobs/day * 2000 minions returns = 500,000 files a day

Use and External Job Cache
~~~~~~~~~~~~~~~~~~~~~~~~~~

An external job cache allows for job storage to be placed on an external
system, such as a database.

- ext_job_cache: this will have the minions store their return data directly
  into a returner (not sent through the Master)
- master_job_cache (New in `2014.7.0`): this will make the Master store the job
  data using a returner (instead of the local job cache on disk).

If a master has many accepted keys, it may take a long time to publish a job
because the master must first determine the matching minions and deliver
that information back to the waiting client before the job can be published.

To mitigate this, a key cache may be enabled. This will reduce the load
on the master to a single file open instead of thousands or tens of thousands.

This cache is updated by the maintanence process, however, which means that
minions with keys that are accepted may not be targeted by the master
for up to sixty seconds by default.

To enable the master key cache, set `key_cache: 'sched'` in the master
configuration file.

Disable The Job Cache
~~~~~~~~~~~~~~~~~~~~~

The job cache is a central component of the Salt Master and many aspects of
the Salt Master will not function correctly without a running job cache.

Disabling the job cache is **STRONGLY DISCOURAGED** and should not be done
unless the master is being used to execute routines that require no history
or reliable feedback!

The job cache can be disabled:

.. code-block:: yaml

   job_cache: False

