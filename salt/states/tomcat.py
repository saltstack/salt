'''
This state uses the manager webapp to manage Apache tomcat webapps
This state requires the manager webapp to be enabled

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
- Not supported multiple version on the same context path
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

# Private
def __virtual__():
    '''
    Load if the module tomcat exists
    '''
    
    return 'tomcat' if 'tomcat.status' in __salt__ else False

def war_deployed(name, war, url='http://localhost:8080/manager', __env__='base'):
    '''
    Enforce that the war will be deployed and started in the context path
    it will make use of war versions
    
    for more info: http://tomcat.apache.org/tomcat-7.0-doc/config/context.html#Naming
    
    name: the context path to deploy
    war: absolute path to war file (should be accessable by the user running tomcat)
         or a path supported by the salt.modules.cp.get_file function
    url: the url of the server manager webapp
        default: http://localhost:8080/manager
    
    Example:
    jenkins:
      tomcat.war_deployed:
        - name: /ran
        - war: salt://jenkins-1.2.4.war
        - require:
          - service: application-service
    '''
    
    # Prepare
    ret = {'name': name,
       'result': True,
       'changes': {},
       'comment': ''}
    basename = war.split('/')[-1]
    version = basename.replace('.war', '');
    webapps =  __salt__['tomcat.ls']()
    deploy = False
    undeploy = False
    status = True
    context = '{0}##{1}'.format(name, version)
    
    # Determine what to do
    try:
        if version != webapps[name]['version']:
            deploy = True
            undeploy = True
            ret['changes']['undeploy'] = 'undeployed {0} in version {1}'.format(name, webapps[name]['version'])
            ret['changes']['deploy'] = 'will deploy {0} in version {1}'.format(name, version)
        else:
            deploy = False
            ret['comment'] = '{0} in version {1} is already deployed'.format(name, version)
            if webapps[name]['mode'] != 'running':
                ret['changes']['start'] = 'starting {0}'.format(name, version)
                status = False
    except Exception:
        deploy = True
        ret['changes']['deploy'] = 'deployed {0} in version {1}'.format(name, version)
    
    # Test
    if __opts__['test']:
        return ret
    
    # make sure the webapp is up if deployed
    if deploy == False:
        if status == False:
            ret['comment'] = __salt__['tomcat.start'](name, url)
            ret['result'] = ret['comment'].startswith('OK')
        return ret
    
    # Undeploy
    if undeploy:
        un = __salt__['tomcat.undeploy'](name)
        if un.startswith('FAIL'):
            ret['result'] = False
            ret['comment'] = un
            return ret
    
    # Deploy
    deploy_res = __salt__['tomcat.deploy_war'](war, name, 'yes', url, __env__)
    
    # Return
    if deploy_res.startswith('OK'):
        ret['result'] = True
        ret['comment'] = __salt__['tomcat.ls']()[name]
        ret['changes']['deploy'] = 'deployed {0} in version {1}'.format(name, version)
    else:
        ret['result'] = False
        ret['comment'] = deploy_res
        ret['changes'].pop('deploy')
    return ret
