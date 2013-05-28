import re

def _check_rbenv(ret,runas=None):
    if not __salt__['rbenv.is_installed'](runas):
        ret['result'] = False
        ret['comment'] = 'Rbenv is not installed.'
    return ret

def _ruby_installed(ret, ruby, runas=None):
    default = __salt__['rbenv.default'](runas=runas)
    for version in __salt__['rbenv.versions'](runas):
        if version == ruby:
            ret['result'] = True
            ret['comment'] = 'Requested ruby exists.'
            ret['default'] = default == ruby
            break

    return ret

def _check_and_install_ruby(ret, ruby, default=False, runas=None):
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
        __salt__['rbenv.default'](ruby,runas=runas)

    return ret

def installed(name,default=False,runas=None):
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if name.startswith('ruby-'):
        name = re.sub(r'^ruby-','',name)

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

def absent(name,runas=None):
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if name.startswith('ruby-'):
        name = re.sub(r'^ruby-','',name)

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
