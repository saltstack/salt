.. _release-3002-9:


========================
Salt 3002.9 (2022-05-25)
========================

Version 3002.9 is a CVE security fix release for :ref:`3002 <release-3002>`.

Fixed
-----

- Fixed an error when running on CentOS Stream 8. (#59161)
- Fix bug in tcp transport (#61865)
- Make sure the correct key is being used when verifying or validating communication, eg. when a Salt syndic is involved use syndic_master.pub and when a Salt minion is involved use minion_master.pub. (#61868)


Security
--------

- Fixed PAM auth to reject auth attempt if user account is locked. (cve-2022-22967)
