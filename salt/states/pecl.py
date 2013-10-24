# -*- coding: utf-8 -*-
'''
Installation of PHP Extensions Using pecl
=========================================

These states manage the installed pecl extensions. Note that php-pear must be
installed for these states to be available, so pecl states should include a
requisite to a pkg.installed state for the package which provides pecl
(``php-pear`` in most cases). Example:

.. code-block:: yaml

    php-pear:
      pkg.installed

    mongo:
      pecl.installed:
        - require:
          - pkg: php-pear
'''


def __virtual__():
    '''
    Only load if the pecl module is available in __salt__
    '''
    return 'pecl' if 'pecl.list' in __salt__ else False


def installed(name,
              version=None,
              defaults=False,
              force=False,
              preferred_state='stable'):
    '''
    Make sure that a pecl extension is installed.

    name
        The pecl extension name to install

    version
        The pecl extension version to install. This option may be
        ignored to install the latest stable version.

    defaults
        Use default answers for extensions such as pecl_http which ask
        questions before installation. Without this option, the pecl.installed
        state will hang indefinitely when trying to install these extensions.

    force
        Whether to force the installed version or not

    preferred_state
        The pecl extension state to install

    .. note::
        The ``defaults`` option will be available in version 0.17.0.
    '''
    # Check to see if we have a designated version
    if not isinstance(version, basestring) and version is not None:
        version = str(version)

    ret = {'name': name,
           'result': None,
           'comment': '',
           'changes': {}}

    installed_pecls = __salt__['pecl.list']()

    if name in installed_pecls:
        # The package is only installed if version is absent or matches
        if (version is None or version in installed_pecls[name]) \
                and preferred_state in installed_pecls[name]:
            ret['result'] = True
            ret['comment'] = ('Pecl extension {0} is already installed.'
                              .format(name))
            return ret

    if version is not None:
        # Modify the name to include the version and proceed.
        name = '{0}-{1}'.format(name, version)

    if __opts__['test']:
        ret['comment'] = ('Pecl extension {0} would have been installed'
                          .format(name))
        return ret
    if __salt__['pecl.install'](name, defaults=defaults, force=force,
                                preferred_state=preferred_state):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = ('Pecl extension {0} was successfully installed'
                          .format(name))
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
        ret['comment'] = ('Pecl extension {0} would have been removed'
                          .format(name))
        return ret
    if __salt__['pecl.uninstall'](name):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = ('Pecl extension {0} was successfully removed.'
                          .format(name))
    else:
        ret['result'] = False
        ret['comment'] = 'Could not remove pecl extension {0}.'.format(name)
    return ret
