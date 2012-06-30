=============
What is Salt?
=============

.. image:: https://secure.travis-ci.org/saltstack/salt.png?branch=develop
   :target: http://travis-ci.org/saltstack/salt

.. rubric:: We’re not just talking about NaCl.

Distributed Remote Execution
============================

Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in the
world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds, or even thousands of individual
servers. It handles them quickly and through a simple yet manageable interface.

Simplicity
==========

Versatility between massive scale deployments and smaller systems may seem
daunting, but Salt is very simple to set up and maintain, regardless of the
size of the project. The architecture of Salt is designed to work with any
number of servers, from a handful of local network systems to international
deployments across disparate datacenters. The topology is a simple
server/client model with the needed functionality built into a single set of
daemons. While the default configuration will work with little to no
modification, Salt can be fine tuned to meet specific needs.

Parallel Execution
==================

The core function of Salt is to enable remote commands to be called in parallel
rather than in serial. It does this over a secure and encrypted protocol using
the smallest and fastest network payloads possible. All of this is possible
and Salt still manages to have a simple interface for developers. Salt also
introduces more granular controls to the realm of remote execution,
allowing for commands to be executed in parallel and for systems to be targeted
based on more than just hostname, but by live system properties.

Building on Proven Technology
=============================

Salt takes advantage of a number of technologies and techniques. The networking
layer is built with the excellent `ZeroMQ`_ networking library. Salt itself
contains a viable, and transparent, ZeroMQ broker inside the daemon. Salt uses
public keys for authentication with the master daemon, then uses faster AES
encryption for payload communication. This means that authentication and
encryption are also built into Salt. Salt takes advantage of communication via
the most excellent `msgpack`_ library, enabling fast and light network traffic.

.. _`ZeroMQ`: http://www.zeromq.org/

.. _`msgpack`: http://msgpack.org/


Python Client Interface
=======================

Salt execution routines can be written as plain Python modules and the data
collected from execution can be sent back to the master server, or any
arbitrary program. Salt can be called from a simple Python API, or from the
command line. This makes it easy to execute one-off commands as well as
operate as an integral part of a larger application.


Fast, Flexible, Scalable, Secure
================================

The result is a system that can execute commands across groups of
varying size, from very few to very many servers at considerably high
speed. We consider speed to be a feature, not an afterthought. Salt’s
unique architecture brings together the best of the remote execution
world, amplifies its capabilities and expands its range, resulting in
this system that is as versatile as it is practical. Last but not least,
security is an intrinsic part of Salt and something not just
influencing how source code is written and how tests are done, but
also something that defines the overall architecture and has heavy
influence on the core design tenets.

Open
====

Salt is developed under the `Apache 2.0 licence`_, and can be used for
open and proprietary projects. Please submit your expansions back to
the Salt project so that we can all benefit together as Salt grows.
Finally, please sprinkle some Salt around your systems and let the
deliciousness come forth.

.. _`Apache 2.0 licence`: http://www.apache.org/licenses/LICENSE-2.0.html
