# -*- coding: utf-8 -*-
'''
Support for Config Server Firewall (CSF)
========================================
:maintainer: Mostafa Hussein <mostafa.hussein91@gmail.com>
:maturity: new
:platform: Linux
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.utils


def __virtual__():
    '''
    Only load if csf exists on the system
    '''
    if salt.utils.which('csf') is None:
        return (False,
                'The csf execution module cannot be loaded: csf unavailable.')
    else:
        return True


def _temp_exists(method, ip):
    '''
    Checks if the ip exists as a temporary rule based
    on the method supplied, (tempallow, tempdeny).
    '''
    _type = method.replace('temp', '').upper()
    cmd = "csf -t | awk -v code=1 -v type=_type -v ip=ip '$1==type && $2==ip {{code=0}} END {{exit code}}'".format(_type, ip)
    exists = __salt__['cmd.run_all'](cmd)
    return not bool(exists['retcode'])


def _exists_with_port(method, rule):
    path = '/etc/csf/csf.{0}'.format(method)
    return __salt__['file.contains'](path, rule)


def exists(method,
            ip,
            port=None,
            proto='tcp',
            direction='in',
            port_origin='d',
            ip_origin='d',
            comment=''):
    '''
    Returns true a rule for the ip already exists 
    based on the method supplied. Returns false if 
    not found.
    CLI Example:
    .. code-block:: bash
        salt '*' csf.exists allow 1.2.3.4
        salt '*' csf.exists tempdeny 1.2.3.4
    '''
    if method.startswith('temp'):
        return _temp_exists(method, ip)
    if port:
        rule = _build_port_rule(ip, port, proto, direction, port_origin, ip_origin, comment)
        return _exists_with_port(method, rule)
    exists = __salt__['cmd.run_all']("egrep ^'{0} +' /etc/csf/csf.{1}".format(ip, method))
    return not bool(exists['retcode'])


def __csf_cmd(cmd):
    '''
    Execute csf command
    '''
    csf_cmd = '{0} {1}'.format(salt.utils.which('csf'), cmd)
    out = __salt__['cmd.run_all'](csf_cmd)

    if out['retcode'] != 0:
        if not out['stderr']:
            ret = out['stdout']
        else:
            ret = out['stderr']
        raise CommandExecutionError(
            'csf failed: {0}'.format(msg)
        )
    else:
        ret = out['stdout']
    return ret


def _status_csf():
    '''
    Return True if csf is running otherwise return False
    '''
    cmd = 'test -e /etc/csf/csf.disable'
    out = __salt__['cmd.run_all'](cmd)
    return bool(out['retcode'])


def _get_opt(method):
    '''
    Returns the cmd option based on a long form argument.
    '''
    opts = {
        'allow': '-a',
        'deny': '-d',
        'unallow': '-ar',
        'undeny': '-dr',
        'tempallow': '-ta',
        'tempdeny': '-td'
    }
    return opts[method]


def _build_args(method, ip, comment):
    '''
    Returns the cmd args for csf basic allow/deny commands.
    '''
    opt = _get_opt(method)
    args = '{0} {1}'.format(opt, ip)
    if comment:
        args += ' {0}'.format(comment)
    return args


def _access_rule(method,
                ip=None,
                port=None,
                proto='tcp',
                direction='in',
                port_origin='d',
                ip_origin='d',
                comment=''):
    '''
    Handles the cmd execution for allow and deny commands.
    '''
    if _status_csf():
        if ip is None:
            return {'error': 'You must supply an ip address or CIDR.'}
        if port is None:
            args = _build_args(method, ip, comment)
            return __csf_cmd(args)
        else:
            if method not in ['allow', 'deny']:
                return {'error': 'Only allow and deny rules are allowed when specifying a port.'}
            return _access_rule_with_port(method, ip, port, proto, direction, port_origin, ip_origin, comment)

def _build_port_rule(ip, port, proto, direction, port_origin, ip_origin, comment):
    kwargs = {
        'ip': ip,
        'port': port,
        'proto': proto,
        'direction': direction,
        'port_origin': port_origin,
        'ip_origin': ip_origin,
    }
    rule = '{proto}|{direction}|{port_origin}={port}|{ip_origin}={ip}'.format(**kwargs)
    if comment:
        rule += ' #{0}'.format(comment)
    
    return rule


def _access_rule_with_port(method,
                            ip,
                            port,
                            proto='tcp', 
                            direction='in',
                            port_origin='d',
                            ip_origin='d',
                            comment=''):
    _exists = exists(method, ip, port, proto, direction, port_origin, ip_origin, comment)
    if _exists:
        return _exists
    rule = _build_port_rule(ip, port, proto, direction, port_origin, ip_origin, comment)
    path = '/etc/csf/csf.{0}'.format(method)
    return __salt__['file.append'](path, rule)


def _tmp_access_rule(method,
                    ip=None, 
                    ttl=None, 
                    port=None, 
                    direction='in',
                    port_origin='d',
                    ip_origin='d',
                    comment=''):
    '''
    Handles the cmd execution for tempdeny and tempallow commands.
    '''
    if _status_csf():
        if ip is None:
            return {'error': 'You must supply an ip address or CIDR.'}
        if ttl is None:
            return {'error': 'You must supply a ttl.'}
        args = _build_tmp_access_args(method, ip, ttl, port, direction, comment)
        return __csf_cmd(args)
            

def _build_tmp_access_args(method, ip, ttl, port, direction, comment):
    '''
    Builds the cmd args for temporary access/deny opts.
    '''
    opt = _get_opt(method)
    args = '{0} {1} {2}'.format(opt, ip, ttl)
    if port:
        args += ' -p {0}'.format(port)
    if direction:
        args += ' -d {0}'.format(direction)
    if comment:
        args += ' #{0}'.format(comment) 
    return args


def running():
    '''
    Check csf status
    CLI Example:
    .. code-block:: bash
        salt '*' csf.running
    '''
    return _status_csf()


def disable():
    '''
    Disable csf permanently
    CLI Example:
    .. code-block:: bash
        salt '*' csf.disable
    '''
    if _status_csf():
        return __csf_cmd('-x')


def enable():
    '''
    Activate csf if not running
    CLI Example:
    .. code-block:: bash
        salt '*' csf.enable
    '''
    if not _status_csf():
        return __csf_cmd('-e')


def reload():
    '''
    Restart csf
    CLI Example:
    .. code-block:: bash
        salt '*' csf.reload
    '''
    if not _status_csf():
        return __csf_cmd('-r')


def tempallow(ip=None, ttl=None, port=None, direction=None, comment=''):
    '''
    Add an rule to the temporary ip allow list.
    See :func:`_access_rule`.
    1- Add an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.tempallow 127.0.0.1 3600 port=22 direction='in' comment='# Temp dev ssh access'
    '''
    return _tmp_access_rule('tempallow', ip, ttl, port, direction, comment)

def tempdeny(ip=None, ttl=None, port=None, direction=None, comment=''):
    '''
    Add a rule to the temporary ip deny list.
    See :func:`_access_rule`.
    1- Add an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.tempdeny 127.0.0.1 300 port=22 direction='in' comment='# Brute force attempt'
    '''
    return _tmp_access_rule('tempdeny', ip, ttl, port, direction, comment)

def allow(ip,
        port=None,
        proto='tcp',
        direction='in',
        port_origin='d',
        ip_origin='s',
        comment=''):
    '''
    Add an rule to csf allowed hosts
    See :func:`_access_rule`.
    1- Add an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.allow 127.0.0.1
        salt '*' csf.allow 127.0.0.1 comment="Allow localhost"
    '''
    return _access_rule('allow', ip, port, proto, direction, port_origin, ip_origin, comment)


def deny(ip,
        port=None,
        proto='tcp',
        direction='in',
        port_origin='d',
        ip_origin='d',
        comment=''):
    '''
    Add an rule to csf denied hosts
    See :func:`_access_rule`.
    1- Deny an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.deny 127.0.0.1
        salt '*' csf.deny 127.0.0.1 comment="Too localhosty"
    '''
    return _access_rule('deny', ip, port, proto, direction, port_origin, ip_origin, comment)


def unallow(ip):
    '''
    Remove a rule from the csf denied hosts
    See :func:`_access_rule`.
    1- Deny an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.unallow 127.0.0.1
    '''
    return _access_rule('unallow', ip)


def undeny(ip):
    '''
    Remove a rule from the csf denied hosts
    See :func:`_access_rule`.
    1- Deny an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.undeny 127.0.0.1
    '''
    return _access_rule('undeny', ip)

