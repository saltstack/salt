'''
Management of python packages
=============================

A state module to manage system installed python packages

.. code-block:: yaml

    virtualenvwrapper:
      pip:
        - installed
        - version: 3.0.1
'''


def installed(name, pip_bin=None):
    '''
    Make sure the package is installed

    name
        The name of the python package to install
    pip_bin :  None
        the pip executable to use

    '''
    if not pip_bin:
        pip_bin='pip'

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    if name in __salt__['pip.list'](name, pip_bin):
        ret['result'] = True
        ret['comment'] = 'Package already installed'
        return ret

    if __salt__['pip.install'](packages=name, bin_env=pip_bin):
        ret['result'] = True
        ret['changes'][name] = 'Installed'
        ret['comment'] = 'Package was successfully installed'
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install package'

    return ret


def removed(name, pip_bin=None):
    """
    Make sure that a package is not installed.

    name
        The name of the package to uninstall
    pip_bin : None
        the pip executable to use
    """
    if not pip_bin:
        pip_bin='pip'

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    if name not in __salt__["pip.list"](packages=name, bin_env=bin_pip):
        ret["result"] = True
        ret["comment"] = "Pacakge is not installed."
        return ret

    if __salt__["pip.uninstall"](packages=name, bin_env=pip_bin):
        ret["result"] = True
        ret["changes"][name] = "Removed"
        ret["comment"] = "Package was successfully removed."
    else:
        ret["result"] = False
        ret["comment"] = "Could not remove package."
    return ret

