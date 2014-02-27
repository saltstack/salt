# -*- coding: utf-8 -*-
'''
Service support for the REST example
'''

# Import python libs
import logging


log = logging.getLogger(__name__)

__proxyenabled__ = ['rest_sample']
# Define the module's virtual name
__virtualname__ = 'pkg'

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}

def __virtual__():
    '''
    Only work on RestExampleOS
    '''
    # Enable on these platforms only.
    enable = set((
        'RestExampleOS',
    ))
    if __grains__['os'] in enable:
        return __virtualname__
    return False


def list_pkgs(versions_as_list=False, **kwargs):
    return __opts__['proxyobject'].package_list()


def install(name=None, refresh=False, fromrepo=None,
            pkgs=None, sources=None, **kwargs):
    return __opts__['proxyobject'].package_install(name, **kwargs)


def remove(name=None, pkgs=None, **kwargs):
    return __opts__['proxyobject'].package_remove(name)


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    if len(names) == 1:
        return str(__opts__['proxyobject'].package_status(names))


def installed(
        name,
        version=None,
        refresh=False,
        fromrepo=None,
        skip_verify=False,
        pkgs=None,
        sources=None,
        **kwargs):

    p = __opts__['proxyobject'].package_status(name)
    if version is None:
        if 'ret' in p:
            return str(p['ret'])
        else:
            return True
    else:
        if p is not None:
            return version == str(p)


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.help

        salt '*' pkg.help install
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))

