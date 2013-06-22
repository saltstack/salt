'''
Installation of PHP pecl extensions.
==============================================

A state module to manage php pecl extensions.

.. code-block:: yaml

    mongo:
      pecl.installed
'''


def installed(
        name,
        version=None):
    '''
    Make sure that a pecl extension is installed.

    name
        The pecl extension name to install

    version
        The pecl extension version to install. This option may be
        ignored to install the latest stable version.
    '''
    # Check to see if we have a designated version
    if not isinstance(version, basestring) and version is not None:
        version = str(version)

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    installed_pecls = __salt__['pecl.list']()

    if name in installed_pecls:
        # The package is only installed if version is absent or matches
        if version is None or version in installed_pecls[name]:
            ret['result'] = True
            ret['comment'] = 'Pecl extension {0} is already installed.'.format(name)
            return ret

    if version is not None:
        # Modify the name to include the version and proceed.
        name = '{0}-{1}'.format(name, version)

    if __opts__['test']:
        ret['comment'] = 'Pecl extension {0} would have been installed'.format(name)
        return ret
    if __salt__['pecl.install'](name):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = 'Pecl extension {0} was successfully installed'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install pecl extension {0}.'.format(name)

    return ret


def removed(name):
    '''
    Make sure that a pecl extension is not installed.

    name
        The pecl extension name to uninstall
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    if name not in __salt__['pecl.list']():
        ret['result'] = True
        ret['comment'] = 'Pecl extension {0} is not installed.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Pecl extension {0} would have been removed'.format(name)
        return ret
    if __salt__['pecl.uninstall'](name):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Pecl extension {0} was successfully removed.'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove pecl extension {0}.'.format(name)
    return ret
