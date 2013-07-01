'''
Managing Ruby installations with rbenv.
========================================

This module is used to install and manage ruby installations with rbenv.
Different versions of ruby can be installed, and uninstalled. Rbenv will
be installed automatically the first time it is needed and can be updated
later. This module will *not* automatically install packages which rbenv
will need to compile the versions of ruby.

If rbenv is run as the root user then it will be installed to /usr/local/rbenv,
otherwise it will be installed to the users ~/.rbenv directory. To make
rbenv available in the shell you may need to add the rbenv/shims and rbenv/bin
directories to the users PATH. If you are installing as root and want other
users to be able to access rbenv then you will need to add RBENV_ROOT to
their environment.

This is how a state configuration could look like:

.. code-block:: yaml

    rbenv-deps:
      pkg.installed:
        - pkgs:
          - bash
          - git
          - openssl
          - gmake
          - curl

    ruby-1.9.3-p392:
      rbenv.absent:
        - require:
          - pkg: rbenv-deps

    ruby-1.9.3-p429:
      rbenv.installed:
        - default: True
        - require:
          - pkg: rbenv-deps

    .. versionadded:: 0.16.0
'''

# Import python libs
import re

def _check_rbenv(ret, runas=None):
    '''
    Check to see if rbenv is installed.
    '''
    if not __salt__['rbenv.is_installed'](runas):
        ret['result'] = False
        ret['comment'] = 'Rbenv is not installed.'
    return ret

def _ruby_installed(ret, ruby, runas=None):
    '''
    Check to see if given ruby is installed.
    '''
    default = __salt__['rbenv.default'](runas=runas)
    for version in __salt__['rbenv.versions'](runas):
        if version == ruby:
            ret['result'] = True
            ret['comment'] = 'Requested ruby exists.'
            ret['default'] = default == ruby
            break

    return ret

def _check_and_install_ruby(ret, ruby, default=False, runas=None):
    '''
    Verify that ruby is installed, install if unavailable
    '''
    ret = _ruby_installed(ret, ruby, runas=runas)
    if not ret['result']:
        if __salt__['rbenv.install_ruby'](ruby, runas=runas):
            ret['result'] = True
            ret['changes'][ruby] = 'Installed'
            ret['comment'] = 'Successfully installed ruby'
            ret['default'] = default
        else:
            ret['result'] = False
            ret['comment'] = 'Could not install ruby.'
            return ret

    if default:
        __salt__['rbenv.default'](ruby, runas=runas)

    return ret

def installed(name, default=False, runas=None):
    '''
    Verify that the specified ruby is installed with rbenv. Rbenv is
    installed if necessary.

    name
        The version of ruby to install
    default : False
        Whether to make this ruby the default.
    runas : None
        The user to run rbenv as.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if name.startswith('ruby-'):
        name = re.sub(r'^ruby-', '', name)

    if __opts__['test']:
        ret['comment'] = 'Ruby {0} is set to be installed'.format(name)
        return ret

    ret = _check_rbenv(ret, runas)
    if ret['result'] == False:
        if not __salt__['rbenv.install'](runas):
            ret['comment'] = 'Rbenv failed to install'
            return ret
        else:
            return _check_and_install_ruby(ret, name, default, runas=runas)
    else:
        return _check_and_install_ruby(ret, name, default, runas=runas)

def _check_and_uninstall_ruby(ret, ruby, runas=None):
    '''
    Verify that ruby is uninstalled
    '''
    ret = _ruby_installed(ret, ruby, runas=runas)
    if ret['result']:
        if ret['default']:
            __salt__['rbenv.default']('system', runas=runas)

        if __salt__['rbenv.uninstall_ruby'](ruby, runas=runas):
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

def absent(name, runas=None):
    '''
    Verify that the specified ruby is not installed with rbenv. Rbenv
    is installed if necessary.

    name
        The version of ruby to uninstall
    runas : None
        The user to run rbenv as.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if name.startswith('ruby-'):
        name = re.sub(r'^ruby-', '', name)

    if __opts__['test']:
        ret['comment'] = 'Ruby {0} is set to be uninstalled'.format(name)
        return ret

    ret = _check_rbenv(ret, runas)
    if ret['result'] == False:
        ret['result'] = True
        ret['comment'] = 'Rbenv not installed, {0} not either'.format(name)
        return ret
    else:
        return _check_and_uninstall_ruby(ret, name, runas=runas)
