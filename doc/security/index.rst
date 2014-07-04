.. _disclosure:

==========================
Security disclosure policy
==========================

:email: security@saltstack.com
:gpg key ID: 4EA0793D
:gpg key fingerprint: ``8ABE 4EFC F0F4 B24B FF2A  AF90 D570 F2D3 4EA0 793D``

The SaltStack Security Team is available at security@saltstack.com for
security-related bug reports or questions.

We request the disclosure of any security-related bugs or issues be reported
non-publicly until such time as the issue can be resolved and a security-fix
release can be prepared. At that time we will release the fix and make a public
announcement with upgrade instructions and download locations.

Security response proceedure
============================

SaltStack takes security and the trust of our customers and users very
seriously. Our disclosure policy is intended to resolve security issues as
quickly and safely as is possible.

1.  A security report sent to security@saltstack.com is assigned to a team
    member. This person is the primary contact for questions and will
    coordinate the fix, release, and announcement.

2.  The reported issue is reproduced and confirmed. A list of affected projects
    and releases is made.

3.  Fixes are implemented for all affected projects and releases that are
    actively supported. Back-ports of the fix are made to any old releases that
    are actively supported.

4.  Packagers are notified via the |salt-packagers| mailing list that an issue
    was reported and resolved, and that an announcement is incoming.

5.  A new release is created and pushed to all affected repositories. The
    release documentation provides a full description of the issue, plus any
    upgrade instructions or other relevant details.

6.  An announcement is made to the |salt-users| and |salt-announce| mailing
    lists. The announcement contains a description of the issue and a link to
    the full release documentation and download locations.

Receiving security announcemnts
===============================

The fastest place to receive security announcements is via the |salt-announce|
mailing list. This list is low-traffic.
