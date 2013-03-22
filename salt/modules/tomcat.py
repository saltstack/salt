'''
Support for Tomcat

This module uses the manager webapp to manage Apache tomcat webapps
If the manager webapp is not configured some of the functions won't work

The following grains should be set
tomcat-manager:
  user: admin user name
  passwd: password

or use pillar:
tomcat-manager.user: admin user name
tomcat-manager.passwd: password

and also configure a user in the conf/tomcat-users.xml file:
<?xml version='1.0' encoding='utf-8'?>
<tomcat-users>
 <role rolename="manager-script"/>
 <user username="tomcat" password="tomcat" roles="manager-script"/>
</tomcat-users>

Notes:
- More information about tomcat manager: http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html
- if you use only this module for deployments you've might want to strict access to the manager only from localhost
  for more info: http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html#Configuring_Manager_Application_Access
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
        user = __grains__['tomcat-manager']['user']
        password = __grains__['tomcat-manager']['passwd']
    except KeyError:
        try:
            user = __salt__['config.option']('tomcat-manager.user')
            password = __salt__['config.option']('tomcat-manager.passwd')
        except Exception:
            return False
    
    if user == '' or password == '':
        return False
    
    basic = urllib2.HTTPBasicAuthHandler()
    basic.add_password(realm='Tomcat Manager Application', uri=uri, user=user, passwd=password)    
    digest = urllib2.HTTPBasicAuthHandler()
    digest.add_password(realm='Tomcat Manager Application', uri=uri, user=user, passwd=password)
    return urllib2.build_opener(basic, digest)
    

def _wget(cmd, opts={}, url='http://localhost:8080/manager'):
    '''
    A private function used to issue the command to tomcat via the manager webapp
    
    cmd: the command to execute
    url: the url of the server manager webapp
        example: http://localhost:8080/manager
    opts: a dict of arguments
    
    return value is a dict in the from of
    {
        res: [True|False]
        msg: list of lines we got back from the manager
    }
    '''
    
    ret = {
        'res': True,
        'msg': []
    }
    
    # preapare authentication
    auth = _auth(url)
    if auth == False:
        ret['res'] = False
        ret['msg'] = 'missing username and password settings (grain/pillar)'
        return ret
    
    # preapare url
    if url[-1] != '/':
        url += '/'
    url += 'text/{0}'.format(cmd)
    if opts:
        url += '?{0}'.format(urllib.urlencode(opts))
    
    # Make the http request
    urllib2.install_opener(auth)
    
    try:
        ret['msg'] = urllib2.urlopen(url).read().splitlines()
        if not ret['msg'][0].startswith('OK'):
            ret['res'] = False
    except Exception:
        ret['res'] = False
        ret['msg'] = 'Failed to create http request'
    
    return ret


def _simple_cmd(cmd, app, url='http://localhost:8080/manager'):
    '''
    Simple command wrapper to commands that need only a path option
    '''
    
    try:
        full = ls(url)[app]['fullname']
        return '\n'.join(_wget(cmd,{'path': '/'+full},url)['msg'])
    except Exception:
        return 'FAIL - No context exists for path {0}'.format(app)


def status(url='http://localhost:8080/manager'):
    '''
    Used to test if the tomcat manager is up
    
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.status
        salt '*' tomcat.status http://localhost:8080/manager
    '''
    
    return _wget('list',{},url)['res']


def ls(url='http://localhost:8080/manager'):
    '''
    list all the deployed webapps
    
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.ls
        salt '*' tomcat.ls http://localhost:8080/manager
    '''
    
    ret = {}
    data = _wget('list','',url)
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


def stop(app, url='http://localhost:8080/manager'):
    '''
    Stop the webapp
    
    app: the webapp context path
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.stop /jenkins
        salt '*' tomcat.stop /jenkins http://localhost:8080/manager
    '''
    
    return _simple_cmd('stop', app, url)


def start(app, url='http://localhost:8080/manager'):
    '''
    Start the webapp
    
    app: the webapp context path
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.start /jenkins
        salt '*' tomcat.start /jenkins http://localhost:8080/manager
    '''
    
    return _simple_cmd('start', app, url)


def reload(app, url='http://localhost:8080/manager'):
    '''
    Reload the webapp
    
    app: the webapp context path
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.reload /jenkins
        salt '*' tomcat.reload /jenkins http://localhost:8080/manager
    '''
    
    return _simple_cmd('reload', app, url)


def sessions(app, url='http://localhost:8080/manager'):
    '''
    return the status of the webapp sessions
    
    app: the webapp context path
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.sessions /jenkins
        salt '*' tomcat.sessions /jenkins http://localhost:8080/manager
    '''
    
    return _simple_cmd('sessions', app, url)


def status_webapp(app, url='http://localhost:8080/manager'):
    '''
    return the status of the webapp (stopped | running | missing)
    
    app: the webapp context path
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.status_webapp /jenkins
        salt '*' tomcat.status_webapp /jenkins http://localhost:8080/manager
    '''
    
    webapps = ls(url)
    for i in webapps:
        if i == app:
            return webapps[i]['mode']
    
    return 'missing'


def serverinfo(url='http://localhost:8080/manager'):
    '''
    return detailes about the server
    
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.serverinfo
        salt '*' tomcat.serverinfo http://localhost:8080/manager
    '''
    
    data = _wget('serverinfo',{},url)
    if data['res'] == False:
        return {'error': data['msg'][0]}
    
    ret = {}
    data['msg'].pop(0)
    for line in data['msg']:
        tmp = line.split(':')
        ret[tmp[0].strip()] = tmp[1].strip()
    
    return ret


def undeploy(app, url='http://localhost:8080/manager'):
    '''
    Undeploy a webapp
    
    app: the webapp context path
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    CLI Examples::
        
        salt '*' tomcat.undeploy /jenkins
        salt '*' tomcat.undeploy /jenkins http://localhost:8080/manager
    '''
    
    return _simple_cmd('undeploy', app, url)


def deploy_war(war, context, force='no', url='http://localhost:8080/manager', env='base'):
    '''
    Deploy a war file
    
    war: absolute path to war file (should be accessable by the user running tomcat)
         or a path supported by the salt.modules.cp.get_file function
    context: the context path to deploy
    force: set True to deploy the webapp even one is deployed in the context
        default: False
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    env: the environment for war file in used by salt.modules.cp.get_file function
    
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
    tempfile = war
    if war[0] != '/':
        tempfile = '/tmp/salt.{0}'.format( war.split('/')[-1] )
        try:
            cached = __salt__['cp.get_file'](war, tempfile, env)
            __salt__['file.set_mode'](cached, '0644')
        except Exception:
            return 'FAIL - could not cache the war file'
    
    context = '{0}##{1}'.format(context, war.split('/')[-1].replace('.war',''))
    
    # Prepare options
    opts = {
        'war': 'file:{0}'.format(tempfile),
        'path': context,
    }
    if force == 'yes':
        opts['update'] = 'true'
    
    return '\n'.join(_wget('deploy',opts,url)['msg'])


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
