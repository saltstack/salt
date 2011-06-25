.. _index:

====
Salt
====

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


Getting started
===============

.. sidebar:: Getting help

    * Watch a presentation on Salt: `video`_ | `slides`_ (PDF).

    * Join the :ref:`salt-users mailing list <community-mailing-list>`.

    * Chat via IRC :ref:`on OFTC in #salt <community-irc>`.

    * Report any bugs on the `GitHub issues page`_.

.. _`video`: http://blip.tv/thomas-s-hatch/salt-0-8-7-presentation-5180182
.. _`slides`: https://github.com/downloads/thatch45/salt/Salt.pdf
.. _`GitHub issues page`: https://github.com/thatch45/salt/issues


New users should start here

.. toctree::
    :maxdepth: 1

    topics/index
    topics/tutorial


Using Salt
==========

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
    ref/states
    ref/renderers
    ref/python-api

* **Modules:**
  :doc:`Writing modules <ref/modules/index>`
  | :doc:`full list of modules <ref/modules/modules>`
* **Grains:**
  :doc:`Grains <ref/grains>` 
* **Returners:**
  :doc:`Writing returners <ref/returners/index>`
  | :doc:`full list of returners <ref/returners/returners>`
* **State enforcement:**
  :doc:`States <ref/states>`
  | :doc:`Renderers <ref/renderers>`
* **Python API:**
  :doc:`Python API <ref/python-api>`

Getting involved
================

.. toctree::
    :maxdepth: 1

    topics/community
    topics/releases/index


Indices, glossary and tables
============================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
