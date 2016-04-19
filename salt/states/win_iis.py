# -*- coding: utf-8 -*-
'''
Microsoft IIS site management

This module provides the ability to add/remove websites and application pools
from Microsoft IIS.

.. versionadded:: 2016.3.0

'''

# Import python libs
from __future__ import absolute_import


# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Load only on minions that have the win_iis module.
    '''
    if 'win_iis.create_site' in __salt__:
        return __virtualname__
    return False


def _get_binding_info(hostheader='', ipaddress='*', port=80):
    '''
    Combine the host header, IP address, and TCP port into bindingInformation format.
    '''
    ret = r'{0}:{1}:{2}'.format(ipaddress, port, hostheader.replace(' ', ''))

    return ret


def deployed(name, sourcepath, apppool='', hostheader='', ipaddress='*', port=80, protocol='http'):
    '''
    Ensure the website has been deployed.

    .. note:

        This function only validates against the site name, and will return True even
        if the site already exists with a different configuration. It will not modify
        the configuration of an existing site.

    :param str name: The IIS site name.
    :param str sourcepath: The physical path of the IIS site.
    :param str apppool: The name of the IIS application pool.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str protocol: The application protocol of the binding.

    .. note:

        If an application pool is specified, and that application pool does not already exist,
        it will be created.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    current_sites = __salt__['win_iis.list_sites']()

    if name in current_sites:
        ret['comment'] = 'Site already present: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Site will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created site: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_site'](name, sourcepath, apppool,
                                                        hostheader, ipaddress, port,
                                                        protocol)
    return ret


def remove_site(name):
    '''
    Delete a website from IIS.

    :param str name: The IIS site name.
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    current_sites = __salt__['win_iis.list_sites']()

    if name not in current_sites:
        ret['comment'] = 'Site has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Site will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        ret['comment'] = 'Removed site: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_site'](name)
    return ret


def create_binding(name, site, hostheader='', ipaddress='*', port=80, protocol='http', sslflags=0):
    '''
    Create an IIS binding.

    .. note:

        This function only validates against the binding ipaddress:port:hostheader combination,
        and will return True even if the binding already exists with a different configuration.
        It will not modify the configuration of an existing binding.

    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str protocol: The application protocol of the binding.
    :param str sslflags: The flags representing certificate type and storage of the binding.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_bindings = __salt__['win_iis.list_bindings'](site)

    if binding_info in current_bindings:
        ret['comment'] = 'Binding already present: {0}'.format(binding_info)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Binding will be created: {0}'.format(binding_info)
        ret['changes'] = {'old': None,
                          'new': binding_info}
    else:
        ret['comment'] = 'Created binding: {0}'.format(binding_info)
        ret['changes'] = {'old': None,
                          'new': binding_info}
        ret['result'] = __salt__['win_iis.create_binding'](site, hostheader, ipaddress,
                                                           port, protocol, sslflags)
    return ret


def remove_binding(name, site, hostheader='', ipaddress='*', port=80):
    '''
    Remove an IIS binding.

    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_bindings = __salt__['win_iis.list_bindings'](site)

    if binding_info not in current_bindings:
        ret['comment'] = 'Binding has already been removed: {0}'.format(binding_info)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Binding will be removed: {0}'.format(binding_info)
        ret['changes'] = {'old': binding_info,
                          'new': None}
    else:
        ret['comment'] = 'Removed binding: {0}'.format(binding_info)
        ret['changes'] = {'old': binding_info,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_binding'](site, hostheader,
                                                           ipaddress, port)
    return ret


def create_cert_binding(name, site, hostheader='', ipaddress='*', port=443, sslflags=0):
    '''
    Assign a certificate to an IIS binding.

    .. note:

        The web binding that the certificate is being assigned to must already exist.

    :param str name: The thumbprint of the certificate.
    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str sslflags: Flags representing certificate type and certificate storage of the binding.

    .. versionadded:: Carbon
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_cert_bindings = __salt__['win_iis.list_cert_bindings'](site)

    if binding_info in current_cert_bindings:
        current_name = current_cert_bindings[binding_info]['certificatehash']

        if name == current_name:
            ret['comment'] = 'Certificate binding already present: {0}'.format(name)
            ret['result'] = True
            return ret
        ret['comment'] = ('Certificate binding already present with a different'
                          ' thumbprint: {0}'.format(current_name))
        ret['result'] = False
    elif __opts__['test']:
        ret['comment'] = 'Certificate binding will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created certificate binding: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_cert_binding'](name, site, hostheader,
                                                                ipaddress, port, sslflags)
    return ret


def remove_cert_binding(name, site, hostheader='', ipaddress='*', port=443):
    '''
    Remove a certificate from an IIS binding.

    .. note:

        This function only removes the certificate from the web binding. It does
        not remove the web binding itself.

    :param str name: The thumbprint of the certificate.
    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.

    .. versionadded:: Carbon
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_cert_bindings = __salt__['win_iis.list_cert_bindings'](site)

    if binding_info not in current_cert_bindings:
        ret['comment'] = 'Certificate binding has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Certificate binding will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        current_name = current_cert_bindings[binding_info]['certificatehash']

        if name == current_name:
            ret['comment'] = 'Removed certificate binding: {0}'.format(name)
            ret['changes'] = {'old': name,
                              'new': None}
            ret['result'] = __salt__['win_iis.remove_cert_binding'](name, site, hostheader,
                                                                    ipaddress, port)
    return ret


def create_apppool(name):
    '''
    Create an IIS application pool.

    .. note:

        This function only validates against the application pool name, and will return
        True even if the application pool already exists with a different configuration.
        It will not modify the configuration of an existing application pool.

    :param str name: The name of the IIS application pool.
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    current_apppools = __salt__['win_iis.list_apppools']()

    if name in current_apppools:
        ret['comment'] = 'Application pool already present: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Application pool will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created application pool: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_apppool'](name)
    return ret


def remove_apppool(name):
    # Remove IIS AppPool
    '''
    Remove an IIS application pool.

    :param str name: The name of the IIS application pool.
    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    current_apppools = __salt__['win_iis.list_apppools']()

    if name not in current_apppools:
        ret['comment'] = 'Application pool has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Application pool will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        ret['comment'] = 'Removed application pool: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_apppool'](name)
    return ret


def create_app(name, site, sourcepath, apppool=None):
    '''
    Create an IIS application.

    .. note:

        This function only validates against the application name, and will return True
        even if the application already exists with a different configuration. It will not
        modify the configuration of an existing application.

    :param str name: The IIS application.
    :param str site: The IIS site name.
    :param str sourcepath: The physical path.
    :param str apppool: The name of the IIS application pool.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    current_apps = __salt__['win_iis.list_apps'](site)

    if name in current_apps:
        ret['comment'] = 'Application already present: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Application will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created application: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_app'](name, site, sourcepath,
                                                       apppool)
    return ret


def remove_app(name, site):
    '''
    Remove an IIS application.

    :param str name: The application name.
    :param str site: The IIS site name.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    current_apps = __salt__['win_iis.list_apps'](site)

    if name not in current_apps:
        ret['comment'] = 'Application has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Application will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        ret['comment'] = 'Removed application: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_app'](name, site)
    return ret


def create_vdir(name, site, sourcepath, app='/'):
    '''
    Create an IIS virtual directory.

    .. note:

        This function only validates against the virtual directory name, and will return
        True even if the virtual directory already exists with a different configuration.
        It will not modify the configuration of an existing virtual directory.

    :param str name: The virtual directory name.
    :param str site: The IIS site name.
    :param str sourcepath: The physical path.
    :param str app: The IIS application.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    current_vdirs = __salt__['win_iis.list_vdirs'](site, app)

    if name in current_vdirs:
        ret['comment'] = 'Virtual directory already present: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Virtual directory will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created virtual directory: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_vdir'](name, site, sourcepath,
                                                        app)

    return ret


def remove_vdir(name, site, app='/'):
    '''
    Remove an IIS virtual directory.

    :param str name: The virtual directory name.
    :param str site: The IIS site name.
    :param str app: The IIS application.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    current_vdirs = __salt__['win_iis.list_vdirs'](site, app)

    if name not in current_vdirs:
        ret['comment'] = 'Virtual directory has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Virtual directory will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        ret['comment'] = 'Removed virtual directory: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_vdir'](name, site, app)

    return ret
