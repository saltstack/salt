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
    :maxdepth: 1

    ref/index
    ref/python-api
    ref/modules/index
    ref/returners/index
    ref/grains
    ref/renderers
    ref/states


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
