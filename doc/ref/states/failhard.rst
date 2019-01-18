======================
Failhard Global Option
======================

Normally, when a state fails Salt continues to execute the remainder of the
defined states and will only refuse to execute states that require the failed
state.

But the situation may exist, where you would want all state execution to stop
if a single state execution fails. The capability to do this is called
``failing hard``.

.. _state-level-failhard:

State Level Failhard
====================

A single state can have a failhard set, this means that if this individual
state fails that all state execution will immediately stop. This is a great
thing to do if there is a state that sets up a critical config file and
setting a require for each state that reads the config would be cumbersome.
A good example of this would be setting up a package manager early on:

.. code-block:: yaml

    /etc/yum.repos.d/company.repo:
      file.managed:
        - source: salt://company/yumrepo.conf
        - user: root
        - group: root
        - mode: 644
        - order: 1
        - failhard: True

In this situation, the yum repo is going to be configured before other states,
and if it fails to lay down the config file, than no other states will be
executed.
It is possible to override a Global Failhard (see below) by explicitly setting
it to ``False`` in the state.

.. _global-failhard:

Global Failhard
===============

It may be desired to have failhard be applied to every state that is executed,
if this is the case, then failhard can be set in the master configuration
file. Setting failhard in the master configuration file will result in failing
hard when any minion gathering states from the master have a state fail.

This is NOT the default behavior, normally Salt will only fail states that
require a failed state.

Using the global failhard is generally not recommended, since it can result
in states not being executed or even checked. It can also be confusing to
see states failhard if an admin is not actively aware that the failhard has
been set.

To use the global failhard set :conf_master:`failhard` to ``True`` in the
master configuration file.
