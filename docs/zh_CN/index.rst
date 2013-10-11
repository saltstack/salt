:orphan:

.. _contents:

.. _what-is-salt-stack:

Salt Stack是什么?
===================

salt是一个新的基础平台管理工具。只需花费数分钟即可运行起来, 扩展性足以支撑管理上万台服务器，数秒钟即可完成数据传递.


Salt delivers a dynamic communication bus for infrastructures that can be used
for orchestration, remote execution, configuration management and much more.

.. seealso:: 离线文档 

    下载Salt文档的副本:

    * `PDF`_
    * `ePub`_

.. _`PDF`: https://media.readthedocs.org/pdf/salt/latest/salt.pdf
.. _`ePub`: https://media.readthedocs.org/epub/salt/latest/salt.epub

.. _download:

下载
========

Salt源码版本可以通过PyPI下载:

    https://pypi.python.org/pypi/salt

安装文档中将给出各操作系统平台下如何得到包及对应的安装方法:    

    :doc:`安装 </topics/installation/index>`

Salt Bootstrap项目是一个以在各平台下能够正确的自动完成Salt安装为目标的shell脚本:    

    https://github.com/saltstack/salt-bootstrap

.. _getting-started:    

入门指南
========================

本教程将帮你快速开始使用Salt并了解到关于Salt的基础知识:

:doc:`官方Salt教程 </topics/tutorials/walkthrough>`

Additional tutorials are available when getting started with Salt

States - Salt配置管理系统:
    - :doc:`States入门 <topics/tutorials/starting_states>`
    - :doc:`基本配置管理 <topics/tutorials/states_pt1>`
    - :doc:`Less basic config management <topics/tutorials/states_pt2>`
    - :doc:`高级技巧 <topics/tutorials/states_pt3>`
    - :doc:`Salt Fileserver Path Inheritance <topics/tutorials/states_pt4>`

无Master(Masterless)快速入门:
    :doc:`Salt快速入门  </topics/tutorials/quickstart>`

所有的教程都可以在以下列表中找到:
    :doc:`Salt教程列表 <topics/tutorials/index>`

.. _salt-in-depth:    

深入Salt
=============

Setting up and using Salt is a simple task but its capabilities run much, much
deeper. These documents will lead to a greater understating of how Salt will
empower infrastructure management.

.. _remote-execution:

远程执行
----------------

Remote execution is the core function of Salt. Running pre-defined or
arbitrary commands on remote hosts.

**Modules**
    Salt modules are the core of remote execution. They provide
    functionality such as installing packages, restarting a service,
    running a remote command, transferring files, and infinitely more.

    :doc:`Full list of modules </ref/modules/all/index>`
        The giant list of core modules that ship with Salt

    :doc:`Writing modules <ref/modules/index>`
        A guide on how to write Salt modules.

**Returners**
    Salt returners allow saving minion responses in various datastores or
    to various locations in addition to display at the CLI.

    :doc:`Full list of returners </ref/returners/all/index>`
        Store minion responses in Redis, Mongo, Cassandra, SQL or more.

    :doc:`Writing returners <ref/returners/index>`
        Extending Salt to communicate with more interfaces is easy, new
        databases can be supported or custom interfaces can be easily
        communicated with.

Targeting
---------

:doc:`Targeting </topics/targeting/index>` is specifying which minions
should execute commands or manage server configuration.

:doc:`Globbing and regex </topics/targeting/globbing>`
    Match minions using globbing and regular expressions.

:doc:`Grains </topics/targeting/grains>`
    Match minions using bits of static information about the minion such as
    OS, software versions, virtualization, CPU, memory, and much more.

:doc:`Node groups </topics/targeting/nodegroups>`
    Statically define groups of minions.

:doc:`Compound matchers </topics/targeting/compound>`
    Combine the above matchers as a single target.

:doc:`Batching execution </topics/targeting/batch>`
    Loop through all matching minions so that only a subset are executing a
    command at one time.

.. configuration-management:    

配置管理
------------------------

Building on the remote execution core is a robust and flexible configuration
management framework. Execution happens on the minions allowing effortless,
simultaneous configuration of tens of thousands of hosts.

**States**
    Express the state of a host using small, easy to read, easy to
    understand configuration files. *No programming required*.

    :doc:`Full list of states <ref/states/all/index>`
        Install packages, create users, transfer files, start services, and
        much more.

    :doc:`Pillar System <topics/pillar/index>`
        Salt's Pillar system

    :doc:`States Overview<ref/states/index>`
        An overview of States and some of the core components.

    :doc:`Highstate data structure <ref/states/highstate>`
        A dry vocabulary and technical representation of the configuration
        format that states represent.

    :doc:`Writing states <ref/states/writing>`
        A guide on how to write Salt state modules. Extending Salt to directly
        manage in more software is easy.

**Renderers**
    Write state configuration files in the language, templating engine, or
    file type of choice. Salt's configuration management system is, under the
    hood, language agnostic.

    :doc:`Full list of renderers <ref/renderers/all/index>`
        YAML is not the only choice, many systems are available, from
        alternative templating engines to the PyDSL language for rendering
        sls formulas.

    :doc:`Renderers <ref/renderers/index>`
        Salt states are only concerned with the ultimate highstate data
        structure. How that data structure is created is not important.

.. miscellaneous-topic:

其他主题
--------------------

Salt is many splendid things.

:doc:`File Server <ref/file_server/index>`
    Salt can easily and quickly transfer files (in fact, that's how Salt
    States work). Even under heavy load, files are chunked and served.

:doc:`Syndic <ref/syndic>`
    A seamless master of masters. Scale Salt to tens of thousands of hosts or
    across many different networks.

:doc:`Peer Communication <ref/peer>`
    Allow minions to communicate amongst themselves. For example, configure
    one minion by querying live data from all the others. With great power
    comes great responsibility.

:doc:`Reactor System <topics/reactor/index>`
    The reactor system allows for Salt to create a self aware environment
    by hooking infrastructure events into actions.

:doc:`Firewall Settings and Salt <topics/tutorials/firewall>`
    A tutorial covering how to properly firewall a Salt Master server.

:doc:`Scheduling Executions (like states)<topics/jobs/schedule>`
    The schedule system in Salt allows for executions to be run of all sorts
    from the master or minion at automatic intervals.

:doc:`Network topology <ref/topology>`
    At it's core, Salt is a highly scalable communication layer built on
    top of ZeroMQ that enables remote execution and configuration
    management. The possibilities are endless and Salt's future looks
    bright.

:doc:`Testing Salt <topics/tests/index>`
    A howto for writing unit tests and integration tests.

:ref:`Python API interface <python-api>`
    Use Salt programmatically from scripts and programs easily and
    simply via ``import salt``.

:doc:`Automatic Updates and Frozen Binary Deployments <topics/tutorials/esky>`
    Use a frozen install to make deployments easier (Even on Windows!). Or
    take advantage of automatic updates to keep minions running the latest
    builds.

:doc:`Windows Software Manager / Package Repository <ref/windows-package-manager>`
    Looking for an easy way to manage software on Windows machines?
    Search no more! Salt has an integrated software package manager for
    Windows machines! Install software hosted on the master, somewhere on the
    network, or any HTTP, HTTPS, or ftp server.

.. reference:    

Reference
---------

:doc:`Command-line interface <ref/cli/index>`
    Read the Salt manpages.

:doc:`Full list of master settings <ref/configuration/master>`
    Read through the heavily-commented master configuration file.

:doc:`Full list of minion settings <ref/configuration/minion>`
    Read through the heavily-commented minion configuration file.

:doc:`Full table of contents </contents>`
    Dense but complete.

FAQ
===

See :doc:`here <faq>` for a list of Frequently Asked Questions.

More information about the project
==================================

:doc:`Release notes </topics/releases/index>`
    Living history of Salt Stack.

:doc:`Community </topics/community>`
    How to get involved.

:doc:`Salt Development </topics/development/index>`
    Information for Hacking on Salt

.. _`salt-contrib`: https://github.com/saltstack/salt-contrib
.. _`salt-states`: https://github.com/saltstack/salt-states
