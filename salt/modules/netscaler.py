# -*- coding: utf-8 -*-

from __future__ import absolute_import
import logging
import salt.utils

try:
    from nsnitro.nsnitro import NSNitro
    from nsnitro.nsexceptions import NSNitroError
    from nsnitro.nsresources.nsserver import NSServer
    from nsnitro.nsresources.nsservice import NSService
    from nsnitro.nsresources.nsservicegroup import NSServiceGroup
    from nsnitro.nsresources.nsservicegroupserverbinding import NSServiceGroupServerBinding
    from nsnitro.nsresources.nslbvserver import NSLBVServer
    from nsnitro.nsresources.nslbvserverservicegroupbinding import NSLBVServerServiceGroupBinding
    from nsnitro.nsresources.nssslvserversslcertkeybinding import NSSSLVServerSSLCertKeyBinding
    HAS_NSNITRO = True
except ImportError:
    HAS_NSNITRO = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the nsnitro library is installed
    '''
    if salt.utils.is_windows():
        return False
    if HAS_NSNITRO:
        return 'netscaler'
    return False


def _connect(**kwargs):
    '''
    Initialise netscaler connection
    '''
    connargs = dict()

    # Shamelessy ripped from the mysql module
    def __connarg(name, key=None):
        '''
        Add key to connargs, only if name exists in our kwargs or as
        netscaler.<name> in __opts__ or __pillar__ Evaluate in said order - kwargs,
        opts then pillar. To avoid collision with other functions, kwargs-based
        connection arguments are prefixed with 'netscaler_' (i.e.
        'netscaler_host', 'netscaler_user', etc.).
        '''
        if key is None:
            key = name
        if name in kwargs:
            connargs[key] = kwargs[name]
        else:
            prefix = 'netscaler_'
            if name.startswith(prefix):
                try:
                    name = name[len(prefix):]
                except IndexError:
                    return
            val = __salt__['config.option']('netscaler.{0}'.format(name), None)
            if val is not None:
                connargs[key] = val

    __connarg('netscaler_host', 'host')
    __connarg('netscaler_user', 'user')
    __connarg('netscaler_pass', 'pass')
    # useSSL = True will be enforced
    #_connarg('connection_useSSL', 'useSSL')

    nitro = NSNitro(connargs['host'], connargs['user'], connargs['pass'], True)
    try:
        nitro.login()
    except NSNitroError as e:
        log.debug('netscaler module error - NSNitro.login() failed: {0}'.format(e.message))
        return None
    return nitro


def _disconnect(nitro):
    try:
        nitro.logout()
    except NSNitroError as e:
        log.debug('netscaler module error - NSNitro.logout() failed: {0}'.format(e.message))
        return None
    return nitro


def _servicegroup_get(sg_name, **connection_args):
    '''
    Return a service group ressource or None
    '''
    nitro = _connect(**connection_args)
    if nitro is None:
        return None
    sg = NSServiceGroup()
    sg.set_servicegroupname(sg_name)
    try:
        sg = NSServiceGroup.get(nitro, sg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroup.get() failed: {0}'.format(e.message))
        sg = None
    _disconnect(nitro)
    return sg


def _servicegroup_get_servers(sg_name, **connection_args):
    '''
    Returns a list of members of a servicegroup or None
    '''
    nitro = _connect(**connection_args)
    if nitro is None:
        return None
    sg = NSServiceGroup()
    sg.set_servicegroupname(sg_name)
    try:
        sg = NSServiceGroup.get_servers(nitro, sg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroup.get_servers failed(): {0}'.format(e.message))
        sg = None
    _disconnect(nitro)
    return sg


def _servicegroup_get_server(sg_name, s_name, s_port=None, **connection_args):
    '''
    Returns a member of a service group or None
    '''
    ret = None
    servers = _servicegroup_get_servers(sg_name, **connection_args)
    if servers is None:
        return None
    for server in servers:
        if server.get_servername() == s_name:
            if s_port is not None and s_port != server.get_port():
                ret = None
            ret = server
    return ret


def servicegroup_exists(sg_name, sg_type=None, **connection_args):
    '''
    Checks if a service group exists

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_exists 'serviceGroupName'
    '''
    sg = _servicegroup_get(sg_name, **connection_args)
    if sg is None:
        return False
    if sg_type is not None and sg_type.upper() != sg.get_servicetype():
        return False
    return True


def servicegroup_add(sg_name, sg_type='HTTP', **connection_args):
    '''
    Add a new service group
    If no service type is specified, HTTP will be used.
    Most common service types: HTTP, SSL, and SSL_BRIDGE

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_add 'serviceGroupName'
        salt '*' netscaler.servicegroup_add 'serviceGroupName' 'serviceGroupType'
    '''
    ret = True
    if servicegroup_exists(sg_name):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    sg = NSServiceGroup()
    sg.set_servicegroupname(sg_name)
    sg.set_servicetype(sg_type.upper())
    try:
        NSServiceGroup.add(nitro, sg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroup.add() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def servicegroup_delete(sg_name, **connection_args):
    '''
    Delete a new service group

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_delete 'serviceGroupName'
    '''
    ret = True
    sg = _servicegroup_get(sg_name, **connection_args)
    if sg is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSServiceGroup.delete(nitro, sg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroup.delete() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def servicegroup_server_exists(sg_name, s_name, s_port=None, **connection_args):
    '''
    Check if a server:port combination is a member of a servicegroup

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_server_exists 'serviceGroupName' 'serverName' 'serverPort'
    '''
    return _servicegroup_get_server(sg_name, s_name, s_port, **connection_args) is not None


def servicegroup_server_up(sg_name, s_name, s_port, **connection_args):
    '''
    Check if a server:port combination is in state UP in a servicegroup

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_server_up 'serviceGroupName' 'serverName' 'serverPort'
    '''
    server = _servicegroup_get_server(sg_name, s_name, s_port, **connection_args)
    #log.debug('state of {0}:{1} is {2}'.format(server.get_servername(), server.get_port(), server.get_svrstate()))
    return server is not None and server.get_svrstate() == 'UP'


def servicegroup_server_enable(sg_name, s_name, s_port, **connection_args):
    '''
    Enable a server:port member of a servicegroup

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_server_enable 'serviceGroupName' 'serverName' 'serverPort'
    '''
    ret = True
    server = _servicegroup_get_server(sg_name, s_name, s_port, **connection_args)
    if server is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSServiceGroup.enable_server(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroup.enable_server() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def servicegroup_server_disable(sg_name, s_name, s_port, **connection_args):
    '''
    Disable a server:port member of a servicegroup

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_server_disable 'serviceGroupName' 'serverName' 'serverPort'
    '''
    ret = True
    server = _servicegroup_get_server(sg_name, s_name, s_port, **connection_args)
    if server is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSServiceGroup.disable_server(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroup.disable_server() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def servicegroup_server_add(sg_name, s_name, s_port, **connection_args):
    '''
    Add a server:port member to a servicegroup

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_server_add 'serviceGroupName' 'serverName' 'serverPort'
    '''
    # Nitro will throw an error if the server is already present
    ret = True
    server = _servicegroup_get_server(sg_name, s_name, s_port, **connection_args)
    if server is not None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    sgsb = NSServiceGroupServerBinding()
    sgsb.set_servicegroupname(sg_name)
    sgsb.set_servername(s_name)
    sgsb.set_port(s_port)
    try:
        NSServiceGroupServerBinding.add(nitro, sgsb)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroupServerBinding() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def servicegroup_server_delete(sg_name, s_name, s_port, **connection_args):
    '''
    Remove a server:port member from a servicegroup

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.servicegroup_server_delete 'serviceGroupName' 'serverName' 'serverPort'
    '''
    # Nitro will throw an error if the server is already not present
    ret = True
    server = _servicegroup_get_server(sg_name, s_name, s_port, **connection_args)
    if server is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    sgsb = NSServiceGroupServerBinding()
    sgsb.set_servicegroupname(sg_name)
    sgsb.set_servername(s_name)
    sgsb.set_port(s_port)
    try:
        NSServiceGroupServerBinding.delete(nitro, sgsb)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServiceGroupServerBinding() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def _service_get(s_name, **connection_args):
    '''
    Returns a service ressource or None
    '''
    nitro = _connect(**connection_args)
    if nitro is None:
        return None
    service = NSService()
    service.set_name(s_name)
    try:
        service = NSService.get(nitro, service)
    except NSNitroError as e:
        log.debug('netscaler module error - NSService.get() failed: {0}'.format(e.message))
        service = None
    _disconnect(nitro)
    return service


def service_exists(s_name, **connection_args):
    '''
    Checks if a service exists

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.service_exists 'serviceName'
    '''
    return _service_get(s_name, **connection_args) is not None


def service_up(s_name, **connection_args):
    '''
    Checks if a service is UP

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.service_up 'serviceName'
    '''
    service = _service_get(s_name, **connection_args)
    return service is not None and service.get_svrstate() == 'UP'


def service_enable(s_name, **connection_args):
    '''
    Enable a service


    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.service_enable 'serviceName'
    '''
    ret = True
    service = _service_get(s_name, **connection_args)
    if service is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSService.enable(nitro, service)
    except NSNitroError as e:
        log.debug('netscaler module error - NSService.enable() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def service_disable(s_name, s_delay=None, **connection_args):
    '''
    Disable a service

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.service_disable 'serviceName'
        salt '*' netscaler.service_disable 'serviceName' 'delayInSeconds'
    '''
    ret = True
    service = _service_get(s_name, **connection_args)
    if service is None:
        return False
    if s_delay is not None:
        service.set_delay(s_delay)
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSService.disable(nitro, service)
    except NSNitroError as e:
        log.debug('netscaler module error - NSService.enable() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def _server_get(s_name, **connection_args):
    nitro = _connect(**connection_args)
    if nitro is None:
        return None
    server = NSServer()
    server.set_name(s_name)
    try:
        server = NSServer.get(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServer.get() failed: {0}'.format(e.message))
        server = None
    _disconnect(nitro)
    return server


def server_exists(s_name, ip=None, s_state=None, **connection_args):
    '''
    Checks if a server exists

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.server_exists 'serverName'
    '''
    server = _server_get(s_name, **connection_args)
    if server is None:
        return False
    if ip is not None and ip != server.get_ipaddress():
        return False
    if s_state is not None and s_state.upper() != server.get_state():
        return False
    return True


def server_add(s_name, s_ip, s_state=None, **connection_args):
    '''
    Add a server
    Note: The default server state is ENABLED

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.server_add 'serverName' 'serverIpAddress'
        salt '*' netscaler.server_add 'serverName' 'serverIpAddress' 'serverState'
    '''
    ret = True
    if server_exists(s_name, **connection_args):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    server = NSServer()
    server.set_name(s_name)
    server.set_ipaddress(s_ip)
    if s_state is not None:
        server.set_state(s_state)
    try:
        NSServer.add(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServer.add() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def server_delete(s_name, **connection_args):
    '''
    Delete a server

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.server_delete 'serverName'
    '''
    ret = True
    server = _server_get(s_name, **connection_args)
    if server is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSServer.delete(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServer.delete() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def server_update(s_name, s_ip, **connection_args):
    '''
    Update a server's attributes

    CLI Example:

    .. code-block:: bash

      salt '*' netscaler.server_update 'serverName' 'serverIP'
    '''
    altered = False
    cur_server = _server_get(s_name, **connection_args)
    if cur_server is None:
        return False
    alt_server = NSServer()
    alt_server.set_name(s_name)
    if cur_server.get_ipaddress() != s_ip:
        alt_server.set_ipaddress(s_ip)
        altered = True
    # Nothing to update, the server is already idem
    if altered is False:
        return False
    # Perform the update
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    ret = True
    try:
        NSServer.update(nitro, alt_server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServer.update() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def server_enabled(s_name, **connection_args):
    '''
    Check if a server is enabled globally

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.server_enabled 'serverName'
    '''
    server = _server_get(s_name, **connection_args)
    return server is not None and server.get_state() == 'ENABLED'


def server_enable(s_name, **connection_args):
    '''
    Enables a server globally

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.server_enable 'serverName'
    '''
    ret = True
    server = _server_get(s_name, **connection_args)
    if server is None:
        return False
    if server.get_state() == 'ENABLED':
        return True
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSServer.enable(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServer.enable() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def server_disable(s_name, **connection_args):
    '''
    Disable a server globally

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.server_disable 'serverName'
    '''
    ret = True
    server = _server_get(s_name, **connection_args)
    if server is None:
        return False
    if server.get_state() == 'DISABLED':
        return True
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSServer.disable(nitro, server)
    except NSNitroError as e:
        log.debug('netscaler module error - NSServer.disable() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def _vserver_get(v_name, **connection_args):
    nitro = _connect(**connection_args)
    vserver = NSLBVServer()
    vserver.set_name(v_name)
    if nitro is None:
        return None
    try:
        vserver = NSLBVServer.get(nitro, vserver)
    except NSNitroError as e:
        log.debug('netscaler module error - NSLBVServer.get() failed: {0}'.format(e.message))
        vserver = None
    _disconnect(nitro)
    return vserver


def vserver_exists(v_name, v_ip=None, v_port=None, v_type=None, **connection_args):
    '''
    Checks if a vserver exists

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_exists 'vserverName'
    '''
    vserver = _vserver_get(v_name, **connection_args)
    if vserver is None:
        return False
    if v_ip is not None and vserver.get_ipv46() != v_ip:
        return False
    if v_port is not None and vserver.get_port() != v_port:
        return False
    if v_type is not None and vserver.get_servicetype().upper() != v_type.upper():
        return False
    return True


def vserver_add(v_name, v_ip, v_port, v_type, **connection_args):
    '''
    Add a new lb vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_add 'vserverName' 'vserverIP' 'vserverPort' 'vserverType'
        salt '*' netscaler.vserver_add 'alex.patate.chaude.443' '1.2.3.4' '443' 'SSL'
    '''
    ret = True
    if vserver_exists(v_name, **connection_args):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    vserver = NSLBVServer()
    vserver.set_name(v_name)
    vserver.set_ipv46(v_ip)
    vserver.set_port(v_port)
    vserver.set_servicetype(v_type.upper())
    try:
        NSLBVServer.add(nitro, vserver)
    except NSNitroError as e:
        log.debug('netscaler module error - NSLBVServer.add() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def vserver_delete(v_name, **connection_args):
    '''
    Delete a lb vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_delete 'vserverName'
    '''
    ret = True
    vserver = _vserver_get(v_name, **connection_args)
    if vserver is None:
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    try:
        NSLBVServer.delete(nitro, vserver)
    except NSNitroError as e:
        log.debug('netscaler module error - NSVServer.delete() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def _vserver_servicegroup_get(v_name, sg_name, **connection_args):
    ret = None
    nitro = _connect(**connection_args)
    if nitro is None:
        return None
    vsg = NSLBVServerServiceGroupBinding()
    vsg.set_name(v_name)
    try:
        vsgs = NSLBVServerServiceGroupBinding.get(nitro, vsg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSLBVServerServiceGroupBinding.get() failed: {0}'.format(e.message))
        return None
    for vsg in vsgs:
        if vsg.get_servicegroupname() == sg_name:
            ret = vsg
    _disconnect(nitro)
    return ret


def vserver_servicegroup_exists(v_name, sg_name, **connection_args):
    '''
    Checks if a servicegroup is tied to a vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_servicegroup_exists 'vserverName' 'serviceGroupName'
    '''
    return _vserver_servicegroup_get(v_name, sg_name, **connection_args) is not None


def vserver_servicegroup_add(v_name, sg_name, **connection_args):
    '''
    Bind a servicegroup to a vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_servicegroup_add 'vserverName' 'serviceGroupName'
    '''
    ret = True
    if vserver_servicegroup_exists(v_name, sg_name, **connection_args):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    vsg = NSLBVServerServiceGroupBinding()
    vsg.set_name(v_name)
    vsg.set_servicegroupname(sg_name)
    try:
        NSLBVServerServiceGroupBinding.add(nitro, vsg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSLBVServerServiceGroupBinding.add() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def vserver_servicegroup_delete(v_name, sg_name, **connection_args):
    '''
    Unbind a servicegroup from a vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_servicegroup_delete 'vserverName' 'serviceGroupName'
    '''
    ret = True
    if not vserver_servicegroup_exists(v_name, sg_name, **connection_args):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    vsg = NSLBVServerServiceGroupBinding()
    vsg.set_name(v_name)
    vsg.set_servicegroupname(sg_name)
    try:
        NSLBVServerServiceGroupBinding.delete(nitro, vsg)
    except NSNitroError as e:
        log.debug('netscaler module error - NSLBVServerServiceGroupBinding.delete() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def _vserver_sslcert_get(v_name, sc_name, **connection_args):
    ret = None
    nitro = _connect(**connection_args)
    if nitro is None:
        return None
    sslcert = NSSSLVServerSSLCertKeyBinding()
    sslcert.set_vservername(v_name)
    try:
        sslcerts = NSSSLVServerSSLCertKeyBinding.get(nitro, sslcert)
    except NSNitroError as e:
        log.debug('netscaler module error - NSSSLVServerSSLCertKeyBinding.get() failed: {0}'.format(e.message))
        return None
    for sslcert in sslcerts:
        if sslcert.get_certkeyname() == sc_name:
            ret = sslcert
    return ret


def vserver_sslcert_exists(v_name, sc_name, **connection_args):
    '''
    Checks if a SSL certificate is tied to a vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_sslcert_exists 'vserverName' 'sslCertificateName'
    '''
    return _vserver_sslcert_get(v_name, sc_name, **connection_args) is not None


def vserver_sslcert_add(v_name, sc_name, **connection_args):
    '''
    Binds a SSL certificate to a vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_sslcert_add 'vserverName' 'sslCertificateName'
    '''
    ret = True
    if vserver_sslcert_exists(v_name, sc_name, **connection_args):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    sslcert = NSSSLVServerSSLCertKeyBinding()
    sslcert.set_vservername(v_name)
    sslcert.set_certkeyname(sc_name)
    try:
        NSSSLVServerSSLCertKeyBinding.add(nitro, sslcert)
    except NSNitroError as e:
        log.debug('netscaler module error - NSSSLVServerSSLCertKeyBinding.add() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret


def vserver_sslcert_delete(v_name, sc_name, **connection_args):
    '''
    Unbinds a SSL certificate from a vserver

    CLI Example:

    .. code-block:: bash

        salt '*' netscaler.vserver_sslcert_delete 'vserverName' 'sslCertificateName'
    '''
    ret = True
    if not vserver_sslcert_exists(v_name, sc_name, **connection_args):
        return False
    nitro = _connect(**connection_args)
    if nitro is None:
        return False
    sslcert = NSSSLVServerSSLCertKeyBinding()
    sslcert.set_vservername(v_name)
    sslcert.set_certkeyname(sc_name)
    try:
        NSSSLVServerSSLCertKeyBinding.delete(nitro, sslcert)
    except NSNitroError as e:
        log.debug('netscaler module error - NSSSLVServerSSLCertKeyBinding.delete() failed: {0}'.format(e.message))
        ret = False
    _disconnect(nitro)
    return ret
