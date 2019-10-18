# -*- coding: utf-8 -*-
'''
Installation of Perl Modules Using cpan
=========================================

These states manage system installed perl modules. Note that perl must be
installed for these states to be available, so cpan states should include a
requisite to a pkg.installed state for the package which provides perl.
Example:

.. code-block:: yaml

    perl:
      pkg.installed
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'cpan'


def __virtual__():
    '''
    Only load if the cpan module is available in __salt__
    '''
    if 'cpan.list' in __salt__:
        return __virtualname__
    return False


def __install(name,
              modules=None,
              bin_env=None,
              force=None,
              mirror=None,
              notest=None,
              upgrade=None,
              **kwargs):
    # If modules is present, ignore name; otherwise use name for modules
    if not modules:
        modules = [name]

    ret = dict(
        name=';'.join(modules),
        result=None,
        comment='',
        changes=dict())

    # TODO verify that the cpan* binary supports all options that have been passed
    # If support is added for cpanminus and cpanplus, this will be very crucial

    ret['result'] = True
    for mod in modules:
        # Ignore modules that are already installed, don't force everything to update
        version = __salt__['cpan.show'](mod, bin_env=bin_env).get("installed version", None)
        if version and 'not installed' not in version:
            if upgrade:
                log.debug("Attempting to upgrade '{}'")
            else:
                log.debug("perl module '{}' is already installed")
                continue

        log.debug("Installing Perl module: {}".format(mod))
        cpan_install_call = __salt__['cpan.install'](
            bin_env=bin_env,
            module=mod,
            force=force,
            mirror=mirror,
            notest=notest,
            **kwargs
        )
        if cpan_install_call.get('error', None):
            ret['comment'] = cpan_install_call.pop('error')
            ret['result'] = False
        if cpan_install_call:
            ret['changes'][mod] = cpan_install_call
        # Quit on the first error
        if ret['comment']:
            break
    return ret


def installed(name,
              modules=None,
              bin_env=None,
              force=None,
              mirror=None,
              notest=None,
              **kwargs):
    '''
    Make sure the package is installed

    bin_env :
        Absolute path to a virtual environment directory or absolute path to
        a cpan executable.

    name
        The name of the perl module to install.

    modules
        Install the specified modules.

    force
        Force the specified action, when it normally would have failed. Use this to install a module even if its tests fail.

    mirror
        A list of mirrors to use for just this run.

        .. code-block:: yaml

            cpanm:
              cpan.installed:
                - name: App::cpanminus
                - mirror:
                  - http://cpan.metacpan.org/
                  - ftp://mirror.xmission.com/CPAN/

    notest
        Do not test modules.  Simply install them.

    Example:

    .. code-block:: yaml

        cpanm:
          cpan.installed:
            - modules:
              - App::cpanminus
              - CPAN
            - mirror:
              - http://cpan.metacpan.org/
              - ftp://mirror.xmission.com/CPAN/
            - require:
              - pkg: perl
    '''
    return __install(name=name, modules=modules, bin_env=bin_env, force=force,
                     mirror=mirror, notest=notest, upgrade=False, **kwargs)


def removed(module,
            details=None,
            bin_env=None):
    raise NotImplementedError("Unable to remove {}".format(module))


def uptodate(name,
             modules=None,
             bin_env=None,
             force=None,
             mirror=None,
             notest=None,
             **kwargs):
    '''
    Verify that the given packages are completely up to date

    bin_env :
        Absolute path to a virtual environment directory or absolute path to
        a cpan executable.

    name
        The name of the perl module to install.

    modules
        Install the specified modules.

    force
        Force the specified action, when it normally would have failed. Use this to install a module even if its tests fail.

    mirror
        A comma-separated list of mirrors to use for just this run.

        .. code-block:: yaml

            cpanm:
              cpan.uptodate:
                - name: App::cpanminus
                - mirror:
                  - http://cpan.metacpan.org/
                  - ftp://mirror.xmission.com/CPAN/
                - require:
                  - pkg: perl

    notest
        Do not test modules.  Simply install them.


    Example:

    .. code-block:: yaml

        cpanm:
          cpan.uptodate:
            - modules:
              - App::cpanminus
              - CPAN
            - require:
              - pkg: perl
    '''
    return __install(name=name, modules=modules, bin_env=bin_env, force=force,
                     mirror=mirror, notest=notest, upgrade=True, **kwargs)
