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
    # If modules is present, ignore name
    if modules:
        if not isinstance(modules, list):
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'modules argument must be formatted as a list'}
    else:
        modules = [name]

    ret = {'name': ';'.join(modules), 'result': None,
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
    for mod in modules:
        # Ignore modules that are already installed, don't force everything to update
        version = __salt__['cpan.show'](mod).get("installed version", None)
        if version and ('not installed' not in version):
            log.debug("perl module '{}' is already installed")
            continue

        log.debug("Installing Perl module: {}".format(mod))
        cpan_install_call = __salt__['cpan.install'](
            module=mod,
            force=force,
            mirror=mirror,
            notest=notest,
            **kwargs
        )
        if cpan_install_call:
            ret['changes'][mod] = cpan_install_call
    return ret


def removed(name,
            bin_env=None):
    raise NotImplemented("Unable to remove {}".format(name))


def uptodate(name,
             modules=None,
             cpan_bin=None,
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
    if cpan_bin and not bin_env:
        bin_env = cpan_bin

    # If modules is present, ignore name
    if modules:
        if not isinstance(modules, list):
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'modules argument must be formatted as a list'}
    else:
        modules = [name]

    ret = {'name': ';'.join(modules), 'result': None,
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
    for pkg in modules:
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

