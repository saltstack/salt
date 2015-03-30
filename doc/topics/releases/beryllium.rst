=======================================
Salt Release Notes - Codename Beryllium
=======================================

Core Changes
============

- Add system version info to ``versions_report``, which appears in both ``salt
  --versions-report`` and ``salt '*' test.versions_report``. Also added is an
  alias ``test.versions`` to ``test.versions_report``. (:issue:`21906`)

- Add colorized console logging support.  This is activated by using
  ``%(colorlevel)s``, ``%(colorname)s``, ``%(colorprocess)s``, ``%(colormsg)s``
  in ``log_fmt_console`` in the config file for any of ``salt-master``,
  ``salt-minion``, and ``salt-cloud``.

JBoss 7 State
=============

- Remove unused argument ``timeout`` in jboss7.status
