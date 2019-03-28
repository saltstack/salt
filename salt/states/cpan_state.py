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
from __future__ import absolute_import, print_function, unicode_literals
import logging
try:
    import pkg_resources
    HAS_PKG_RESOURCES = True
except ImportError:
    HAS_PKG_RESOURCES = False

# Import salt libs
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# Import 3rd-party libs
from salt.ext import six
# pylint: disable=import-error

# pylint: enable=import-error

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'cpan'


def __virtual__():
    '''
    Only load if the pip module is available in __salt__
    '''
    if HAS_PKG_RESOURCES is False:
        return False, 'The pkg_resources python library is not installed'
    if 'cpan.list' in __salt__:
        return __virtualname__
    return False

def installed(name,
              pkgs=None,
              cpan_bin=None,
              bin_env=None,
              force=None,
              mirror=None,
              notest=None,
              **kwargs):
    '''
    Make sure the package is installed

    name
        The name of the perl module to install.

    Example:

    .. code-block:: yaml

        cpanm:
          cpan.installed:
            - pkgs:
              - App::cpanminus
              - CPAN
            - require:
              - pkg: perl
    '''
    if cpan_bin and not bin_env:
        bin_env = cpan_bin

    # If pkgs is present, ignore name
    if pkgs:
        if not isinstance(pkgs, list):
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'pkgs argument must be formatted as a list'}
    else:
        pkgs = [name]

    ret = {'name': ';'.join(pkgs), 'result': None,
           'comment': '', 'changes': {}}

    try:
        cur_version = __salt__['cpan.version'](bin_env)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = None
        ret['comment'] = 'Error installing \'{0}\': {1}'.format(name, err)
        return ret

    # TODO verify that the cpan* binary supports all options that have been passed
    # If support is added for cpanminus and cpanplus, this will be very crucial

    ret['changes'] = dict()
    for pkg in pkgs:
        # Ignore modules that are already installed, don't force everything to update
        version = __salt__['cpan.show'](pkg).get("installed version", None)
        if version and ('not installed' not in version):
            log.debug("perl module '{}' is already installed")
            continue

        log.debug("Installing Perl module: {}".format(pkg))
        cpan_install_call = __salt__['cpan.install'](
            module=pkg,
            force=force,
            mirror=mirror,
            notest=notest,
            **kwargs
        )
        if cpan_install_call:
            ret['changes'][pkg] = cpan_install_call
    return ret


def removed(name,
            bin_env=None):
    raise NotImplemented("Unable to remove {}".format(name))


def uptodate(name,
             pkgs=None,
             cpan_bin=None,
             bin_env=None,
             force=None,
             mirror=None,
             notest=None,
             **kwargs):
    '''
    Verify that the given packages are completely up to date

    name
        The name of the perl module to install. You can also specify version

    Example:

    .. code-block:: yaml

        cpanm:
          cpan.uptodate:
            - pkgs:
              - App::cpanminus
              - CPAN
            - require:
              - pkg: perl
    '''
    if cpan_bin and not bin_env:
        bin_env = cpan_bin

    # If pkgs is present, ignore name
    if pkgs:
        if not isinstance(pkgs, list):
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'pkgs argument must be formatted as a list'}
    else:
        pkgs = [name]

    ret = {'name': ';'.join(pkgs), 'result': None,
           'comment': '', 'changes': {}}

    try:
        cur_version = __salt__['cpan.version'](bin_env)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = None
        ret['comment'] = 'Error installing \'{0}\': {1}'.format(name, err)
        return ret

    # TODO verify that the cpan* binary supports all options that have been passed
    # If support is added for cpanminus and cpanplus, this will be very crucial

    ret['changes'] = dict()
    for pkg in pkgs:
        log.debug("Installing Perl module: {}".format(pkg))
        cpan_install_call = __salt__['cpan.install'](
            module=pkg,
            force=force,
            mirror=mirror,
            notest=notest,
            **kwargs
        )
        if cpan_install_call:
            ret['changes'][pkg] = cpan_install_call
    return ret

