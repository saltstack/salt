'''
Managing Ruby installations and gemsets with Ruby Version Manager (RVM).
========================================================================

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
      group:
        - present
      user.present:
        - gid: rvm
        - home: /home/rvm
        - require:
          - group: rvm

    rvm-deps:
      pkg.installed:
        - names:
          - bash
          - coreutils
          - gzip
          - bzip2
          - gawk
          - sed
          - curl
          - git-core
          - subversion
          - sudo

    mri-deps:
      pkg.installed:
        - names:
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
        - names:
          - curl
          - g++
          - openjdk-6-jre-headless

    ruby-1.9.2:
      rvm.installed:
        - default: True
        - runas: rvm
        - require:
          - pkg: rvm-deps
          - pkg: mri-deps
          - user: rvm

    jruby:
      rvm.installed:
        - runas: rvm
        - require:
          - pkg: rvm-deps
          - pkg: jruby-deps
          - user: rvm

    jgemset:
      rvm.gemset_present:
        - ruby: jruby
        - runas: rvm
        - require:
          - rvm: jruby

    mygemset:
      rvm.gemset_present:
        - ruby: ruby-1.9.2
        - runas: rvm
        - require:
          - rvm: ruby-1.9.2
'''
# Import Python libs
import re


def _check_rvm(ret):
    '''
    Check to see if rmv is installed and install it
    '''
    if not __salt__['rvm.is_installed']():
        if __salt__['rvm.install']():
            ret['changes']['rvm'] = 'Installed'
        else:
            ret['result'] = False
            ret['comment'] = 'Could not install RVM.'
    return ret


def _check_and_install_ruby(ret, ruby, default=False, runas=None):
    '''
    Verify that ruby is installed, install if unavailable
    '''
    ret = _check_ruby(ret, ruby, runas=runas)
    if not ret['result']:
        if __salt__['rvm.install_ruby'](ruby, runas=runas):
            ret['result'] = True
            ret['changes'][ruby] = 'Installed'
            ret['comment'] = 'Successfully installed ruby.'
            ret['default'] = False
        else:
            ret['result'] = False
            ret['comment'] = 'Could not install ruby.'
            return ret

    if not ret['default'] and default:
        __salt__['rvm.set_default'](ruby, runas=runas)

    return ret


def _check_ruby(ret, ruby, runas=None):
    '''
    Check that ruby is installed
    '''
    match_version = True
    match_micro_version = False
    micro_version_regex = re.compile('-([0-9]{4}\.[0-9]{2}|p[0-9]+)$')
    if micro_version_regex.search(ruby):
        match_micro_version = True
    if re.search('^[a-z]+$', ruby):
        match_version = False
    ruby = re.sub('^ruby-', '', ruby)

    for impl, version, default in __salt__['rvm.list'](runas=runas):
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


def installed(name, default=False, runas=None):
    '''
    Verify that the specified ruby is installed with RVM. RVM is
    installed when necessary.

    name
        The version of ruby to install
    default : False
        Whether to make this ruby the default.
    runas : None
        The user to run rvm as.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    ret = _check_rvm(ret)
    if ret['result'] == False:
        return ret

    if __opts__['test']:
        ret['comment'] = 'Ruby {0} is set to be installed'.format(name)
        return ret

    return _check_and_install_ruby(ret, name, default, runas=runas)


def gemset_present(name, ruby='default', runas=None):
    '''
    Verify that the gemset is present.

    name
        The name of the gemset.
    ruby : default
        The ruby version this gemset belongs to.
    runas : None
        The use user to run rvm as.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    ret = _check_rvm(ret)
    if ret['result'] is False:
        return ret

    if '@' in name:
        ruby, name = name.split('@')
        ret = _check_ruby(ret, ruby)
        if not ret['result']:
            ret['result'] = False
            ret['comment'] = 'Requested ruby implementation was not found.'
            return ret

    if name in __salt__['rvm.gemset_list'](ruby, runas=runas):
        ret['result'] = True
        ret['comment'] = 'Gemset already exists.'
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Set to install gemset {0}'.format(name)
            return ret
        if __salt__['rvm.gemset_create'](ruby, name, runas=runas):
            ret['result'] = True
            ret['comment'] = 'Gemset successfully created.'
            ret['changes'][name] = 'created'
        else:
            ret['result'] = False
            ret['comment'] = 'Gemset could not be created.'

    return ret
