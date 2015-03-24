=======================================
Salt Release Notes - Codename Beryllium
=======================================

Core Changes
=============

- Add system version info to ``versions_report``, which appears in both ``salt
  --versions-report`` and ``salt '*' test.versions_report``. Also added is an
  alias ``test.versions`` to ``test.versions_report``. (:issue:`21906`)

JBoss 7 State
=============

- Remove unused argument ``timeout`` in jboss7.status
