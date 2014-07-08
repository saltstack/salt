===================================
Introduction to using salt at scale
===================================

Using salt at scale can be quite a tricky task. If its planned to use saltstack 
for thousands of minions on one or more masters, this tutorial will give advise
on tuning the master and minion settings, will give general tips what can or
should be enabled/disabled and also give some insights to what errors may be
caused by what situation. It will not go into the details of any setup
procedure required.

For how to install the saltmaster and get everything up and running, please
go here: `Installing saltstack <http://docs.saltstack.com/topics/installation/index.html>`_

    Note
    This tutorial is not intended for users with less than a thousand minions.
    Even though it can not hurt, to tune a few settings mentioned in this
    tutorial if the environment consists of less than a thousand minions.

    When used with minions, the term 'many' always means at least a thousand
    and 'a few' always means 500.

    For simplicity reasons, this tutorial will default to the standard ports
    used by salt.

The Master
==========

The most common problems on the salt-master that can occur with many minions
are:

1. too many minions connecting at once
2. too many minions re-connecting at once
3. too many minions returning at once
4. too little ressources (CPU/HDD)

The first three have the same cause. Its usually TCP-SYN-Floods that can occur
in different situations when doing certain things without knowing what actually
happens under the hood.

The fourth is caused by masters with little hardware ressources in combination
with a possible bug in ZeroMQ. At least thats what it looks like till today
(`Issue 118651 <https://github.com/saltstack/salt/issues/11865>`_,
`Issue 5948 <https://github.com/saltstack/salt/issues/5948>`_,
`Mail thread <https://groups.google.com/forum/#!searchin/salt-users/lots$20of$20minions/salt-users/WxothArv2Do/t12MigMQDFAJ>`_)

None of these problems is actually caused by salt itself. Salt and ZeroMQ as
well can handle several thousand minions a master easily. Its usually
misconfigurations in a few places that can be easily fixed.

To fully understand each problem, it is important to understand, how salt works.

Very briefly, the saltmaster offers two services to the minions.

- a job publisher on port 4505
- an open port 4506 to receive the minions returns

All minions are always connected to the publisher on port 4505 and only connect
to the open return port 4506 if necessary. On an idle master, there will only
be connections on port 4505.

Too many minions connecting
===========================
When the minion service is first started up on all machines, they connect to
their masters publisher on port 4505. If too many minion services are started
at once, this can already cause a TCP-SYN-flood on the master. This can be
easily avoided by not starting too many minions at once. This is rarely a
problem though.

It is much more likely to happen, that if many minions have already made their
first connection to the master and wait for their key to be accepted, they
check in every 10 seconds (conf_minion:`acceptance_wait_time`). With the
default of 10 seconds and a thousand minions, thats about 100 minions
checking in every second.  If all keys are now accepted at once with

.. code-block:: bash

    $ salt-key -A -y

the master may run into a bug where it consumes 100% CPU and growing amounts
of memory. This has been reported on the mailing list and the issue-tracker
on github a few times (
`Issue 118651 <https://github.com/saltstack/salt/issues/11865>`_,
`Issue 5948 <https://github.com/saltstack/salt/issues/5948>`_, 
`Mail thread <https://groups.google.com/forum/#!searchin/salt-users/lots$20of$20minions/salt-users/WxothArv2Do/t12MigMQDFAJ>`_),
but the root cause has not yet been found. 

The easiest way around this is, to not accept too many minions at once. It
only has to be done once, no need to rush.


Too many minions re-connecting
==============================
This is most likely to happen in the testing phase, when all minion keys have
already been accepted, the framework is being tested and parameters change
frequently in the masters configuration file.

Upon a service restart, the salt-master generates a new AES-key to encrypt
its publications with, but the minions don't yet know about the masters new
AES-key. When the first job after the masters restart is published, the
minions realize, that they have received a publication they can not decrypt
and try to re-auth themselves on the master.

Because all minions always receive all publications, every single minion who
can not decrypt a/the publication, will try to re-auth immediately, causing
thousands of minions trying to re-auth at once. This can be avoided by
setting the

.. code-block:: yaml

    random_reauth_delay: 60

in the minions configuration file to a higher value and stagger the amount
of re-auth attempts. Increasing this value will of course increase the time
it takes, until all minions are reachable again via salt commands.

But this is not only the salt part that requires tuning. The ZeroMQ socket
settings on the minion side should also be tweaked.

As described before, the master and the minions are permanently connected
with each other through the publisher on port 4505.  Restarting the salt-master
service shuts down the publishing-socket on the masters only to bring it
back up within seconds.

This change is detected by the ZeroMQ-socket on the minions end. Not being
connected does not really matter to the minion pull-socket or the minion.
The pull-socket just waits and tries to reconnect, while the minion just does
not receive publications while not being connected.

In this situation, its the pull-sockets reconnect value (default 100ms)
that might be too low. With each and every minions pull-socket trying to
reconnect within 100ms as soon as the master publisher port comes back up,
its a piece of cake to cause a syn-flood on the masters publishing port.

To tune the minions sockets reconnect attempts, there are a few values in
the sample configuration file (default values)

.. code-block:: yaml

    recon_default: 100ms
    recon_max: 5000
    recon_randomize: True


- recon_default: the default value the socket should use, i.e. 100ms
- recon_max: the max value that the socket should use as a delay before trying to reconnect
- recon_randomize: enables randomization between recon_default and recon_max

To tune this values to an existing environment, a few decision have to be made.


1. How long can one wait, before the minions should be back online and reachable with salt?

2. How many reconnects can the master handle without detecting a syn flood?

These questions can not be answered generally. Their answers highly depend
on the hardware and the administrators requirements.

Here is an example scenario with the goal, to have all minions reconnect
within a 60 second time-frame on a salt-master service restart.

.. code-block:: yaml

    recon_default: 1000
    recon_max: 59000
    recon_randomize: True

Each minion will have a randomized reconnect value between 'recon_default'
and 'recon_default + recon_max', which in this example means between 1000ms
and 60000ms (or between 1 and 60 seconds). The generated random-value will
be doubled after each attempt to reconnect (ZeroMQ default behaviour).

Lets say the generated random value is 11 seconds (or 11000ms).

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

.. code-block:: math

    1000/60 = ~16 
    
round about 16 connection attempts a second. These values should be altered to
values that match your environment. Keep in mind though, that it may grow over
time and that more minions might raise the problem again.


Too many minions returning at once
==================================
This can also happen during the testing phase, if all minions are addressed at
once with

.. code-block:: bash

    $ salt * test.ping

it may cause thousands of minions trying to return their data to the salt-master
open port 4506. Also causing a syn-flood if the master cant handle that many
returns at once.

This can be easily avoided with salts batch mode:

.. code-block:: bash

    $ salt * test.ping -b 50

This will only address 50 minions at once while looping through all addressed
minions.


Too little ressources
=====================
The masters resources always have to match the environment. There is no way
to give good advise without knowing the environment the master is supposed to
run in.  But here are some general tuning tips for different situations:

The master has little CPU-Power
-------------------------------
Salt uses RSA-Key-Pairs on the masters and minions end. Both generate 4096
bit key-pairs on first start. While the key-size for the master is currently
not configurable, the minions keysize can be configured with different
key-sizes. For example with a 2048 bit key:

.. code-block:: yaml

    keysize: 2048

With thousands of decrpytions, the amount of time that can be saved on the
masters end should not be neglected. See here for reference:
`Pull Request 9235 <https://github.com/saltstack/salt/pull/9235>`_ how much
influence the key-size can have.

Downsizing the salt-masters key is not that important, because the minions
do not encrypt as many messages as the master does.

The master has slow disks
-------------------------
By default, the master saves every minions return for every job in its
job-cache. The cache can then be used later, to lookup results for previous
jobs. The default directory for this is:

.. code-block:: yaml

    cachedir: /var/cache/salt

and then in the ``/proc`` directory.

Each jobs return for every minion is saved in a single file. Over time this
directory can grow immensly, depending on the number of published jobs and if

.. code-block:: yaml
    
    keep_jobs: 24

was raised to have a longer job-history than 24 hours. Saving the files is
not that expensive, but cleaning up can be over time.

.. code-block:: math
    
    250 jobs/day * 2000 minions returns = 500.000 files a day

If no job history is needed, the job cache can be disabled:

.. code-block:: yaml
   
   job_cache: False


For legal reasons, it might be required, that there is a permanent job-cache
for a certain amount of time. If thats the case, there are currently only two
alternatives.

- use returners and disable the job-cache
- use salt-eventsd and disable the job-cache

The first one has the disadvantage of losing the encryption used by salt
unless the returner implements it.

The second one is not part of the official salt environment and therefore
not broadly known on the mailing list or by the core salt-developers.

`salt-eventsd on github <https://github.com/felskrone/salt/salt-eventsd>`_
