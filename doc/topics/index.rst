====================
Introduction to Salt
====================

.. rubric:: We’re not just talking about NaCl.

The 30 second summary
=====================

Salt is:

* **A configuration management system.** Salt is capable of maintaining remote
  nodes in defined states. For example, it can ensure that specific packages are
  installed and that specific services are running.

* **A distributed remote execution system used to execute commands and
  query data on remote nodes.** Salt can query and execute commands either on
  individual nodes or by using an arbitrary selection criteria.

It was developed in order to bring the best solutions found in the
world of remote execution together and make them better, faster, and more
malleable. Salt accomplishes this through its ability to handle large loads of
information, and not just dozens but hundreds and even thousands of individual
servers quickly through a simple and manageable interface.

Simplicity
==========
Providing versatility between massive scale deployments and smaller systems may seem
daunting, but Salt is very simple to set up and maintain, regardless of the
size of the project. The architecture of Salt is designed to work with any
number of servers, from a handful of local network systems to international
deployments across different data centers. The topology is a simple
server/client model with the needed functionality built into a single set of
daemons. While the default configuration will work with little to no
modification, Salt can be fine tuned to meet specific needs.

Parallel execution
==================
The core functions of Salt:

* enable commands to remote systems to be called in parallel rather than serially
* use a secure and encrypted protocol
* use the smallest and fastest network payloads possible
* provide a simple programming interface

Salt also introduces more granular controls to the realm of remote
execution, allowing systems to be targeted not just by hostname, but
also by system properties.

Builds on proven technology
===========================
Salt takes advantage of a number of technologies and techniques. The
networking layer is built with the excellent `ZeroMQ`_ networking
library, so the Salt daemon includes a viable and transparent AMQ
broker. Salt uses public keys for authentication with the master
daemon, then uses faster `AES`_ encryption for payload communication;
authentication and encryption are integral to Salt.  Salt takes
advantage of communication via `msgpack`_, enabling fast and light
network traffic.

.. _`ZeroMQ`: https://zeromq.org/
.. _`msgpack`: https://msgpack.org/
.. _`AES`: https://en.wikipedia.org/wiki/Advanced_Encryption_Standard

Python client interface
=======================
In order to allow for simple expansion, Salt execution routines can be written
as plain Python modules. The data collected from Salt executions can be sent
back to the master server, or to any arbitrary program. Salt can be called from
a simple Python API, or from the command line, so that Salt can be used to
execute one-off commands as well as operate as an integral part of a larger
application.

Fast, flexible, scalable
========================
The result is a system that can execute commands at high speed on
target server groups ranging from one to very many servers. Salt is
very fast, easy to set up, amazingly malleable and provides a single
remote execution architecture that can manage the diverse
requirements of any number of servers.  The Salt infrastructure
brings together the best of the remote execution world, amplifies its
capabilities and expands its range, resulting in a system that is as
versatile as it is practical, suitable for any network.

Open
====
Salt is developed under the `Apache 2.0 license`_, and can be used for
open and proprietary projects. Please submit your expansions back to
the Salt project so that we can all benefit together as Salt grows.
Please feel free to sprinkle Salt around your systems and let the
deliciousness come forth.

.. _salt-community:

Salt Community
==============

Join the Salt!

There are many ways to participate in and communicate with the Salt community.

Salt has an active IRC channel and a mailing list.

Mailing List
============

Join the `salt-users mailing list`_. It is the best place to ask questions
about Salt and see whats going on with Salt development! The Salt mailing list
is hosted by Google Groups. It is open to new members.

.. _`salt-users mailing list`: https://groups.google.com/forum/#!forum/salt-users

Additionally, all users of Salt should be subscribed to the Announcements mailing
list which contains important updates about Salt, such as new releaes and
security-related announcements. This list is low-traffic.

.. _`salt-announce mailing list`: https://groups.google.com/forum/#!forum/salt-announce


IRC
===

The ``#salt`` IRC channel is hosted on the popular `Freenode`_ network. You
can use the `Freenode webchat client`_ right from your browser.  `Logs of the
IRC channel activity`_ are also available.

.. _Freenode: http://freenode.net/irc_servers.shtml
.. _`Freenode webchat client`: https://webchat.freenode.net/#salt
.. _`Logs of the IRC channel activity`: https://freenode.logbot.info/salt/

If you wish to discuss the development of Salt itself join us in
``#salt-devel``.


Follow on Github
================

The Salt code is developed via Github. Follow Salt for constant updates on what
is happening in Salt development:

|saltrepo|

Long-term planning and strategic decisions are handled via Salt Enhancement Proposals
and can be found on GitHub.

.. _`Salt Enhancement Proposals`: https://github.com/saltstack/salt-enhancement-proposals


Blogs
=====

SaltStack Inc. keeps a `blog`_ with recent news and advancements:

http://www.saltstack.com/blog/

.. _`blog`: http://www.saltstack.com/blog/


Example Salt States
===================

The official ``salt-states`` repository is:
https://github.com/SS-archive/salt-states

A few examples of salt states from the community:

* https://github.com/blast-hardcheese/blast-salt-states
* https://github.com/kevingranade/kevingranade-salt-state
* https://github.com/uggedal/states
* https://github.com/mattmcclean/salt-openstack/tree/master/salt
* https://github.com/rentalita/ubuntu-setup/
* https://github.com/brutasse/states
* https://github.com/bclermont/states
* https://github.com/pcrews/salt-data

Follow on Open Hub
==================

https://www.openhub.net/p/salt

Other community links
=====================

- `Salt Stack Inc. <http://www.saltstack.com>`_
- `Subreddit <http://www.reddit.com/r/saltstack>`_
- `YouTube <https://www.youtube.com/user/SaltStack>`_
- `Facebook <https://www.facebook.com/SaltStack>`_
- `Twitter <https://twitter.com/SaltStackInc>`_
- `Wikipedia page <https://en.wikipedia.org/wiki/Salt_(software)>`_
- `Stack Overflow <https://stackoverflow.com/questions/tagged/salt-stack>`_

Hack the Source
===============

If you want to get involved with the development of source code or the
documentation efforts, please review the :ref:`contributing documentation
<contributing>`!

.. _`Apache 2.0 license`: http://www.apache.org/licenses/LICENSE-2.0.html
