"""
State module for syslog_ng
==========================

:maintainer:    Tibor Benke <btibi@sch.bme.hu>
:maturity:      new
:depends:       cmd, ps, syslog_ng
:platform:      all

Users can generate syslog-ng configuration files from YAML format or use
 plain ones and reload, start, or stop their syslog-ng by using this module.

Details
-------

The service module is not available on all system, so this module includes
:mod:`syslog_ng.reloaded <salt.states.syslog_ng.reloaded>`,
:mod:`syslog_ng.stopped <salt.states.syslog_ng.stopped>`,
and :mod:`syslog_ng.started <salt.states.syslog_ng.started>` functions.
If the service module is available on the computers, users should use that.

Users can generate syslog-ng configuration with
:mod:`syslog_ng.config <salt.states.syslog_ng.config>` function.
For more information see :ref:`syslog-ng state usage <syslog-ng-sate-usage>`.

Syslog-ng configuration file format
-----------------------------------

The syntax of a configuration snippet in syslog-ng.conf:

    ..

        object_type object_id {<options>};


These constructions are also called statements. There are options inside of them:

    ..

        option(parameter1, parameter2); option2(parameter1, parameter2);

You can find more information about syslog-ng's configuration syntax in the
Syslog-ng Admin guide:
http://www.balabit.com/sites/default/files/documents/syslog-ng-ose-3.5-guides/en/syslog-ng-ose-v3.5-guide-admin/html-single/index.html#syslog-ng.conf.5
"""

import logging

log = logging.getLogger(__name__)


def config(name, config, write=True):
    """
    Builds syslog-ng configuration.

    name : the id of the Salt document
    config : the parsed YAML code
    write : if True, it writes  the config into the configuration file,
    otherwise just returns it
    """
    return __salt__["syslog_ng.config"](name, config, write)


def stopped(name=None):
    """
    Kills syslog-ng.
    """
    return __salt__["syslog_ng.stop"](name)


def started(
    name=None,
    user=None,
    group=None,
    chroot=None,
    caps=None,
    no_caps=False,
    pidfile=None,
    enable_core=False,
    fd_limit=None,
    verbose=False,
    debug=False,
    trace=False,
    yydebug=False,
    persist_file=None,
    control=None,
    worker_threads=None,
    *args,
    **kwargs
):
    """
    Ensures, that syslog-ng is started via the given parameters.

    Users shouldn't use this function, if the service module is available on
    their system.
    """
    return __salt__["syslog_ng.start"](
        name=name,
        user=user,
        group=group,
        chroot=chroot,
        caps=caps,
        no_caps=no_caps,
        pidfile=pidfile,
        enable_core=enable_core,
        fd_limit=fd_limit,
        verbose=verbose,
        debug=debug,
        trace=trace,
        yydebug=yydebug,
        persist_file=persist_file,
        control=control,
        worker_threads=worker_threads,
    )


def reloaded(name):
    """
    Reloads syslog-ng.
    """
    return __salt__["syslog_ng.reload"](name)
