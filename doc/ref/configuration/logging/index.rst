.. _logging:

=======
Logging
=======

The Salt Project tries to get the logging to work for you and help us solve any
issues you might find along the way.

If you want to get some more information on the nitty-gritty of salt's logging
system, please head over to the :ref:`logging development
document <logging-internals>`, if all you're after is salt's logging
configurations, please continue reading.


.. conf_log:: log_levels

Log Levels
==========

The log levels are ordered numerically such that setting the log level to a
specific level will record all log statements at that level and higher.  For
example, setting ``log_level: error`` will log statements at ``error``,
``critical``, and ``quiet`` levels, although nothing *should* be logged at
``quiet`` level.

Most of the logging levels are defined by default in Python's logging library
and can be found in the official :ref:`Python documentation <python:levels>`.
Salt uses some more levels in addition to the standard levels.  All levels
available in salt are shown in the table below.

.. note::

    Python dependencies used by salt may define and use additional logging
    levels.  For example, the Python 2 version of the ``multiprocessing``
    standard Python library `uses the levels
    <https://docs.python.org/3/library/multiprocessing.html#logging>`_
    ``subwarning``, 25 and ``subdebug``, 5.

+----------+---------------+--------------------------------------------------------------------------+
| Level    | Numeric value | Description                                                              |
+==========+===============+==========================================================================+
| quiet    |          1000 | Nothing should be logged at this level                                   |
+----------+---------------+--------------------------------------------------------------------------+
| critical |            50 | Critical errors                                                          |
+----------+---------------+--------------------------------------------------------------------------+
| error    |            40 | Errors                                                                   |
+----------+---------------+--------------------------------------------------------------------------+
| warning  |            30 | Warnings                                                                 |
+----------+---------------+--------------------------------------------------------------------------+
| info     |            20 | Normal log information                                                   |
+----------+---------------+--------------------------------------------------------------------------+
| profile  |            15 | Profiling information on salt performance                                |
+----------+---------------+--------------------------------------------------------------------------+
| debug    |            10 | Information useful for debugging both salt implementations and salt code |
+----------+---------------+--------------------------------------------------------------------------+
| trace    |             5 | More detailed code debugging information                                 |
+----------+---------------+--------------------------------------------------------------------------+
| garbage  |             1 | Even more debugging information                                          |
+----------+---------------+--------------------------------------------------------------------------+
| all      |             0 | Everything                                                               |
+----------+---------------+--------------------------------------------------------------------------+

Available Configuration Settings
================================

.. conf_log:: log_file

``log_file``
------------

The log records can be sent to a regular file, local path name, or network
location.  Remote logging works best when configured to use rsyslogd(8) (e.g.:
``file:///dev/log``), with rsyslogd(8) configured for network logging.  The
format for remote addresses is:

.. code-block:: text

    <file|udp|tcp>://<host|socketpath>:<port-if-required>/<log-facility>

Where ``log-facility`` is the symbolic name of a syslog facility as defined in
the :py:meth:`SysLogHandler documentation
<logging.handlers.SysLogHandler.encodePriority>`. It defaults to ``LOG_USER``.

Default: Dependent of the binary being executed, for example, for
``salt-master``, ``/var/log/salt/master``.

Examples:

.. code-block:: yaml

    log_file: /var/log/salt/master

.. code-block:: yaml

    log_file: /var/log/salt/minion

.. code-block:: yaml

    log_file: file:///dev/log

.. code-block:: yaml

    log_file: file:///dev/log/LOG_DAEMON

.. code-block:: yaml

    log_file: udp://loghost:10514

.. conf_log:: log_level

``log_level``
-------------

Default: ``warning``

The level of log record messages to send to the console. One of ``all``,
``garbage``, ``trace``, ``debug``, ``profile``, ``info``, ``warning``,
``error``, ``critical``, ``quiet``.

.. code-block:: yaml

    log_level: warning

.. note::
    Add ``log_level: quiet`` in salt configuration file to completely disable
    logging. In case of running salt in command line use ``--log-level=quiet``
    instead.

.. conf_log:: log_level_logfile

``log_level_logfile``
---------------------

Default: ``info``

The level of messages to send to the log file. One of ``all``, ``garbage``,
``trace``, ``debug``, ``profile``, ``info``, ``warning``, ``error``,
``critical``, ``quiet``.

.. code-block:: yaml

    log_level_logfile: warning

.. conf_log:: log_datefmt

``log_datefmt``
---------------

Default: ``%H:%M:%S``

The date and time format used in console log messages. Allowed date/time
formatting matches those used in :py:func:`time.strftime`.

.. code-block:: yaml

    log_datefmt: '%H:%M:%S'

.. conf_log:: log_datefmt_logfile

``log_datefmt_logfile``
-----------------------

Default: ``%Y-%m-%d %H:%M:%S``

The date and time format used in log file messages. Allowed date/time
formatting matches those used in :py:func:`time.strftime`.

.. code-block:: yaml

    log_datefmt_logfile: '%Y-%m-%d %H:%M:%S'

.. conf_log:: log_fmt_console

``log_fmt_console``
-------------------

Default: ``[%(levelname)-8s] %(message)s``

The format of the console logging messages. All standard python logging
:py:class:`~logging.LogRecord` attributes can be used. Salt also provides these
custom LogRecord attributes to colorize console log output:

.. code-block:: python

    "%(colorlevel)s"  # log level name colorized by level
    "%(colorname)s"  # colorized module name
    "%(colorprocess)s"  # colorized process number
    "%(colormsg)s"  # log message colorized by level

.. note::
    The ``%(colorlevel)s``, ``%(colorname)s``, and ``%(colorprocess)``
    LogRecord attributes also include padding and enclosing brackets, ``[`` and
    ``]`` to match the default values of their collateral non-colorized
    LogRecord attributes.

.. code-block:: yaml

    log_fmt_console: '[%(levelname)-8s] %(message)s'

.. conf_log:: log_fmt_logfile

``log_fmt_logfile``
-------------------

Default: ``%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s``

The format of the log file logging messages. All standard python logging
:py:class:`~logging.LogRecord` attributes can be used.  Salt also provides
these custom LogRecord attributes that include padding and enclosing brackets
``[`` and ``]``:

.. code-block:: python

    "%(bracketlevel)s"  # equivalent to [%(levelname)-8s]
    "%(bracketname)s"  # equivalent to [%(name)-17s]
    "%(bracketprocess)s"  # equivalent to [%(process)5s]

.. code-block:: yaml

    log_fmt_logfile: '%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s'

.. conf_log:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

This can be used to control logging levels more specifically, based on log call name.  The example sets
the main salt library at the 'warning' level, sets ``salt.modules`` to log
at the ``debug`` level, and sets a custom module to the ``all`` level:

.. code-block:: yaml

  log_granular_levels:
    'salt': 'warning'
    'salt.modules': 'debug'
    'salt.loader.saltmaster.ext.module.custom_module': 'all'

.. conf_log:: log_fmt_jid

You can determine what log call name to use here by adding ``%(module)s`` to the
log format. Typically, it is the path of the file which generates the log
without the trailing ``.py`` and with path separators replaced with ``.``


``log_fmt_jid``
-------------------

Default: ``[JID: %(jid)s]``

The format of the JID when added to logging messages.

.. code-block:: yaml

    log_fmt_jid: '[JID: %(jid)s]'

External Logging Handlers
-------------------------

Besides the internal logging handlers used by salt, there are some external
which can be used, see the :ref:`external logging handlers<external-logging-handlers>`
document.
