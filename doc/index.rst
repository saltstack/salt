.. _index:

.. rubric:: Simplified system communication

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
.. _`slides`: https://github.com/downloads/thatch45/salt/Salt.pdf

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
    :maxdepth: 1

    ref/index
    ref/python-api
    ref/modules/index
    ref/returners/index
    ref/grains
    ref/renderers
    ref/states
    ref/runners


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
