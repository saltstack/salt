###############################################################################
#                           APACHE SOLR SALT MODULE                           #
# Author: Jed Glazner                                                         #
# Version: 0.1                                                                #
# Modified: 9/20/2011                                                         #
#                                                                             #
# This module uses http requests to talk to the apache solr request handlers  #
# to gather information and report errors. Because of this the minion doesn't #
# nescessarily need to reside on the actual slave.  However if you want to    #
# use the signal function the minion must reside on the physical solr host.   #
#                                                                             #
# This module supports multi-core and standard setups.  Certain methods are   #
# master/slave specific.  Make sure you set the solr.type. If you have        #
# questions or want a feature request please ask.                             #
#                                                                             #
# #############################################################################

import urllib
import json

# Override these in the minion config. solr.cores as an empty list indicates
# this is not a multi-core setup.
__opts__ = {'solr.cores': [],
            'solr.baseurl': 'http://localhost:8983/solr',
            'solr.type':'master',
            'solr.init_script': '/etc/rc.d/solr'}

def __virtual__():
    '''
    PRIVATE METHOD
    Solr needs to be installed to use this.

    Return: str/bool Indicates weather solr is present or not

    TODO: currently __salt__ is not available to call in this method because all the salt
    modules have not been loaded yet. Use a grains module?
    '''
    return 'solr'
    names = ['solr', 'apache-solr']
    for name in names:
        if __salt__['pkg.version'](name):
            return 'solr'

    return False

def __check_for_cores__():
    '''
    PRIVATE METHOD
    Checks to see if using_cores has been set or not. if it's been set
    return it, otherwise figure it out and set it. Then return it

    Return: bool True indicates that cores are used.
    '''
    if len(__opts__['solr.cores']) > 0:
        return True
    else:
        return False

def __get_return_dict__(success=True, data={}, errors=[], warnings=[]):
    '''
    PRIVATE METHOD
    Creates a new return dict with default values. Defaults may be overwritten.

    Param: bool success Default = True
    Param: dict data Default = {}
    Param: list errors Default = []
    Param: list warnings Default= []
    '''
    return {'success':success, 'data':data, 'errors':errors, 'warnings':warnings}

def __update_return_dict__(ret, success, data, errors, warnings=[]):
    '''
    PRIVATE METHOD
    Updates the return dictionary and returns it.

    Param: dict ret: The origional returning dictionary to update
    Param: bool success: Updates the dictionary to see if the call was a success
    Param: dict data: The data to update.
    Param: list errors: Errors list to append to the return
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    ret['success'] = success
    ret['data'].update(data)
    ret['errors'] = ret['errors'] + errors
    ret['warnings'] = ret['warnings'] + warnings
    return ret 


def __format_url__(request_handler,core_name=None,extra=None):
    '''
    PRIVATE METHOD
    Formats the url based on parameters, and if cores are used or not

    Param: str request_handler: The request handler to hit
    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Param: list extra: A list of additional name value pairs ([command=blah]) - Default None 
    Return: str formatted url
    '''
    if core_name is None:
        return "{0}/{1}?wt=json".format(__opts__['solr.baseurl'],request_handler)
    else:
        if extra is None:
            return "{0}/{1}/{2}?wt=json".format(__opts__['solr.baseurl'],core_name,request_handler)
        else:
            return "{0}/{1}/{2}?wt=json&{3}".format(__opts__['solr.baseurl'],core_name,request_handler,"&".join(extra))

def __http_request__(url):
    '''
    PRIVATE METHOD
    Uses json.load to fetch the json results from the solr api and returns a dict

    Param: str Url (A formatted url to and to urllib)
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    try:
        data = json.load(urllib.urlopen(url))
        return __get_return_dict__(True, data,[])
    except Exception as e:
        return __get_return_dict__(False, {}, ["{0} : {1}".format(url,e)])

def __replication_request__(replication_command, core_name=None, params=[]):
    '''
    PRIVATE METHOD
    Performs the requested replication command and returns a dictionary with success, errors and data
    as keys. The data object will contain the json response.

    Param: str replication_command: The replication command to execute
    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Param: list params ([]): Any additional parameters you want send.  Should be a list of strings in name=value format.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    url = __format_url__('replication',core_name=core_name,extra=["command={0}".format(replication_command)] + params)
    return __http_request__(url)

def __get_admin_info__(command, core_name=None):
    '''
    PRIVATE METHOD
    Calls the __http_request__ method and passes the admin command to execute and stores the data. 
    This data is fairly static but should be refreshed periodically to make sure everying this ok.
    Returns a dictionary with success, errors, and data as keys. The data object will contain the json response. 

    Param: str command: The admin command to run
    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    url = __format_url__("admin/{0}".format(command), core_name=core_name)
    resp =  __http_request__(url)
    return resp

def lucene_version(core_name=None):
    '''
    Gets the lucene version that solr is using. If you are running a multi-core setup you should specify
    a core name since all the cores run under the same servlet container, they will all have the same 
    version.

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example: 
    salt '*' solr.lucene_version 
    '''
    ret = __get_return_dict__()
    #do we want to check for all the cores?
    if core_name is None and __check_for_cores__():
        success=True
        for name in __opts__['solr.cores']:
            resp = __get_admin_info__('system', core_name=name )
            if resp['success']:
                data = {name:{'lucene_version':resp['data']['lucene']['lucene-spec-version']}}
            else:
                data = {name:{'lucene_version':None}}
                success=False
            ret = __update_return_dict__(ret,success, data, resp['errors'])
        return ret
    #we can assume all other cases will be ok since __get_admin_info__ handles None cases for core
    else:
        resp = __get_admin_info__('system', core_name=core_name)
        if resp['success']:
            version = resp['data']['lucene']['lucene-spec-version']
            return __get_return_dict__(True, {'lucene_version':version}, resp['errors'])
        else:
            return resp

def version(core_name=None):
    '''
    Gets the solr version of solr currently in use for the core specified.  You should
    specify a core here as all the cores will run under the same servelet container and
    so will all have the same version.

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    alt '*' solr.version
    '''
    ret = __get_return_dict__()
    #do we want to check for all the cores?
    if core_name is None and __check_for_cores__():
        success=True
        for name in __opts__['solr.cores']:
            resp = __get_admin_info__('system', core_name=name )
            if resp['success']:
                data = {name:{'version':resp['data']['lucene']['solr-spec-version']}}
            else:
                success=False
                data = {name:{'version':None}}
            ret = __update_return_dict__(ret,success,data,resp['errors'], resp['warnings'])
        return ret
    #we can assume all other cases will be ok since __get_admin_info__ handles None cases for core_name
    else:
        resp = __get_admin_info__('system', core_name=core_name)
        if resp['success']:
            version = resp['data']['lucene']['solr-spec-version']
            return __get_return_dict__(True, {'version':version}, reps['errors'], resp['warnings'])
        else:
            return resp

def optimize(core_name=None):
    '''
    RUN ON THE MASTER ONLY
    Optimize the solr index.  This should be done on a daily basis and only on solr masters. 
    It may take a LONG time to run and depending on timeout settings may time out the http request.
    
    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return:  dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    
    CLI Example:
    salt '*' solr.optimize music
    '''
    ret = __get_return_dict__()

    # since only masters can call this let's check the config:
    if __opts__['solr.type'] != 'master':
        return ret.update({'success':False, 'errors':ret['errors'].append('Only minions configured as solr masters can run this')})

    if core_name is None and __check_for_cores__():
        success=True
        for name in __opts__['solr.cores']:
            url = __format_url__('update',core_name=name,extra=["optimize=true"])
            resp = __http_request__(url)
            if resp['success']:
                ret =  __update_return_dict__(ret, success, {name : {'data':resp['data']}}, resp['errors'], resp['warnings'])
            else:
                success=False
                ret =  __update_return_dict__(ret, success, {name : {'data':resp['data']}}, resp['errors'], resp['warnings'])
        return ret 
    else:
        url = __format_url__('update',core_name=core_name,extra=["optimize=true"])
        return __http_request__(url)

def ping(core_name=None):
    '''
    Does a health check on solr, makes sure solr can talk to the indexes. Leave core_name empty to check all cores.

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.ping music
    '''
    ret = __get_return_dict__()
    if core_name is None and __check_for_cores__():
        success=True
        for name in __opts__['solr.cores']:
            resp = __get_admin_info__('ping', core_name=name)
            if resp['success']:
                data = {name:{'status':resp['data']['status']}}
            else:
                success=False
                data = {name:{'status':None}}
            ret = __update_return_dict__(ret,success, data, resp['errors'])
        return ret
    else:
        resp = __get_admin_info__('ping', core_name=core_name)
        if resp['success']:
            return __get_return_dict__(ret,True, resp['data'], resp['errors'])
        else:
            return resp

def is_replication_enabled(core_name=None):
    '''
    USED ONLY BY SLAVES
    Check for errors, and determine if a slave is replicating or not. Returns replication data for failures

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.is_replication_enabled music
    '''
    ret = __get_return_dict__()
    success = True
    # since only slaves can call this let's check the config:
    if __opts__['solr.type'] != 'slave':
        return ret.update({'success':False, 'errors':ret['errors'].append('Only minions configured as solr slaves can run this')})
    #define a convenience method so we dont duplicate code - same checks used in cases below
    def _checks(ret, success, resp,core):
        if response['success']:
            slave = resp['data']['details']['slave']
            # we need to initialize this to false in case there is an error on the master
            # and we can't get this info.
            replication_enabled  = 'false'
            master_url = slave['masterUrl']
            #check for errors on the slave
            if slave.has_key('ERROR'):
                success=False
                resp['errors'].append("{0}: {1} - {2}".format(name, slave['ERROR'], master_url))
                #if there is an error return everything
                data = slave if core is None else {core : {'data':slave}}
            else:
                replication_enabled = slave['masterDetails']['master']['replicationEnabled']
            #if replication is turned off on the master, or polling is disabled we need to return false
            #these are not errors, but the purpose of this call is to check to see if the slaves can replicate.
            if replication_enabled == 'false':
                resp['warnings'].append("Replicaiton is disabled on the master.")
                success = False
            if slave['isPollingDisabled'] == 'true':
                success = False
                resp['warning'].append("Polling is disabled")
            #update the return
            ret = __update_return_dict__(ret, success, data, resp['errors'], resp['warnings'])
        return (ret, success)

    if core_name is None and __check_for_cores__():
        for name in __opts__['solr.cores']:
            response = __replication_request__('details', core_name=name)
            ret, success = _checks(ret, success, response,name)
    else:
        response = __replication_request__('details', core_name=core_name)
        ret, success = _checks(ret, success, response,core_name)

    return ret

def match_index_versions(core_name=None):
    '''
    SLAVE ONLY
    Verifies that the master and the slave versions are in sync by comparing the index version.

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.match_index_versions music
    '''
    #get the defualt return dict
    ret = __get_return_dict__()
    success = True
    # since only slaves can call this let's check the config:
    if __opts__['solr.type'] != 'slave':
        return ret.update({'success':False, 'errors':ret['errors'].append('Only minions configured as solr slaves can run this')})

    def _match(ret, success, resp, core):
        if response['success']:
            slave = resp['data']['details']['slave']
            master_url = resp['data']['details']['slave']['masterUrl']
            if slave.has_key('ERROR'):
                error = slave['ERROR']
                success=False
                resp['errors'].append("{0}: {1} - {2}".format(name, error, master_url))
                #if there was an error return the entire response so the alterer can get what it wants
                data = slave if core is None else {core : {'data': slave}}
            else:
                index_versions = {'master':slave['masterDetails']['indexVersion'],
                                  'slave' : resp['data']['details']['indexVersion'],
                                  'next_replication' : slave['nextExecutionAt'],
                                  'failed_replication' : slave['replicationFailedAtList']
                                  }
                #check the index versions 
                if index_versions['master'] != index_versions['slave']:
                    success = False
                    resp['errors'].append("Master and Slave index versions do not match. Next replication at: {0}".format(next_replication))
                data = index_versions if core is None else {core : {'data' : index_versions}}
            ret = __update_return_dict__(ret, success, data, resp['errors'], resp['warnings'])
        return (ret, success)
                
    #check all cores?        
    if core_name is None and __check_for_cores__():
        success = True
        for name in __opts__['solr.cores']:
            response = __replication_request__('details', core_name=name)
            ret, success = _match(ret, success, response, name) 
    else:
        response = __replication_request__('details', core_name=core_name)
        ret, success = _match(ret , success, response, core_name)

    return ret

def replication_details(core_name=None):
    '''
    Get the replication details. You can use the results from this call to pass to:
    match_index_versions OR replication_enabled.

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.replication_details music
    '''
    ret = __get_return_dict__()
    if core_name is None:
        success=True
        for name in __opts__['solr.cores']:
            resp = __replication_request__('details', core_name=name)
            ret = __update_return_dict__(ret, success, {name : {'data':resp['data']}}, resp['errors'], resp['warnings'])
    else:
        resp = __replication_request__('details', core_name=core_name)
        if resp['success']:
            ret =  __update_return_dict__(ret, success, resp['data'], resp['errors'], resp['warnings'])
        else:
            return resp
    return ret
    
def backup_master(core_name=None, path=None):
    '''
    Tell the master to make a backup. If you don't pass a core name and you are using cores
    it will backup all cores and append the name of the core to the backup path.

    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Param: str path (/srv/media/solr/backup): The base backup path. DO NOT INCLUDE THE CORE NAME IN THIS STRING.
                                              if the core name is specified or if you are using cores and leave
                                              core_name blank the name of the core will be appened to this value.
                                              
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.backup_master music
    '''
    if path is None:
        path = "/srv/media/solr/backup{0}"
    else:
        path = path + "{0}"
    ret = __get_return_dict__()
    if core_name is None and __check_for_cores__():
        success=True
        for name in __opts__['solr.cores']:
            path = path + name
            resp = __replication_request__('backup', core_name=name, extra="&location={0}".format(path))
            if resp['success']:
                ret = __update_return_dict__(ret, success, {name : {'data': resp['data']}}, resp['errors'], resp['warnings'])
            else:
                success=False
                ret = __update_return_dict__(ret, success, {name : {'data': resp['data']}}, resp['errors'], resp['warnings'])
        return ret
    else:
        if core_name is None:
            path = path.format("")
        else:
            path = path.format("/{0}".format(core_name))
        resp = __replication_request__('backup', core_name=core_name, params=["location={0}".format(path)])
        return resp

def set_is_polling(polling, core_name=None):
    '''
    SLAVE ONLY
    Prevent the slaves from polling the master for updates.
    
    Param: bool polling: True/False True will enable polling. False will disable it.
    Param: str core_name (None): The name of the solr core if using cores. Leave this blank if you
                                 you are not using cores or if you want to check all cores
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    
    CLI Example:
    salt '*' solr.set_is_polling False
    '''

    ret = __get_return_dict__()        
    # since only slaves can call this let's check the config:
    if __opts__['solr.type'] != 'slave':
        return ret.update({'success':False, 'errors':ret['errors'].append('Only minions configured as solr slaves can run this')})

    cmd = "enablepoll" if polling else "disapblepoll"
    if core_name is None and __check_for_cores__():
        success=True
        for name in __opts__['solr.cores']:
            resp = __replication_request__(cmd, core_name=name)
            if not resp['success']:
                success = False
            ret = __update_return_dict__(ret, success, {name : {'data' : resp['data']}}, resp['errors'], resp['warnings'])
        return ret
    else:
        resp = __replication_request__(cmd, core_name=name)
        return resp

def signal(signal=None):
    '''
    Signals Apache Solr to start, stop, or restart. Obvioulsy this is only
    going to work if the minion resides on the solr host. Additionally 
    Solr doesn't ship with an init script so one must be created. 

    Param: str signal (None): The command to pass to the apache solr init
                              valid values are 'start', 'stop', and 'restart'

    CLI Example:
    salt '*' solr.signal restart
    '''
    
    ret = __get_return_dict__()
    valid_signals = 'start stop restart'
    if not valid_signals.count(signal):
        return
    
    cmd = "{0} {1}".format(__opts__['solr.init_script'], signal)
    out = __salt__['cmd.run'](cmd)
