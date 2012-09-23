'''
Installation of PHP pecl extensions.
==============================================

A state module to manage php pecl extensions.

.. code-block:: yaml

    mongo:
      pecl.installed
'''


def installed(name):
    '''
    Make sure that a pecl extension is installed.

    name
        The pecl extension name to install
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    if name in __salt__['pecl.list']():
        ret['result'] = True
        ret['comment'] = 'Pecl is already installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The pecl {0} would have been installed'.format(name)
        return ret
    if __salt__['pecl.install'](name):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = 'Pecl was successfully installed'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install pecl.'

    return ret


def removed(name):
    '''
    Make sure that a pecl extension is not installed.

    name
        The pecl exntension name to uninstall
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    if name not in __salt__['pecl.list']():
        ret['result'] = True
        ret['comment'] = 'Pecl is not installed.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The pecl {0} would have been removed'.format(name)
        return ret
    if __salt__['pecl.uninstall'](name):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Pecl was successfully removed.'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove pecl.'
    return ret
