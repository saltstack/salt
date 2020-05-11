# -*- coding: utf-8 -*-
'''
Managing Ruby installations with rbenv
======================================

This module is used to install and manage ruby installations with rbenv and the
ruby-build plugin. Different versions of ruby can be installed, and uninstalled.
Rbenv will be installed automatically the first time it is needed and can be
updated later. This module will *not* automatically install packages which rbenv
will need to compile the versions of ruby. If your version of ruby fails to
install, refer to the ruby-build documentation to verify you are not missing any
dependencies: https://github.com/rbenv/ruby-build/wiki

If rbenv is run as the root user then it will be installed to /usr/local/rbenv,
otherwise it will be installed to the users ~/.rbenv directory. To make
rbenv available in the shell you may need to add the rbenv/shims and rbenv/bin
directories to the users PATH. If you are installing as root and want other
users to be able to access rbenv then you will need to add RBENV_ROOT to
their environment.

The following state configuration demonstrates how to install Ruby 1.9.x
and 2.x using rbenv on Ubuntu/Debian:

.. code-block:: yaml

    rbenv-deps:
      pkg.installed:
        - names:
          - bash
          - git
          - openssl
          - libssl-dev
          - make
          - curl
          - autoconf
          - bison
          - build-essential
          - libffi-dev
          - libyaml-dev
          - libreadline6-dev
          - zlib1g-dev
          - libncurses5-dev

    ruby-1.9.3-p429:
      rbenv.absent:
        - require:
          - pkg: rbenv-deps

    ruby-2.0.0-p598:
      rbenv.installed:
        - default: True
        - require:
          - pkg: rbenv-deps
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import re
import copy


def _check_rbenv(ret, user=None):
    '''
    Check to see if rbenv is installed.
    '''
    if not __salt__['rbenv.is_installed'](user):
        ret['result'] = False
        ret['comment'] = 'Rbenv is not installed.'
    return ret


def _ruby_installed(ret, ruby, user=None):
    '''
    Check to see if given ruby is installed.
    '''
    default = __salt__['rbenv.default'](runas=user)
    for version in __salt__['rbenv.versions'](user):
        if version == ruby:
            ret['result'] = True
            ret['comment'] = 'Requested ruby exists'
            ret['default'] = default == ruby
            break

    return ret


def _check_and_install_ruby(ret, ruby, default=False, user=None):
    '''
    Verify that ruby is installed, install if unavailable
    '''
    ret = _ruby_installed(ret, ruby, user=user)
    if not ret['result']:
        if __salt__['rbenv.install_ruby'](ruby, runas=user):
            ret['result'] = True
            ret['changes'][ruby] = 'Installed'
            ret['comment'] = 'Successfully installed ruby'
            ret['default'] = default
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to install ruby'
            return ret

    if default:
        __salt__['rbenv.default'](ruby, runas=user)

    return ret


def installed(name, default=False, user=None):
    '''
    Verify that the specified ruby is installed with rbenv. Rbenv is
    installed if necessary.

    name
        The version of ruby to install

    default : False
        Whether to make this ruby the default.

    user: None
        The user to run rbenv as.

        .. versionadded:: 0.17.0

    .. versionadded:: 0.16.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    rbenv_installed_ret = copy.deepcopy(ret)

    if name.startswith('ruby-'):
        name = re.sub(r'^ruby-', '', name)

    if __opts__['test']:
        ret = _ruby_installed(ret, name, user=user)
        if not ret['result']:
            ret['comment'] = 'Ruby {0} is set to be installed'.format(name)
        else:
            ret['comment'] = 'Ruby {0} is already installed'.format(name)
        return ret

    rbenv_installed_ret = _check_and_install_rbenv(rbenv_installed_ret, user)
    if rbenv_installed_ret['result'] is False:
        ret['result'] = False
        ret['comment'] = 'Rbenv failed to install'
        return ret
    else:
        return _check_and_install_ruby(ret, name, default, user=user)


def _check_and_uninstall_ruby(ret, ruby, user=None):
    '''
    Verify that ruby is uninstalled
    '''
    ret = _ruby_installed(ret, ruby, user=user)
    if ret['result']:
        if ret['default']:
            __salt__['rbenv.default']('system', runas=user)

        if __salt__['rbenv.uninstall_ruby'](ruby, runas=user):
            ret['result'] = True
            ret['changes'][ruby] = 'Uninstalled'
            ret['comment'] = 'Successfully removed ruby'
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to uninstall ruby'
            return ret
    else:
        ret['result'] = True
        ret['comment'] = 'Ruby {0} is already absent'.format(ruby)

    return ret


def absent(name, user=None):
    '''
    Verify that the specified ruby is not installed with rbenv. Rbenv
    is installed if necessary.

    name
        The version of ruby to uninstall

    user: None
        The user to run rbenv as.

        .. versionadded:: 0.17.0

    .. versionadded:: 0.16.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if name.startswith('ruby-'):
        name = re.sub(r'^ruby-', '', name)

    ret = _check_rbenv(ret, user)
    if ret['result'] is False:
        ret['result'] = True
        ret['comment'] = 'Rbenv not installed, {0} not either'.format(name)
        return ret
    else:
        if __opts__['test']:
            ret = _ruby_installed(ret, name, user=user)
            if ret['result']:
                ret['result'] = None
                ret['comment'] = 'Ruby {0} is set to be uninstalled'.format(name)
            else:
                ret['result'] = True
                ret['comment'] = 'Ruby {0} is already uninstalled'.format(name)
            return ret

        return _check_and_uninstall_ruby(ret, name, user=user)


def _check_and_install_rbenv(ret, user=None):
    '''
    Verify that rbenv is installed, install if unavailable
    '''
    ret = _check_rbenv(ret, user)
    if ret['result'] is False:
        if __salt__['rbenv.install'](user):
            ret['result'] = True
            ret['comment'] = 'Rbenv installed'
        else:
            ret['result'] = False
            ret['comment'] = 'Rbenv failed to install'
    else:
        ret['result'] = True
        ret['comment'] = 'Rbenv is already installed'

    return ret


def install_rbenv(name, user=None):
    '''
    Install rbenv if not installed. Allows you to require rbenv be installed
    prior to installing the plugins. Useful if you want to install rbenv
    plugins via the git or file modules and need them installed before
    installing any rubies.

    Use the rbenv.root configuration option to set the path for rbenv if you
    want a system wide install that is not in a user home dir.

    user: None
        The user to run rbenv as.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if __opts__['test']:
        ret = _check_rbenv(ret, user=user)
        if ret['result'] is False:
            ret['result'] = None
            ret['comment'] = 'Rbenv is set to be installed'
        else:
            ret['result'] = True
            ret['comment'] = 'Rbenv is already installed'
        return ret

    return _check_and_install_rbenv(ret, user)
