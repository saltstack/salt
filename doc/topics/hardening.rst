.. _hardening-salt:

==============
Hardening Salt
==============

This topic contains tips you can use to secure and harden your Salt
environment. How you best secure and harden your Salt environment depends
heavily on how you use Salt, where you use Salt, how your team is structured,
where you get data from, and what kinds of access (internal and external) you
require.

.. warning::

    For historical reasons, Salt requires PyCrypto as a "lowest common
    denominator". However, `PyCrypto is unmaintained`_ and best practice is to
    manually upgrade to use a more maintained library such as `PyCryptodome`_. See
    `Issue #52674`_ and `Issue #54115`_ for more info


.. _PyCrypto is unmaintained: https://github.com/dlitz/pycrypto/issues/301#issue-551975699
.. _PyCryptodome: https://pypi.org/project/pycryptodome/
.. _Issue #52674: https://github.com/saltstack/salt/issues/52674
.. _Issue #54115: https://github.com/saltstack/salt/issues/54115


General hardening tips
======================

- Restrict who can directly log into your Salt master system.
- Use SSH keys secured with a passphrase to gain access to the Salt master system.
- Track and secure SSH keys and any other login credentials you and your team
  need to gain access to the Salt master system.
- Use a hardened bastion server or a VPN to restrict direct access to the Salt
  master from the internet.
- Don't expose the Salt master any more than what is required.
- Harden the system as you would with any high-priority target.
- Keep the system patched and up-to-date.
- Use tight firewall rules.

Salt hardening tips
===================

- Subscribe to `salt-users`_ or `salt-announce`_ so you know when new Salt
  releases are available. Keep your systems up-to-date with the latest patches.
- Use Salt's Client :ref:`ACL system <acl>` to avoid having to give out root
  access in order to run Salt commands.
- Use Salt's Client :ref:`ACL system <acl>` to restrict which users can run what commands.
- Use :ref:`external Pillar <all-salt.pillars>` to pull data into Salt from
  external sources so that non-sysadmins (other teams, junior admins,
  developers, etc) can provide configuration data without needing access to the
  Salt master.
- Make heavy use of SLS files that are version-controlled and go through
  a peer-review/code-review process before they're deployed and run in
  production. This is good advice even for "one-off" CLI commands because it
  helps mitigate typos and mistakes.
- Use salt-api, SSL, and restrict authentication with the :ref:`external auth
  <acl-eauth>` system if you need to expose your Salt master to external
  services.
- Make use of Salt's event system and :ref:`reactor <reactor>` to allow minions
  to signal the Salt master without requiring direct access.
- Run the ``salt-master`` daemon as non-root.
- Disable which modules are loaded onto minions with the
  :conf_minion:`disable_modules` setting. (for example, disable the ``cmd``
  module if it makes sense in your environment.)
- Look through the fully-commented sample :ref:`master
  <configuration-examples-master>` and :ref:`minion
  <configuration-examples-minion>` config files. There are many options for
  securing an installation.
- Run :ref:`masterless-mode <tutorial-standalone-minion>` minions on
  particularly sensitive minions. There is also :ref:`salt-ssh` or the
  :mod:`modules.sudo <salt.modules.sudo>` if you need to further restrict
  a minion.

.. _salt-users: https://groups.google.com/forum/#!forum/salt-users
.. _salt-announce: https://groups.google.com/forum/#!forum/salt-announce
