.. _index:

Salt is a powerful remote execution manager that can be used to administer
servers in a fast and efficient way.

Salt allows commands to be executed across large groups of servers. This means
systems can be easily managed, but data can also be easily gathered. Quick
introspection into running systems becomes a reality.

Remote execution is usually used to set up a certain state on a remote system.
Salt addresses this problem as well, the salt state system uses salt state
files to define the state a server needs to be in.

Between the remote execution system, and state management Salt addresses the
backbone of cloud and data center management.

News
----

0.9.2 released!

Release announcement:

.. toctree::
    :maxdepth: 1

    topics/releases/0.9.2

Download
--------

The latest Salt is 0.9.2:

|latest|

Additional packages can be downloaded from the download page:

.. toctree::
    :maxdepth: 1

    topics/download

Getting Started
===============

A number of resources are available to get going with Salt.

Quick Start
-----------

If you want to get set up quickly and try out Salt, follow the tutorial.

.. toctree::
    :maxdepth: 1

    topics/tutorial

Salt in Depth
=============

While using and setting up Salt is a simple task, the capabilities of Salt
run much deeper.

Gaining a better understanding of how Salt works will allow you to get much
more out of Salt.

Screencasts and Presentations
-----------------------------

Presentation at SLLUG in May 2011
`video`_ | `slides`_ (PDF)

.. _`video`: http://blip.tv/thomas-s-hatch/salt-0-8-7-presentation-5180182
.. _`slides`: :download:`Salt.pdf`

Configuration and CLI Usage
---------------------------

.. toctree::
    :maxdepth: 1

    ref/configuration/index
    ref/cli/index

Extending Salt
==============

Writing your own customizations on top of Salt

.. toctree::
    :hidden:

    ref/index
    ref/modules/index
    ref/grains
    ref/returners/index
    ref/states/index
    ref/runners
    ref/renderers
    ref/python-api
    ref/file_server/index

* **Modules:**
  :doc:`Writing modules <ref/modules/index>`
  | :doc:`full list of modules <ref/modules/modules>`
* **Grains:**
  :doc:`Grains <ref/grains>` 
* **Returners:**
  :doc:`Writing returners <ref/returners/index>`
  | :doc:`full list of returners <ref/returners/returners>`
* **State enforcement:**
  :doc:`States <ref/states/index>`
  | :doc:`Renderers <ref/renderers>`
* **Python API:**
  :doc:`Python API <ref/python-api>`
* **File Server:**
  :doc:`File Server <ref/file_server/index>`

Salt Network Topology
=====================

Salt can be extended beyond a simple master commanding minions, for more
information read up on the peer and syndic interfaces.

.. toctree::
    :maxdepth: 1

    ref/syndic
    ref/peer

Getting Involved
================

There are many ways to interact with the Salt community.

.. toctree::
    :maxdepth: 1

    topics/community
    topics/releases/index


Indices, glossary and tables
============================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
