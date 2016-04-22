.. _get-started:

=========
SaltStack
=========
Salt, a new approach to infrastructure management, is easy enough to get
running in minutes, scalable enough to manage tens of thousands of servers,
and fast enough to communicate with those servers in *seconds*.

Salt delivers a dynamic communication bus for infrastructures that can be used
for orchestration, remote execution, configuration management and much more.

.. toctree::
    :maxdepth: 1

    topics/index

Get Started
===========
The Get Started Guide shows you how to:

* Install and configure SaltStack
* Remotely execute commands across all managed systems
* Design, develop, and deploy system configurations

.. toctree::
    :maxdepth: 1

    Get Started Guide <https://docs.saltstack.com/en/getstarted/>

If you just want to get Salt installed and start using it, *Salt in 10 minutes*
gets you up and running quickly.

.. toctree::
    :maxdepth: 1

    topics/tutorials/walkthrough

Install Salt
============
**Latest Stable Release**: |current_release_doc|

The installation document, found in the following link,  outlines where to
obtain packages and installation specifics for platforms:

* :ref:`Installation <installation>`

The Salt Bootstrap project, found in the following repository, is a single
shell script, which automates the install correctly on  multiple platforms:

* https://github.com/saltstack/salt-bootstrap

Demo Environments
=================
You can download one of the following `Vagrant <http://vagrantup.com>`_
projects to quickly set up a Salt demo environment:

- https://github.com/UtahDave/salt-vagrant-demo
- https://github.com/UtahDave/salt-vagrant-lxc

Example Formulas
================
A Github repo that contains a number of community-maintained formulas is
available at https://github.com/saltstack-formulas. Contributions are welcome!

A Github repo that contains formulas to install a number of Windows
applications is available at https://github.com/saltstack/salt-winrepo-ng. Note
that Salt makes this repo :ref:`available <windows-package-manager>` to your
Windows minions, and contributions are welcome!

Mailing List
============
Join the `salt-users mailing list`_. It is the best place to ask questions
about Salt and see whats going on with Salt development! The Salt mailing list
is hosted by Google Groups. It is open to new members.

https://groups.google.com/forum/#!forum/salt-users

.. _`salt-users mailing list`: https://groups.google.com/forum/#!forum/salt-users

There is also a low-traffic list used to announce new releases
called `salt-announce`_

https://groups.google.com/forum/#!forum/salt-announce

.. _`salt-announce`: https://groups.google.com/forum/#!forum/salt-announce

IRC
===
The ``#salt`` IRC channel is hosted on the popular `Freenode`__ network. You
can use the `Freenode webchat client`__ right from your browser.

`Logs of the IRC channel activity`__ are being collected courtesy of Moritz Lenz.

.. __: http://freenode.net/irc_servers.shtml
.. __: http://webchat.freenode.net/?channels=salt&uio=Mj10cnVlJjk9dHJ1ZSYxMD10cnVl83
.. __: http://irclog.perlgeek.de/salt/

If you wish to discuss the development of Salt itself join us in
``#salt-devel``.

Follow on GitHub
================
The Salt code is developed via GitHub. Follow Salt for constant updates on what
is happening in Salt development:

|saltrepo|

Hack the Source
===============
If you want to get involved with the development of source code or the
documentation efforts, please review the :ref:`Developing Salt Tutorial
<developing-tutorial>`.

