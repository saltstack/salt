'''
Support for Tomcat

This module uses the manager webapp to manage Apache tomcat webapps
If the manager webapp is not configured some of the functions won't work

The following grains/pillar should be set::

    tomcat-manager.user: admin user name
    tomcat-manager.passwd: password

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
import urllib
import urllib2
import tempfile
import os

# Import Salt libs
import salt.utils

__func_alias__ = {
    'reload_': 'reload'
}

# Private
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
        catalina_home = glob.glob(location)
        if catalina_home:
            return catalina_home[-1]
    return False


def _auth(uri):
    '''
    returns a authentication handler.
    Get user & password from grains, if are not set default to modules.config.option

    If user & pass are missing return False
    '''
    try:
        user = __grains__['tomcat-manager.user']
        password = __grains__['tomcat-manager.passwd']
    except KeyError:
        try:
            user = salt.utils.option('tomcat-manager.user', '', __opts__, __pillar__)
            password = salt.utils.option('tomcat-manager.passwd', '', __opts__, __pillar__)
        except Exception:
            return False

    if user == '' or password == '':
        return False

    basic = urllib2.HTTPBasicAuthHandler()
    basic.add_password(realm='Tomcat Manager Application', uri=uri, user=user, passwd=password)
    digest = urllib2.HTTPDigestAuthHandler()
    digest.add_password(realm='Tomcat Manager Application', uri=uri, user=user, passwd=password)
    return urllib2.build_opener(basic, digest)


def _wget(cmd, opts=None, url='http://localhost:8080/manager', timeout=180):
    '''
    A private function used to issue the command to tomcat via the manager webapp

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
    if auth == False:
        ret['res'] = False
        ret['msg'] = 'missing username and password settings (grain/pillar)'
        return ret

    # prepare URL
    if url[-1] != '/':
        url += '/'
    url += 'text/{0}'.format(cmd)
    if opts:
        url += '?{0}'.format(urllib.urlencode(opts))

    # Make the HTTP request
    urllib2.install_opener(auth)

    try:
        ret['msg'] = urllib2.urlopen(url, timeout=timeout).read().splitlines()
        if not ret['msg'][0].startswith('OK'):
            ret['res'] = False
    except Exception:
        ret['res'] = False
        ret['msg'] = 'Failed to create HTTP request'

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

    CLI Examples::

        salt '*' tomcat.leaks
    '''

    return '\n'.join(_wget('findleaks', {'statusLine': 'true'}, url, timeout=timeout)['msg'])


def status(url='http://localhost:8080/manager', timeout=180):
    '''
    Used to test if the tomcat manager is up

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples::

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

    CLI Examples::

        salt '*' tomcat.ls
        salt '*' tomcat.ls http://localhost:8080/manager
    '''

    ret = {}
    data = _wget('list', '', url, timeout=timeout)
    if data['res'] == False:
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

    CLI Examples::

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

    CLI Examples::

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

    CLI Examples::

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

    CLI Examples::

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

    CLI Examples::

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
    return detailes about the server

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request

    CLI Examples::

        salt '*' tomcat.serverinfo
        salt '*' tomcat.serverinfo http://localhost:8080/manager
    '''

    data = _wget('serverinfo', {}, url, timeout=timeout)
    if data['res'] == False:
        return {'error': data['msg'][0]}

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

    CLI Examples::

        salt '*' tomcat.undeploy /jenkins
        salt '*' tomcat.undeploy /jenkins http://localhost:8080/manager
    '''

    return _simple_cmd('undeploy', app, url, timeout=timeout)


def deploy_war(war, context, force='no', url='http://localhost:8080/manager', env='base', timeout=180):
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
    env : base
        the environment for WAR file in used by salt.modules.cp.get_file
        function
    timeout : 180
        timeout for HTTP request

    CLI Examples::

        cp module
        salt '*' tomcat.deploy_war salt://application.war /api
        salt '*' tomcat.deploy_war salt://application.war /api no
        salt '*' tomcat.deploy_war salt://application.war /api yes http://localhost:8080/manager

        minion local file system
        salt '*' tomcat.deploy_war /tmp/application.war /api
        salt '*' tomcat.deploy_war /tmp/application.war /api no
        salt '*' tomcat.deploy_war /tmp/application.war /api yes http://localhost:8080/manager
    '''

    # Copy file name if needed
    tfile = war
    if war[0] != '/':
        tfile = os.path.join(tempfile.gettempdir(), 'salt.' + os.path.basename(war))
        cached = __salt__['cp.get_file'](war, tfile, env)
        if not cached:
            return 'FAIL - could not cache the WAR file'
        __salt__['file.set_mode'](cached, '0644')

    # Prepare options
    opts = {
        'war': 'file:{0}'.format(tfile),
        'path': context,
        'version': os.path.basename(war).replace('.war', ''),
    }
    if force == 'yes':
        opts['update'] = 'true'

    # Deploy
    deployed = _wget('deploy', opts, url, timeout=timeout)
    res = '\n'.join(deployed['msg'])

    # Cleanup
    if war[0] != '/':
        __salt__['file.remove'](tfile)

    return res


# Non-Manager functions
def version():
    '''
    Return server version from catalina.sh version

    CLI Example::

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

    CLI Example::

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
            ret[comps[0]] = comps[1]
    return ret


def signal(signal=None):
    '''
    Signals catalina to start, stop, securestart, forcestop.

    CLI Example::

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
