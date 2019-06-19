# -*- coding: utf-8 -*-
'''
Managing Ruby installations and gemsets with Ruby Version Manager (RVM)
=======================================================================

This module is used to install and manage ruby installations and
gemsets with RVM, the Ruby Version Manager. Different versions of ruby
can be installed and gemsets created. RVM itself will be installed
automatically if it's not present. This module will not automatically
install packages that RVM depends on or ones that are needed to build
ruby. If you want to run RVM as an unprivileged user (recommended) you
will have to create this user yourself. This is how a state
configuration could look like:

.. code-block:: yaml

    rvm:
      group.present: []
      user.present:
        - gid: rvm
        - home: /home/rvm
        - require:
          - group: rvm

    rvm-deps:
      pkg.installed:
        - pkgs:
          - bash
          - coreutils
          - gzip
          - bzip2
          - gawk
          - sed
          - curl
          - git-core
          - subversion

    mri-deps:
      pkg.installed:
        - pkgs:
          - build-essential
          - openssl
          - libreadline6
          - libreadline6-dev
          - curl
          - git-core
          - zlib1g
          - zlib1g-dev
          - libssl-dev
          - libyaml-dev
          - libsqlite3-0
          - libsqlite3-dev
          - sqlite3
          - libxml2-dev
          - libxslt1-dev
          - autoconf
          - libc6-dev
          - libncurses5-dev
          - automake
          - libtool
          - bison
          - subversion
          - ruby

    jruby-deps:
      pkg.installed:
        - pkgs:
          - curl
          - g++
          - openjdk-6-jre-headless

    ruby-1.9.2:
      rvm.installed:
        - default: True
        - user: rvm
        - require:
          - pkg: rvm-deps
          - pkg: mri-deps
          - user: rvm

    jruby:
      rvm.installed:
        - user: rvm
        - require:
          - pkg: rvm-deps
          - pkg: jruby-deps
          - user: rvm

    jgemset:
      rvm.gemset_present:
        - ruby: jruby
        - user: rvm
        - require:
          - rvm: jruby

    mygemset:
      rvm.gemset_present:
        - ruby: ruby-1.9.2
        - user: rvm
        - require:
          - rvm: ruby-1.9.2
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import re


def _check_rvm(ret, user=None):
    '''
    Check to see if rvm is installed.
    '''
    if not __salt__['rvm.is_installed'](user):
        ret['result'] = False
        ret['comment'] = 'RVM is not installed.'
    return ret


def _check_and_install_ruby(ret, ruby, default=False, user=None, opts=None, env=None):
    '''
    Verify that ruby is installed, install if unavailable
    '''
    ret = _check_ruby(ret, ruby, user=user)
    if not ret['result']:
        if __salt__['rvm.install_ruby'](ruby, runas=user, opts=opts, env=env):
            ret['result'] = True
            ret['changes'][ruby] = 'Installed'
            ret['comment'] = 'Successfully installed ruby.'
            ret['default'] = False
        else:
            ret['result'] = False
            ret['comment'] = 'Could not install ruby.'
            return ret

    if default:
        __salt__['rvm.set_default'](ruby, runas=user)

    return ret


def _check_ruby(ret, ruby, user=None):
    '''
    Check that ruby is installed
    '''
    match_version = True
    match_micro_version = False
    micro_version_regex = re.compile(r'-([0-9]{4}\.[0-9]{2}|p[0-9]+)$')
    if micro_version_regex.search(ruby):
        match_micro_version = True
    if re.search('^[a-z]+$', ruby):
        match_version = False
    ruby = re.sub('^ruby-', '', ruby)

    for impl, version, default in __salt__['rvm.list'](runas=user):
        if impl != 'ruby':
            version = '{impl}-{version}'.format(impl=impl, version=version)
        if not match_micro_version:
            version = micro_version_regex.sub('', version)
        if not match_version:
            version = re.sub('-.*', '', version)
        if version == ruby:
            ret['result'] = True
            ret['comment'] = 'Requested ruby exists.'
            ret['default'] = default
            break
    return ret


def installed(name, default=False, user=None, opts=None, env=None):
    '''
    Verify that the specified ruby is installed with RVM. RVM is
    installed when necessary.

    name
        The version of ruby to install

    default : False
        Whether to make this ruby the default.

    user: None
        The user to run rvm as.

    env: None
        A list of environment variables to set (ie, RUBY_CONFIGURE_OPTS)

    opts: None
        A list of option flags to pass to RVM (ie -C, --patch)

        .. versionadded:: 0.17.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if __opts__['test']:
        ret['comment'] = 'Ruby {0} is set to be installed'.format(name)
        return ret

    ret = _check_rvm(ret, user)
    if ret['result'] is False:
        if not __salt__['rvm.install'](runas=user):
            ret['comment'] = 'RVM failed to install.'
            return ret
        else:
            return _check_and_install_ruby(ret, name, default, user=user, opts=opts, env=env)
    else:
        return _check_and_install_ruby(ret, name, default, user=user, opts=opts, env=env)


def gemset_present(name, ruby='default', user=None):
    '''
    Verify that the gemset is present.

    name
        The name of the gemset.

    ruby: default
        The ruby version this gemset belongs to.

    user: None
        The user to run rvm as.

        .. versionadded:: 0.17.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    ret = _check_rvm(ret, user)
    if ret['result'] is False:
        return ret

    if '@' in name:
        ruby, name = name.split('@')
        ret = _check_ruby(ret, ruby)
        if not ret['result']:
            ret['result'] = False
            ret['comment'] = 'Requested ruby implementation was not found.'
            return ret

    if name in __salt__['rvm.gemset_list'](ruby, runas=user):
        ret['result'] = True
        ret['comment'] = 'Gemset already exists.'
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Set to install gemset {0}'.format(name)
            return ret
        if __salt__['rvm.gemset_create'](ruby, name, runas=user):
            ret['result'] = True
            ret['comment'] = 'Gemset successfully created.'
            ret['changes'][name] = 'created'
        else:
            ret['result'] = False
            ret['comment'] = 'Gemset could not be created.'

    return ret
