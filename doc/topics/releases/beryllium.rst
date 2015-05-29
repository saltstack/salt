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

Remove unused argument ``timeout`` in jboss7.status.

Pkgrepo State
=============

Deprecate ``enabled`` argument in ``pkgrepo.managed`` in favor of ``disabled``.

Archive Module
==============

In the ``archive.tar`` and ``archive.cmd_unzip`` module functions, remove the
arbitrary prefixing of the options string with ``-``.  An options string
beginning with a ``--long-option``, would have uncharacteristically needed its
first ``-`` removed under the former scheme.

Also, tar will parse its options differently if short options are used with or
without a preceding ``-``, so it is better to not confuse the user into
thinking they're using the non- ``-`` format, when really they are using the
with- ``-`` format.

Deprecations
============

The ``digital_ocean.py`` Salt Cloud driver was removed in favor of the
``digital_ocean_v2.py`` driver as DigitalOcean has removed support for APIv1.
The ``digital_ocean_v2.py`` was renamed to ``digital_ocean.py`` and supports
DigitalOcean's APIv2.
