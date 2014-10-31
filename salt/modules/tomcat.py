# -*- coding: utf-8 -*-
'''
Support for Tomcat

This module uses the manager webapp to manage Apache tomcat webapps
If the manager webapp is not configured some of the functions won't work

The following grains/pillar should be set::

    tomcat-manager:user: admin user name
    tomcat-manager:passwd: password

and also configure a user in the conf/tomcat-users.xml file::

    <?xml version='1.0' encoding='utf-8'?>
    <tomcat-users>
        <role rolename="manager-script"/>
        <user username="tomcat" password="tomcat" roles="manager-script"/>
    </tomcat-users>

Notes:

- More information about tomcat manager:
  http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html
- if you use only this module for deployments you've might want to strict
  access to the manager only from localhost for more info:
  http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html#Configuring_Manager_Application_Access
- Tested on:

  JVM Vendor:
      Sun Microsystems Inc.
  JVM Version:
      1.6.0_43-b01
  OS Architecture:
      amd64
  OS Name:
      Linux
  OS Version:
      2.6.32-358.el6.x86_64
  Tomcat Version:
      Apache Tomcat/7.0.37
'''

# Import python libs
import glob
import hashlib
import urllib
import urllib2
import tempfile
import os
import re

# Import Salt libs
import salt.utils

__func_alias__ = {
    'reload_': 'reload'
}


def __virtual__():
    '''
    Only load tomcat if it is installed or if grains/pillar config exists
    '''
    if __catalina_home() or _auth('dummy'):
        return 'tomcat'
    return False


def __catalina_home():
    '''
    Tomcat paths differ depending on packaging
    '''
    locations = ['/usr/share/tomcat*', '/opt/tomcat']
    for location in locations:
        folders = glob.glob(location)
        if folders:
            for catalina_home in folders:
                if os.path.isdir(catalina_home + "/bin"):
                    return catalina_home
    return False


def _get_credentials():
    '''
    Get the username and password from opts, grains & pillar
    '''

    ret = {
        'user': False,
        'passwd': False
    }

    for item in ret:
        entry = 'tomcat-manager:{0}'.format(item)
        for struct in [__opts__, __grains__, __pillar__]:
            ret[item] = salt.utils.traverse_dict_and_list(struct, entry, '_|-')
            if ret[item] == '_|-':
                ret[item] = False
            else:
                break
    return ret['user'], ret['passwd']


def _auth(uri):
    '''
    returns a authentication handler.
    Get user & password from grains, if are not set default to
    modules.config.option

    If user & pass are missing return False
    '''

    user, password = _get_credentials()
    if user is False or password is False:
        return False

    basic = urllib2.HTTPBasicAuthHandler()
    basic.add_password(realm='Tomcat Manager Application', uri=uri,
            user=user, passwd=password)
    digest = urllib2.HTTPDigestAuthHandler()
    digest.add_password(realm='Tomcat Manager Application', uri=uri,
            user=user, passwd=password)
    return urllib2.build_opener(basic, digest)


def _wget(cmd, opts=None, url='http://localhost:8080/manager', timeout=180):
    '''
    A private function used to issue the command to tomcat via the manager
    webapp

    cmd
        the command to execute
    url
        the URL of the server manager webapp
        example: http://localhost:8080/manager
    opts
        a dict of arguments
    timeout
        timeout for HTTP request

    return value is a dict in the from of::

        {
            res: [True|False]
            msg: list of lines we got back from the manager
        }
    '''

    ret = {
        'res': True,
        'msg': []
    }

    # prepare authentication
    auth = _auth(url)
    if auth is False:
        ret['res'] = False
        ret['msg'] = 'missing username and password settings (grain/pillar)'
        return ret

    # prepare URL
    if url[-1] != '/':
        url += '/'
    url6 = url
    url += 'text/{0}'.format(cmd)
    url6 += '{0}'.format(cmd)
    if opts:
        url += '?{0}'.format(urllib.urlencode(opts))
        url6 += '?{0}'.format(urllib.urlencode(opts))

    # Make the HTTP request
    urllib2.install_opener(auth)

    try:
        # Trying tomcat >= 7 url
        ret['msg'] = urllib2.urlopen(url, timeout=timeout).read().splitlines()
    except Exception:
        try:
            # Trying tomcat6 url
            ret['msg'] = urllib2.urlopen(url6, timeout=timeout).read().splitlines()
        except Exception:
            ret['msg'] = 'Failed to create HTTP request'

    if not ret['msg'][0].startswith('OK'):
        ret['res'] = False

    return ret


def _simple_cmd(cmd, app, url='http://localhost:8080/manager', timeout=180):
    '''
    Simple command wrapper to commands that need only a path option
    '''

    try:
        opts = {
            'path': app,
            'version': ls(url)[app]['version']
        }
        return '\n'.join(_wget(cmd, opts, url, timeout=timeout)['msg'])
    except Exception:
        return 'FAIL - No context exists for path {0}'.format(app)


# Functions
def leaks(url='http://localhost:8080/manager', timeout=180):
    '''
    Find memory leaks in tomcat

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.leaks
    '''

    return _wget('findleaks', {'statusLine': 'true'},
        url, timeout=timeout)['msg']


def status(url='http://localhost:8080/manager', timeout=180):
    '''
    Used to test if the tomcat manager is up

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.status
        salt '*' tomcat.status http://localhost:8080/manager
    '''

    return _wget('list', {}, url, timeout=timeout)['res']


def ls(url='http://localhost:8080/manager', timeout=180):
    '''
    list all the deployed webapps

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.ls
        salt '*' tomcat.ls http://localhost:8080/manager
    '''

    ret = {}
    data = _wget('list', '', url, timeout=timeout)
    if data['res'] is False:
        return {}
    data['msg'].pop(0)
    for line in data['msg']:
        tmp = line.split(':')
        ret[tmp[0]] = {
            'mode': tmp[1],
            'sessions': tmp[2],
            'fullname': tmp[3],
            'version': '',
        }
        sliced = tmp[3].split('##')
        if len(sliced) > 1:
            ret[tmp[0]]['version'] = sliced[1]

    return ret


def stop(app, url='http://localhost:8080/manager', timeout=180):
    '''
    Stop the webapp

    app
        the webapp context path
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.stop /jenkins
        salt '*' tomcat.stop /jenkins http://localhost:8080/manager
    '''

    return _simple_cmd('stop', app, url, timeout=timeout)


def start(app, url='http://localhost:8080/manager', timeout=180):
    '''
    Start the webapp

    app
        the webapp context path
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.start /jenkins
        salt '*' tomcat.start /jenkins http://localhost:8080/manager
    '''

    return _simple_cmd('start', app, url, timeout=timeout)


def reload_(app, url='http://localhost:8080/manager', timeout=180):
    '''
    Reload the webapp

    app
        the webapp context path
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.reload /jenkins
        salt '*' tomcat.reload /jenkins http://localhost:8080/manager
    '''

    return _simple_cmd('reload', app, url, timeout=timeout)


def sessions(app, url='http://localhost:8080/manager', timeout=180):
    '''
    return the status of the webapp sessions

    app
        the webapp context path
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.sessions /jenkins
        salt '*' tomcat.sessions /jenkins http://localhost:8080/manager
    '''

    return _simple_cmd('sessions', app, url, timeout=timeout)


def status_webapp(app, url='http://localhost:8080/manager', timeout=180):
    '''
    return the status of the webapp (stopped | running | missing)

    app
        the webapp context path
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.status_webapp /jenkins
        salt '*' tomcat.status_webapp /jenkins http://localhost:8080/manager
    '''

    webapps = ls(url, timeout=timeout)
    for i in webapps:
        if i == app:
            return webapps[i]['mode']

    return 'missing'


def serverinfo(url='http://localhost:8080/manager', timeout=180):
    '''
    return details about the server

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.serverinfo
        salt '*' tomcat.serverinfo http://localhost:8080/manager
    '''

    data = _wget('serverinfo', {}, url, timeout=timeout)
    if data['res'] is False:
        return {'error': data['msg']}

    ret = {}
    data['msg'].pop(0)
    for line in data['msg']:
        tmp = line.split(':')
        ret[tmp[0].strip()] = tmp[1].strip()

    return ret


def undeploy(app, url='http://localhost:8080/manager', timeout=180):
    '''
    Undeploy a webapp

    app
        the webapp context path
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.undeploy /jenkins
        salt '*' tomcat.undeploy /jenkins http://localhost:8080/manager
    '''

    return _simple_cmd('undeploy', app, url, timeout=timeout)


def deploy_war(war,
               context,
               force='no',
               url='http://localhost:8080/manager',
               saltenv='base',
               timeout=180,
               env=None,
               temp_war_location=None):
    '''
    Deploy a WAR file

    war
        absolute path to WAR file (should be accessible by the user running
        tomcat) or a path supported by the salt.modules.cp.get_file function
    context
        the context path to deploy
    force : False
        set True to deploy the webapp even one is deployed in the context
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    saltenv : base
        the environment for WAR file in used by salt.modules.cp.get_url
        function
    timeout : 180
        timeout for HTTP request
    temp_war_location : None
        use another location to temporarily copy to war file
        by default the system's temp directory is used

    CLI Examples:

    cp module

    .. code-block:: bash

        salt '*' tomcat.deploy_war salt://application.war /api
        salt '*' tomcat.deploy_war salt://application.war /api no
        salt '*' tomcat.deploy_war salt://application.war /api yes http://localhost:8080/manager

    minion local file system

    .. code-block:: bash

        salt '*' tomcat.deploy_war /tmp/application.war /api
        salt '*' tomcat.deploy_war /tmp/application.war /api no
        salt '*' tomcat.deploy_war /tmp/application.war /api yes http://localhost:8080/manager
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    # Decide the location to copy the war for the deployment
    tfile = 'salt.{0}'.format(os.path.basename(war))
    if temp_war_location is not None:
        if not os.path.isdir(temp_war_location):
            return 'Error - "{0}" is not a directory'.format(temp_war_location)
        tfile = os.path.join(temp_war_location, tfile)
    else:
        tfile = os.path.join(tempfile.gettempdir(), tfile)

    # Copy file name if needed
    cache = False
    if not os.path.isfile(war):
        cache = True
        cached = __salt__['cp.get_url'](war, tfile, saltenv)
        if not cached:
            return 'FAIL - could not cache the WAR file'
        try:
            __salt__['file.set_mode'](cached, '0644')
        except KeyError:
            pass
    else:
        tfile = war

    version_extract = re.findall("\\d+.\\d+.\\d+?", os.path.basename(war).replace('.war', ''))
    if len(version_extract) == 1:
        version_string = version_extract[0]
    else:
        version_string = None

    # Prepare options
    opts = {
        'war': 'file:{0}'.format(tfile),
        'path': context,
        'version': version_string,
    }
    if force == 'yes':
        opts['update'] = 'true'

    # Deploy
    deployed = _wget('deploy', opts, url, timeout=timeout)
    res = '\n'.join(deployed['msg'])

    # Cleanup
    if cache:
        __salt__['file.remove'](tfile)

    return res


def passwd(passwd,
           user='',
           alg='md5',
           realm=None):
    '''
    This function replaces the $CATALINA_HOME/bin/digest.sh script
    convert a clear-text password to the $CATALINA_BASE/conf/tomcat-users.xml
    format

    CLI Examples:

    .. code-block:: bash

        salt '*' tomcat.passwd secret
        salt '*' tomcat.passwd secret tomcat sha1
        salt '*' tomcat.passwd secret tomcat sha1 'Protected Realm'
    '''
    if alg == 'md5':
        m = hashlib.md5()
    elif alg == 'sha1':
        m = hashlib.sha1()
    else:
        return False

    if realm:
        m.update('{0}:{1}:{2}'.format(
            user,
            realm,
            passwd,
            ))
    else:
        m.update(passwd)

    return m.hexdigest()


# Non-Manager functions
def version():
    '''
    Return server version from catalina.sh version

    CLI Example:

    .. code-block:: bash

        salt '*' tomcat.version
    '''
    cmd = __catalina_home() + '/bin/catalina.sh version'
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if 'Server version' in line:
            comps = line.split(': ')
            return comps[1]


def fullversion():
    '''
    Return all server information from catalina.sh version

    CLI Example:

    .. code-block:: bash

        salt '*' tomcat.fullversion
    '''
    cmd = __catalina_home() + '/bin/catalina.sh version'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if ': ' in line:
            comps = line.split(': ')
            ret[comps[0]] = comps[1].lstrip()
    return ret


def signal(signal=None):
    '''
    Signals catalina to start, stop, securestart, forcestop.

    CLI Example:

    .. code-block:: bash

        salt '*' tomcat.signal start
    '''
    valid_signals = {'forcestop': 'stop -force',
                     'securestart': 'start -security',
                     'start': 'start',
                     'stop': 'stop'}

    if signal not in valid_signals:
        return

    cmd = '{0}/bin/catalina.sh {1}'.format(
        __catalina_home(), valid_signals[signal]
    )
    __salt__['cmd.run'](cmd)
