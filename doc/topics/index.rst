.. _`Apache 2.0 license`: http://www.apache.org/licenses/LICENSE-2.0.html

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
