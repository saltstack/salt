# -*- coding: utf-8 -*-
'''
Manage Apache Tomcat web applications
=====================================

.. note::
    This state requires the Tomcat Manager webapp to be installed and running.

The following grains/pillars must be set for communication with Tomcat Manager
to work:

.. code-block:: yaml

    tomcat-manager:
        user: 'tomcat-manager'
        passwd: 'Passw0rd'


Configuring Tomcat Manager
--------------------------
To manage webapps via the Tomcat Manager, you'll need to configure
a valid user in the file ``conf/tomcat-users.xml``.

.. code-block:: xml
   :caption: conf/tomcat-users.xml

    <?xml version='1.0' encoding='utf-8'?>
    <tomcat-users>
        <role rolename="manager-script"/>
        <user username="tomcat-manager" password="Passw0rd" roles="manager-script"/>
    </tomcat-users>

Notes
-----

- Using multiple versions (aka. parallel deployments) on the same context
  path is not supported.
- More information about the Tomcat Manager:
  http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html
- If you use only this module for deployments you might want to restrict
  access to the manager so it's only accessible via localhost.
  For more info: http://tomcat.apache.org/tomcat-7.0-doc/manager-howto.html#Configuring_Manager_Application_Access
- Last tested on:
    Tomcat Version:
      Apache Tomcat/7.0.54
    JVM Vendor:
      Oracle Corporation
    JVM Version:
      1.8.0_101-b13
    OS Architecture:
      amd64
    OS Name:
      Linux
    OS Version:
      3.10.0-327.22.2.el7.x86_64
'''

from __future__ import absolute_import, unicode_literals, print_function

from salt.ext import six


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
                 version=True):
    '''
    Enforce that the WAR will be deployed and started in the context path,
    while making use of WAR versions in the filename.

    .. note::

        For more info about Tomcats file paths and context naming, please see
        http://tomcat.apache.org/tomcat-7.0-doc/config/context.html#Naming

    name
        The context path to deploy (incl. forward slash) the WAR to.
    war
        Absolute path to WAR file (should be accessible by the user running
        Tomcat) or a path supported by the ``salt.modules.cp.get_url`` function.
    force : False
        Force deployment even if the version strings are the same.
        Disabled by default.
    url : http://localhost:8080/manager
        The URL of the Tomcat Web Application Manager.
    timeout : 180
        Timeout for HTTP requests to the Tomcat Manager.
    temp_war_location : None
        Use another location to temporarily copy the WAR file to.
        By default the system's temp directory is used.
    version : ''
        Specify the WAR version.  If this argument is provided, it overrides
        the version encoded in the WAR file name, if one is present.

        .. versionadded:: 2015.8.6

        Use ``False`` or blank value to prevent guessing the version and keeping it blank.

        .. versionadded:: 2016.11.0

    Example:

    .. code-block:: yaml

        jenkins:
          tomcat.war_deployed:
            - name: /salt-powered-jenkins
            - war: salt://jenkins-1.2.4.war
            - require:
              - service: application-service

    .. note::

        Be aware that in the above example the WAR ``jenkins-1.2.4.war`` will
        be deployed to the context path ``salt-powered-jenkins##1.2.4``. To avoid this
        either specify a version yourself, or set version to ``False``.

    '''
    # Prepare
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # if version is defined or False, we don't want to overwrite
    if version is True:
        version = __salt__['tomcat.extract_war_version'](war) or ''
    elif not version:
        version = ''

    webapps = __salt__['tomcat.ls'](url, timeout)
    deploy = False
    undeploy = False
    status = True

    # Gathered/specified new WAR version string
    specified_ver = 'version {0}'.format(version) if version else 'no version'

    # Determine what to do
    try:
        # Printed version strings, here to throw exception if no webapps[name]
        current_ver = 'version ' + webapps[name]['version'] \
            if webapps[name]['version'] else 'no version'
        # `endswith` on the supposed string will cause Exception if empty
        if (not webapps[name]['version'].endswith(version)
            or (version == '' and webapps[name]['version'] != version)
            or force):
            deploy = True
            undeploy = True
            ret['changes']['undeploy'] = ('undeployed {0} with {1}'.
                                          format(name, current_ver))
            ret['changes']['deploy'] = ('will deploy {0} with {1}'.
                                        format(name, specified_ver))
        else:
            deploy = False
            ret['comment'] = ('{0} with {1} is already deployed'.
                              format(name, specified_ver))
            if webapps[name]['mode'] != 'running':
                ret['changes']['start'] = 'starting {0}'.format(name)
                status = False
            else:
                return ret
    except Exception:
        deploy = True
        ret['changes']['deploy'] = ('deployed {0} with {1}'.
                                    format(name, specified_ver))

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
                                               temp_war_location=temp_war_location,
                                               version=version)

    # Return
    if deploy_res.startswith('OK'):
        ret['result'] = True
        ret['comment'] = six.text_type(__salt__['tomcat.ls'](url, timeout)[name])
        ret['changes']['deploy'] = ('deployed {0} with {1}'.
                                    format(name, specified_ver))
    else:
        ret['result'] = False
        ret['comment'] = deploy_res
        ret['changes'].pop('deploy')
    return ret


def wait(name, url='http://localhost:8080/manager', timeout=180):
    '''
    Wait for the Tomcat Manager to load.

    Notice that if tomcat is not running we won't wait for it start and the
    state will fail. This state can be required in the tomcat.war_deployed
    state to make sure tomcat is running and that the manager is running as
    well and ready for deployment.

    url : http://localhost:8080/manager
        The URL of the server with the Tomcat Manager webapp.
    timeout : 180
        Timeout for HTTP request to the Tomcat Manager.

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
    Enforce that the WAR will be undeployed from the server

    name
        The context path to undeploy.
    url : http://localhost:8080/manager
        The URL of the server with the Tomcat Manager webapp.
    timeout : 180
        Timeout for HTTP request to the Tomcat Manager.

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
        ret['comment'] = 'Tomcat Manager does not respond'
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
