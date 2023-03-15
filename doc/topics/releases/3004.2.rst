.. _release-3004-2:

=========================
Salt 3004.2 Release Notes
=========================

Version 3004.2 is a CVE security fix release for :ref:`3004 <release-3004>`.

Fixed
-----

- Expand environment variables in the root_dir registry key (#61445)
- Update Markup and contextfunction imports for jinja versions >=3.1. (#61848)
- Fix bug in tcp transport (#61865)
- Make sure the correct key is being used when verifying or validating communication, eg. when a Salt syndic is involved use syndic_master.pub and when a Salt minion is involved use minion_master.pub. (#61868)

Security
--------

- Fixed PAM auth to reject auth attempt if user account is locked. (cve-2022-22967)
