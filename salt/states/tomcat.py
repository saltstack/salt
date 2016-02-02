# -*- coding: utf-8 -*-
'''
This state uses the manager webapp to manage Apache tomcat webapps
This state requires the manager webapp to be enabled

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

- Not supported multiple version on the same context path
- More information about tomcat manager:
    http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html
- if you use only this module for deployments you might want to restrict
    access to the manager so its only accessible via localhost
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

from __future__ import absolute_import

# import salt libs
from salt.modules.tomcat import _extract_war_version


# Private
def __virtual__():
    '''
    Load if the module tomcat exists
    '''

    return 'tomcat' if 'tomcat.status' in __salt__ else False


# Functions
def war_deployed(name,
                 war,
                 force=False,
                 url='http://localhost:8080/manager',
                 timeout=180,
                 temp_war_location=None,
                 version=''):
    '''
    Enforce that the WAR will be deployed and started in the context path
    it will make use of WAR versions

    for more info:
        http://tomcat.apache.org/tomcat-7.0-doc/config/context.html#Naming

    name
        the context path to deploy
    war
        absolute path to WAR file (should be accessible by the user running
        tomcat) or a path supported by the salt.modules.cp.get_url function
    force
        force deploy even if version strings are the same, False by default.
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request to the tomcat manager
    temp_war_location : None
        use another location to temporarily copy to war file
        by default the system's temp directory is used
    version : ''
        Specify the war version.  If this argument is provided, it overrides
        the version encoded in the war file name, if one is present.

        .. versionadded:: 2015.8.6

    Example:

    .. code-block:: yaml

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

    if not version:
        version = _extract_war_version(war)

    webapps = __salt__['tomcat.ls'](url, timeout)
    deploy = False
    undeploy = False
    status = True

    # Determine what to do
    try:
        if not webapps[name]['version'].endswith(version) or force:
            deploy = True
            undeploy = True
            ret['changes']['undeploy'] = ('undeployed {0} in version {1}'.
                    format(name, webapps[name]['version']))
            ret['changes']['deploy'] = ('will deploy {0} in version {1}'.
                    format(name, version))
        else:
            deploy = False
            ret['comment'] = ('{0} in version {1} is already deployed'.
                    format(name, version))
            if webapps[name]['mode'] != 'running':
                ret['changes']['start'] = 'starting {0}'.format(name)
                status = False
            else:
                return ret
    except Exception:
        deploy = True
        ret['changes']['deploy'] = ('deployed {0} in version {1}'.format(name,
            version))

    # Test
    if __opts__['test']:
        ret['result'] = None
        return ret

    # make sure the webapp is up if deployed
    if deploy is False:
        if status is False:
            ret['comment'] = __salt__['tomcat.start'](name, url,
                    timeout=timeout)
            ret['result'] = ret['comment'].startswith('OK')
        return ret

    # Undeploy
    if undeploy:
        un = __salt__['tomcat.undeploy'](name, url, timeout=timeout)
        if un.startswith('FAIL'):
            ret['result'] = False
            ret['comment'] = un
            return ret

    # Deploy
    deploy_res = __salt__['tomcat.deploy_war'](war,
                                               name,
                                               'yes',
                                               url,
                                               __env__,
                                               timeout,
                                               temp_war_location=temp_war_location)

    # Return
    if deploy_res.startswith('OK'):
        ret['result'] = True
        ret['comment'] = str(__salt__['tomcat.ls'](url, timeout)[name])
        ret['changes']['deploy'] = 'deployed {0} in version {1}'.format(name,
                version)
    else:
        ret['result'] = False
        ret['comment'] = deploy_res
        ret['changes'].pop('deploy')
    return ret


def wait(name, url='http://localhost:8080/manager', timeout=180):
    '''
    Wait for the tomcat manager to load

    Notice that if tomcat is not running we won't wait for it start and the
    state will fail. This state can be required in the tomcat.war_deployed
    state to make sure tomcat is running and that the manager is running as
    well and ready for deployment

    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request to the tomcat manager

    Example:

    .. code-block:: yaml

        tomcat-service:
          service.running:
            - name: tomcat
            - enable: True

        wait-for-tomcatmanager:
          tomcat.wait:
            - timeout: 300
            - require:
              - service: tomcat-service

        jenkins:
          tomcat.war_deployed:
            - name: /ran
            - war: salt://jenkins-1.2.4.war
            - require:
              - tomcat: wait-for-tomcatmanager
    '''

    result = __salt__['tomcat.status'](url, timeout)
    ret = {'name': name,
       'result': result,
       'changes': {},
       'comment': ('tomcat manager is ready' if result
               else 'tomcat manager is not ready')
       }

    return ret


def mod_watch(name, url='http://localhost:8080/manager', timeout=180):
    '''
    The tomcat watcher function.
    When called it will reload the webapp in question
    '''

    msg = __salt__['tomcat.reload'](name, url, timeout)
    result = msg.startswith('OK')

    ret = {'name': name,
       'result': result,
       'changes': {name: result},
       'comment': msg
       }

    return ret


def undeployed(name,
                 url='http://localhost:8080/manager',
                 timeout=180):
    '''
    Enforce that the WAR will be un-deployed from the server

    name
        the context path to deploy
    url : http://localhost:8080/manager
        the URL of the server manager webapp
    timeout : 180
        timeout for HTTP request to the tomcat manager

    Example:

    .. code-block:: yaml

        jenkins:
          tomcat.undeployed:
            - name: /ran
            - require:
              - service: application-service
    '''

    # Prepare
    ret = {'name': name,
       'result': True,
       'changes': {},
       'comment': ''}

    if not __salt__['tomcat.status'](url, timeout):
        ret['comment'] = 'Tomcat Manager does not response'
        ret['result'] = False
        return ret

    try:
        version = __salt__['tomcat.ls'](url, timeout)[name]['version']
        ret['changes'] = {'undeploy': version}
    except KeyError:
        return ret

    # Test
    if __opts__['test']:
        ret['result'] = None
        return ret

    undeploy = __salt__['tomcat.undeploy'](name, url, timeout=timeout)
    if undeploy.startswith('FAIL'):
        ret['result'] = False
        ret['comment'] = undeploy
        return ret

    return ret
