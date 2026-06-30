.. _security-index:

================
Salt security
================

The Salt security documentation is split into three sections.

* :ref:`security-threat-model` describes what Salt's wire protocol
  protects, what the master-side ACL system protects, and the
  operator-side trust boundaries that fall outside both.
* :ref:`security-key-lifecycle` is the operational reference for
  accepting, rejecting, rotating, regenerating, and denying minion
  keys, including the surprise edge cases (ID collision, grain
  flapping, ``rejected_retry``).
* The disclosure policy and historic CVE feed are below on this
  page.

.. toctree::
    :maxdepth: 1

    threat-model
    key-lifecycle


.. _disclosure:

==========================
Security disclosure policy
==========================

The canonical Salt security policy, contact information and PGP public key
live in the ``SECURITY.md`` file at the root of the Salt source tree.

To avoid this page drifting out of sync with the live document, see:

* `SECURITY.md on master <https://github.com/saltstack/salt/blob/master/SECURITY.md>`_

That file is the authoritative source for:

* the security contact email
* the current GPG key ID and fingerprint
* the full ASCII-armored GPG public key
* the security response procedure

.. _saltstack_security_announcements:

Receiving security announcements
================================

For receiving security announcements, see the ``SECURITY.md`` file linked
above. Notifications are sent to the ``salt-packagers``, ``salt-users`` and
``salt-announce`` mailing lists.
