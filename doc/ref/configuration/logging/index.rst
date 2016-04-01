=======
Logging
=======

The salt project tries to get the logging to work for you and help us solve any
issues you might find along the way.

If you want to get some more information on the nitty-gritty of salt's logging
system, please head over to the :doc:`logging development
document</topics/development/logging>`, if all you're after is salt's logging
configurations, please continue reading.


Available Configuration Settings
================================

.. conf_log:: log_file

``log_file``
------------

The log records can be sent to a regular file, local path name, or network location.
Remote logging works best when configured to use rsyslogd(8) (e.g.: ``file:///dev/log``),
with rsyslogd(8) configured for network logging.  The format for remote addresses is:
``<file|udp|tcp>://<host|socketpath>:<port-if-required>/<log-facility>``.

Default: Dependent of the binary being executed, for example, for ``salt-master``,
``/var/log/salt/master``.


Examples:


.. code-block:: yaml

    log_file: /var/log/salt/master


.. code-block:: yaml

    log_file: /var/log/salt/minion


.. code-block:: yaml

    log_file: file:///dev/log

.. code-block:: yaml

    log_file: udp://loghost:10514



.. conf_log:: log_level

``log_level``
-------------

Default: ``warning``

The level of log record messages to send to the console.
One of ``all``, ``garbage``, ``trace``, ``debug``, ``info``, ``warning``,
``error``, ``critical``, ``quiet``.

.. code-block:: yaml

    log_level: warning



.. conf_log:: log_level_logfile

``log_level_logfile``
---------------------

Default: ``warning``

The level of messages to send to the log file.
One of ``all``, ``garbage``, ``trace``, ``debug``, ``info``, ``warning``,
``error``, ``critical``, ``quiet``.

.. code-block:: yaml

    log_level_logfile: warning



.. conf_log:: log_datefmt

``log_datefmt``
---------------

Default: ``%H:%M:%S``

The date and time format used in console log messages. Allowed date/time
formatting can be seen on :func:`time.strftime <python2:time.strftime>`.

.. code-block:: yaml

    log_datefmt: '%H:%M:%S'



.. conf_log:: log_datefmt_logfile

``log_datefmt_logfile``
-----------------------

Default: ``%Y-%m-%d %H:%M:%S``

The date and time format used in log file messages. Allowed date/time
formatting can be seen on :func:`time.strftime <python2:time.strftime>`.

.. code-block:: yaml

    log_datefmt_logfile: '%Y-%m-%d %H:%M:%S'



.. conf_log:: log_fmt_console

``log_fmt_console``
-------------------

Default: ``[%(levelname)-8s] %(message)s``

The format of the console logging messages. All standard python logging
:ref:`LogRecord attributes <python2:logrecord-attributes>` can be used.  Salt
also provides these custom LogRecord attributes to colorize console log output:

.. code-block:: python

    '%(colorlevel)s'   # log level name colorized by level
    '%(colorname)s'    # colorized module name
    '%(colorprocess)s' # colorized process number
    '%(colormsg)s'     # log message colorized by level

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

Default: ``%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s``

The format of the log file logging messages. All standard python logging
:ref:`LogRecord attributes <python2:logrecord-attributes>` can be used.  Salt
also provides these custom LogRecord attributes that include padding and
enclosing brackets ``[`` and ``]``:

.. code-block:: python

    '%(bracketlevel)s'   # equivalent to [%(levelname)-8s]
    '%(bracketname)s'    # equivalent to [%(name)-17s]
    '%(bracketprocess)s' # equivalent to [%(process)5s]

.. code-block:: yaml

    log_fmt_logfile: '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s'



.. conf_log:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

This can be used to control logging levels more specifically.  The example sets
the main salt library at the 'warning' level, but sets ``salt.modules`` to log
at the ``debug`` level:

.. code-block:: yaml

  log_granular_levels:
    'salt': 'warning'
    'salt.modules': 'debug'


External Logging Handlers
-------------------------

Besides the internal logging handlers used by salt, there are some external
which can be used, see the :doc:`external logging handlers<handlers/index>`
document.
