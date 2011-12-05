###############################################################################
#                           APACHE SOLR SALT MODULE                           #
# Author: Jed Glazner                                                         #
# Version: 0.2                                                                #
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

#######################  COMING FEATURES IN 0.3 ###############################
# 
# 1. Add command for checking for replication failures on slaves
# 2. Improve match_index_versions since it's pointless on busy solr masters
# 3. Add additional local fs checks for backups to make sure they succeeded
#
##############################################################################

import urllib2
import json
import socket
import os

# Override these in the minion config. 
'''
solr.cores: A list of core names eg ['core1','core2'].
            An empty list indicates non-multicore setup.
solr.host: The host name of solr node. (localhost)
solr.port: The port that solr runs on. (8983)
solr.baseurl: The root url path to access solr eg /solr
solr.request_timeout: The number of seconds before timing out an http/https/ftp
                      request. If nothing is specified then the python global
                      timeout setting is used.
solr.type: Possible values are 'master' or 'slave'
solr.backup_path: The path to store your backups. If you are using cores and
                  you can specify to append the core name to the path in the
                  backup method.
solr.num_backups: For versions of solr >= 3.5. Indicates the number of backups
                  to keep. This option is ignored if your version is less.
solr.init_script: The full path to your init script with start/stop options
solr.dih.options: A list of options to pass to the dih. 
-------------------
Required Options for DIH
clean (False): Clear the index before importing
commit (True): Commit the documents to the index upon completion
optimize (True): Optimize the index after commit is complete
verbose (True): Get verbose output
'''
#sane defaults
__opts__ = {'solr.cores': [],
            'solr.host': 'localhost',
            'solr.port': '8983',
            'solr.baseurl':'/solr',
            'solr.type':'master',
            'solr.request_timeout': None,
            'solr.init_script': '/etc/rc.d/solr',
            'solr.dih.import_options': {'clean':False, 'optimize':True,
                                        'commit':True, 'verbose':False},
            'solr.backup_path': None,
            'solr.num_backups':1
            }

########################## PRIVATE METHODS ##############################

def __virtual__():
    '''
    PRIVATE METHOD
    Solr needs to be installed to use this.

    Return: str/bool Indicates weather solr is present or not

    TODO:// currently __salt__ is not available to call in this method because 
    all the salt modules have not been loaded yet. Use a grains module?
    '''
    return 'solr'
    names = ['solr', 'apache-solr']
    for name in names:
        if __salt__['pkg.version'](name):
            return 'solr'

    return False

def _check_for_cores():
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

def _get_return_dict(success=True, data={}, errors=[], warnings=[]):
    '''
    PRIVATE METHOD
    Creates a new return dict with default values. Defaults may be overwritten.

    Param: bool success Default = True
    Param: dict data Default = {}
    Param: list errors Default = []
    Param: list warnings Default= []
    '''
    ret = {'success':success, 
           'data':data, 
           'errors':errors, 
           'warnings':warnings}

    return ret

def _update_return_dict(ret, success, data, errors=[], warnings=[]):
    '''
    PRIVATE METHOD
    Updates the return dictionary and returns it.

    Param: dict ret: The original returning dictionary to update
    Param: bool success: Indicates if the call was successful.
    Param: dict data: The data to update.
    Param: list errors: Errors list to append to the return
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    ret['success'] = success
    ret['data'].update(data)
    ret['errors'] = ret['errors'] + errors
    ret['warnings'] = ret['warnings'] + warnings
    return ret 


def _format_url(handler,host=None,core_name=None,extra=[]):
    '''
    PRIVATE METHOD
    Formats the url based on parameters, and if cores are used or not

    Param: str request_handler: The request handler to hit
    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.  
    Param: list extra ([]): A list of additional name value pairs ['name=value]
    Return: str formatted url
    '''
    if host is None:
        host = __opts__['solr.host']
    port = __opts__['solr.port']
    baseurl = __opts__['solr.baseurl']
    if core_name is None:
        if extra is None or len(extra) == 0:
            return "http://{0}:{1}{2}/{3}?wt=json".format(
                    host, port, baseurl, handler)
        else:
            return "http://{0}:{1}{2}/{3}?wt=json&{4}".format(
                    host, port, baseurl, handler,"&".join(extra))
    else:
        if extra is None or len(extra) == 0:
            return "http://{0}:{1}{2}/{3}/{4}?wt=json".format(
                    host,port,baseurl,handler,core_name)
        else:
            return "http://{0}:{1}{2}/{3}/{4}?wt=json&{5}".format(
                    host,port,baseurl,handler,core_name,"&".join(extra))

def _http_request(url):
    '''
    PRIVATE METHOD
    Uses json.load to fetch the json results from the solr api.

    Param: str Url (A formatted url to and to urllib)
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    TODO://Add a timeout param.
    '''
    try:
        request_timeout = __opts__['solr.request_timeout']
        if request_timeout is None:
            data = json.load(urllib2.urlopen(url))
        else:
            data = json.load(urllib2.urlopen(url,timeout=request_timeout))
        return _get_return_dict(True, data,[])
    except Exception as e:
        return _get_return_dict(False, {}, ["{0} : {1}".format(url,e)])

def _replication_request(replication_command, host=None,core_name=None, params=[]):
    '''
    PRIVATE METHOD
    Performs the requested replication command and returns a dictionary with 
    success, errors and data as keys. The data object will contain the json 
    response.

    Param: str replication_command: The replication command to execute
    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Param: list params ([]): Any additional parameters you want send.  
                             Should be a list of strings in name=value format.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    extra = ["command={0}".format(replication_command)] + params
    url = _format_url('replication',host=host,core_name=core_name,extra=extra)
    return _http_request(url)

def _get_admin_info(command, host=None, core_name=None):
    '''
    PRIVATE METHOD
    Calls the _http_request method and passes the admin command to execute 
    and stores the data. This data is fairly static but should be refreshed 
    periodically to make sure everything this OK. The data object will contain 
    the json response. 

    Param: str command: The admin command to run
    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    url = _format_url("admin/{0}".format(command), host,core_name=core_name)
    resp =  _http_request(url)
    return resp

def _is_master():
    '''
    PRIVATE METHOD
    Simple method to determine if the minion is configured as master or slave

    Return: bool
    '''
    if __opts__['solr.type'] == 'master':
        return True
    return False

def _merge_options(options):
    '''
    PRIVATE METHOD
    updates the default import options from __opts__['solr.dih.import_options']
    with the dictionary passed in.  Also converts booleans to strings 
    to pass to solr.

    Param: dict options {str:bool}: Dictionary that over rides default options
    Return: dict {str:str}
    '''


    defaults = __opts__['solr.dih.import_options']
    if type(options) == dict:
        defaults.update(options)
    for (k,v) in defaults.items():
        if type(v) is bool:
            defaults[k] = str(bool(v)).lower()
    return defaults


def _pre_index_check(handler, host=None, core_name=None):
    '''
    PRIVATE METHOD - MASTER CALL
    Does a pre-check to make sure that all the options are set and that
    we can talk to solr before trying to send a command to solr. This
    Command should only be issued to masters.

    Param: str handler:
    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores. - this field
                                 is required if you are using cores.
    Return:  dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    #make sure that it's a master minion
    if host is None and not _is_master():
        err = ['solr.pre_indexing_check can only be called by "master" minions']
        return _get_return_dict(False, err)
    '''
    solr can run out of memory quickly if the dih is processing multiple 
    handlers at the same time, so if it's a multicore setup require a 
    core_name param.
    '''
    if core_name is None and _check_for_cores(): 
        errors = ['solr.full_import is not safe to multiple handlers at once']
        return _get_return_dict(False, errors=errors)
    #check to make sure that we're not already indexing
    resp = import_status(handler, host, core_name)
    if resp['success']:
        status = resp['data']['status']
        if status == 'busy':
            warn = ['An indexing process is already running.']
            return _get_return_dict(True, warnings=warn)
        if status != 'idle':
            errors = ['Unknown status: "{0}"'.format(status)]
            return _get_return_dict(False, data=resp['data'],errors=errors)
    else:
        errors = ['Status check failed. Response details: {0}'.format(resp)]
        return _get_return_dict(False, data=resp['data'],errors=errors)

    return resp

def _find_value(ret_dict, key, path=None):
    '''
    PRIVATE METHOD
    Traverses a dictionary of dictionaries/lists to find key
    and return the value stored.
    TODO:// this method doesn't really work very well, and it's not really very
            useful in it's current state. The purpose for this method is to
            simplify parsing the json ouput so you can just pass the key
            you want to find and have it return the value.

    Param: dict return_dict: The return dictionary
    Param: str key: The key to find in the dictionary.

    Return: list [{path:path, value:value}]
    '''
    if path is None:
        path = key
    else:
        path = "{0}:{1}".format(path, key)

    ret = []
    for (k, v) in ret_dict.items():
        if k == key:
            ret.append({path:v})
        if type(v) is list:
            for x in v:
                if type(x) is dict:
                    ret = ret + _find_value(x, key, path)
        if type(v) is dict:
            ret = ret + _find_value(v, key, path)
    return ret

########################## PUBLIC METHODS ##############################

def lucene_version(core_name=None):
    '''
    Gets the lucene version that solr is using. If you are running a multi-core
    setup you should specify a core name since all the cores run under the same
    servlet container, they will all have the same version.

    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example: 
    salt '*' solr.lucene_version 
    '''
    ret = _get_return_dict()
    #do we want to check for all the cores?
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = _get_admin_info('system', core_name=name )
            if resp['success']:
                version = resp['data']['lucene']['lucene-spec-version']
                data = {name: {'lucene_version':version}}
            else:#generally this means that an exception happened.
                data = {name:{'lucene_version':None}}
                success=False
            ret = _update_return_dict(ret,success, data, resp['errors'])
        return ret
    else:
        resp = _get_admin_info('system', core_name=core_name)
        if resp['success']:
            version = resp['data']['lucene']['lucene-spec-version']
            return _get_return_dict(True, {'version':version}, resp['errors'])
        else:
            return resp

def version(core_name=None):
    '''
    Gets the solr version for the core specified.  You should specify a core 
    here as all the cores will run under the same servlet container and so 
    will all have the same version.

    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    alt '*' solr.version
    '''
    ret = _get_return_dict()
    #do we want to check for all the cores?
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = _get_admin_info('system', core_name=name )
            if resp['success']:
                lucene = resp['data']['lucene']
                data = {name:{'version':lucene['solr-spec-version']}}
            else:
                success=False
                data = {name:{'version':None}}
            ret = _update_return_dict(ret, success, data, 
                                      resp['errors'], resp['warnings'])
        return ret
    else:
        resp = _get_admin_info('system', core_name=core_name)
        if resp['success']:
            version = resp['data']['lucene']['solr-spec-version']
            return _get_return_dict(True, {'version':version}, 
                                    reps['errors'], resp['warnings'])
        else:
            return resp

def optimize(host=None, core_name=None):
    '''
    Optimize the solr index.  Optimizing the index is a good way to keep 
    Search queries fast, but it is a very expensive operation. The ideal
    process is to run this with a master/slave configuration.  Then you 
    can optimize the master, and push the optimized index to the slaves.
    If you are running a single solr instance, or if you are going to run 
    this on a slave be aware than search performance will be horrible 
    while this command is being run. Additionally it can take a LONG time
    to run and your http request may timeout. If that happens adjust your
    timeout settings.
    
    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return:  dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    
    CLI Example:
    salt '*' solr.optimize music
    '''
    ret = _get_return_dict()

    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            url = _format_url('update',host=host,core_name=name,extra=["optimize=true"])
            resp = _http_request(url)
            if resp['success']:
                data = {name : {'data':resp['data']}}
                ret =  _update_return_dict(ret, success, data, 
                                           resp['errors'], resp['warnings'])
            else:
                success=False
                data = {name : {'data':resp['data']}}
                ret =  _update_return_dict(ret, success, data, 
                                           resp['errors'], resp['warnings'])
        return ret 
    else:
        url = _format_url('update',host=host,core_name=core_name,extra=["optimize=true"])
        return _http_request(url)

def ping(host=None, core_name=None):
    '''
    Does a health check on solr, makes sure solr can talk to the indexes. 

    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Param: str host (None): The solr host to ping. Default is localhost
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.ping music
    '''
    ret = _get_return_dict()
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = _get_admin_info('ping', host=host,core_name=name)
            if resp['success']:
                data = {name:{'status':resp['data']['status']}}
            else:
                success=False
                data = {name:{'status':None}}
            ret = _update_return_dict(ret,success, data, resp['errors'])
        return ret
    else:
        resp = _get_admin_info('ping', host=host,core_name=core_name)
        return resp

def is_replication_enabled(host=None, core_name=None):
    '''
    SLAVE CALL
    Check for errors, and determine if a slave is replicating or not.
    Param: str host (None): The solr host to query. __opts__['host'] is default
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.is_replication_enabled music
    '''
    ret = _get_return_dict()
    success = True
    # since only slaves can call this let's check the config:
    if self._is_master() and host is None:
        errors = ['Only "slave" minions can run "is_replication_enabled"']
        return ret.update({'success':False, 'errors':errors})
    #define a convenience method so we don't duplicate code
    def _checks(ret, success, resp,core):
        if response['success']:
            slave = resp['data']['details']['slave']
            # we need to initialize this to false in case there is an error
            # on the master and we can't get this info.
            replication_enabled  = 'false'
            master_url = slave['masterUrl']
            #check for errors on the slave
            if slave.has_key('ERROR'):
                success=False
                err = "{0}: {1} - {2}".format(name, slave['ERROR'], master_url)
                resp['errors'].append(err)
                #if there is an error return everything
                data = slave if core is None else {core : {'data':slave}}
            else:
                enabled = slave['masterDetails']['master']['replicationEnabled']
                '''
                if replication is turned off on the master, or polling is 
                disabled we need to return false. These may not not errors, 
                but the purpose of this call is to check to see if the slaves 
                can replicate.
                '''
            if enabled == 'false':
                resp['warnings'].append("Replication is disabled on master.")
                success = False
            if slave['isPollingDisabled'] == 'true':
                success = False
                resp['warning'].append("Polling is disabled")
            #update the return
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
        return (ret, success)

    if core_name is None and _check_for_cores():
        for name in __opts__['solr.cores']:
            response = _replication_request('details', host=host,core_name=name)
            ret, success = _checks(ret, success, response,name)
    else:
        response = _replication_request('details', host=host, core_name=core_name)
        ret, success = _checks(ret, success, response,core_name)

    return ret

def match_index_versions(host=None,core_name=None):
    '''
    SLAVE CALL
    Verifies that the master and the slave versions are in sync by 
    comparing the index version. If you are constantly pushing updates
    the index the master and slave versions will seldom match. A solution
    to this is pause indexing every so often to allow the slave to replicate
    and then call this method before allowing indexing to resume.

    Param: str host (None): The hostname of the slave to run the command on
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.match_index_versions music
    '''
    # since only slaves can call this let's check the config:
    if _is_master() and host is None:
        e = ['solr.match_index_versions can only be called by "slave" minions']
        return ret.update({'success':False, 'errors':e})
    #get the default return dict
    ret = _get_return_dict()
    success = True

    def _match(ret, success, resp, core):
        if response['success']:
            slave = resp['data']['details']['slave']
            master_url = resp['data']['details']['slave']['masterUrl']
            if slave.has_key('ERROR'):
                error = slave['ERROR']
                success=False
                err = "{0}: {1} - {2}".format(name, error, master_url)
                resp['errors'].append(err)
                #if there was an error return the entire response so the 
                #alterer can get what it wants
                data = slave if core is None else {core : {'data': slave}}
            else:
                versions = {'master':slave['masterDetails']['indexVersion'],
                            'slave' : resp['data']['details']['indexVersion'],
                            'next_replication' : slave['nextExecutionAt'],
                            'failed_list' : slave['replicationFailedAtList']
                           }
                #check the index versions
                if index_versions['master'] != index_versions['slave']:
                    success = False
                    err = "Master and Slave index versions do not match."
                    resp['errors'].append(err)
                data = versions if core is None else {core:{'data':versions}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
        else:
            success = False
            err = resp['errors']
            data = resp['data']
            ret = _update_return_dict(ret, success, data, errors=err)
        return (ret, success)
                
    #check all cores?        
    if core_name is None and _check_for_cores():
        success = True
        for name in __opts__['solr.cores']:
            response = _replication_request('details', host=host,core_name=name)
            ret, success = _match(ret, success, response, name) 
    else:
        response = _replication_request('details', host=host,core_name=core_name)
        ret, success = _match(ret , success, response, core_name)

    return ret

def replication_details(host=None, core_name=None):
    '''
    Get the full replication details.

    Param: str slave (None): The hostname of the slave to run the command on
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.replication_details music
    '''
    ret = _get_return_dict()
    if core_name is None:
        success=True
        for name in __opts__['solr.cores']:
            resp = _replication_request('details', host=host,core_name=name)
            data = {name : {'data':resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
    else:
        resp = _replication_request('details', host=host,core_name=core_name)
        if resp['success']:
            ret =  _update_return_dict(ret, success, resp['data'], 
                                        resp['errors'], resp['warnings'])
        else:
            return resp
    return ret
    
def backup(host=None, core_name=None, append_core_to_path=False):
    '''
    Tell solr make a backup.  This method can be mis-leading since it uses
    the backup api.  If an error happens during the backup you are not
    notified.  The status: 'OK' in the response simply means that solr received
    the request successfully. 

    Param: str host (None): The hostname of the slave to run the command on
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Param: str append_core_to_path (False): If True add the name of the core
                                            to the backup path. Assumes that
                                            minion backup path is not None.
                                              
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.backup music
    '''
    path = __opts__['solr.backup_path']
    print path
    numBackups = __opts__['solr.num_backups']
    print numBackups
    if path is not None:
        if not path.endswith(os.path.sep):
            path += os.path.sep

    ret = _get_return_dict()
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            params = []
            if path is not None:
                path = path + name if append_core_to_path else path
                params.append("&location={0}".format(path + name))
            params.append("&numberToKeep={0}".format(numBackups))
            resp = _replication_request('backup', host=host,core_name=name, params=params)
            if not resp['success']:
                success=False
            data = {name : {'data': resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
        return ret
    else:
        if core_name is not None and path is not None:
            if append_core_to_path:
                path += core_name
        if path is not None:
            params = ["location={0}".format(path)]
        params.append("&numberToKeep={0}".format(numBackups))
        resp = _replication_request('backup',host=host,core_name=core_name,params=params)
        return resp

def set_is_polling(polling, host=None, core_name=None):
    '''
    SLAVE CALL
    Prevent the slaves from polling the master for updates.
    
    Param: bool polling: True will enable polling. False will disable it.
    Param: str host (None): The hostname of the slave to run the command on
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    
    CLI Example:
    salt '*' solr.set_is_polling False
    '''

    ret = _get_return_dict()        
    # since only slaves can call this let's check the config:
    if _is_master() and host is None:
        err = ['solr.set_is_polling can only be called by "slave" minions']
        return ret.update({'success':False, 'errors':err})

    cmd = "enablepoll" if polling else "disapblepoll"
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = set_is_polling(cmd, host=host,core_name=name)
            if not resp['success']:
                success = False
            data = {name : {'data' : resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
        return ret
    else:
        resp = _replication_request(cmd, host=host,core_name=name)
        return resp

def set_replication_enabled(status, host=None,core_name=None):
    '''
    MASTER ONLY
    Sets the master to ignore poll requests from the slaves. Useful when 
    you don't want the slaves replicating during indexing or when clearing
    the index.

    Param bool status: Sets the replication status to the specified state.
    Param: str host (None): The hostname of the slave to run the command on
    Param str core_name (None): The name of the solr core if using cores.
                                Leave this blank if you are not using cores or
                                if you want to set the status on all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    if _is_master() and host is None:
        return _get_return_dict(False, 
                errors=['Only minions configured as master can run this'])
    cmd = 'enablereplication' if status else 'disablereplication'
    if core_name is None and _check_for_cores():
        ret = _get_return_dict()
        success=True
        for name in __opts__['solr.cores']:
            resp = set_replication_enabled(status, host, name)
            if not resp['success']:
                success = False
            data = {name : {'data' : resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                    resp['errors'], resp['warnings'])
        return ret
    else:
        if status:
            return  _replication_request(cmd, host=host, core_name=core_name)
        else:
            return  _replication_request(cmd, host=host, core_name=core_name)

def signal(signal=None):
    '''
    Signals Apache Solr to start, stop, or restart. Obviously this is only
    going to work if the minion resides on the solr host. Additionally 
    Solr doesn't ship with an init script so one must be created.

    Param: str signal (None): The command to pass to the apache solr init
                              valid values are 'start', 'stop', and 'restart'

    CLI Example:
    salt '*' solr.signal restart
    '''
    
    ret = _get_return_dict()
    valid_signals = 'start stop restart'
    if not valid_signals.count(signal):
        return
    
    cmd = "{0} {1}".format(__opts__['solr.init_script'], signal)
    out = __salt__['cmd.run'](cmd)

def reload_core(host=None,core_name=None):
    '''
    MULTI-CORE HOSTS ONLY
    Load a new core from the same configuration as an existing registered core.
    While the "new" core is initializing, the "old" one will continue to 
    accept requests. Once it has finished, all new request will go to the 
    "new" core, and the "old" core will be unloaded.

    Param: str host (None): The hostname of the slave to run the command on
    Param: str core_name: The name of the core to reload. Pass None to reload all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    ret = _get_return_dict()
    if not _check_for_cores():
        err = ['solr.reload_core can only be called by "multi-core" minions']
        return ret.update({'success':False, 'errors':err})

    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = reload_core(host, name)
            if not resp['success']:
                success = False
            data = {name : {'data' : resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                    resp['errors'], resp['warnings'])
        return ret
    extra = ['action=RELOAD', 'core={0}'.format(core_name)]
    url = _format_url('admin/cores', host=host, core_name=None,extra=extra)
    return _http_request(url)

def core_status(host=None, core_name=None):
    '''
    MULTI-CORE HOSTS ONLY
    Get the status for a given core or all cores if no core is specified

    Param: str host (None): The hostname of the slave to run the command on
    Param: str core_name: The name of the core to reload
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    ret = _get_return_dict()
    if not _check_for_cores():
        err = ['solr.reload_core can only be called by "multi-core" minions']
        return ret.update({'success':False, 'errors':err})

    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = reload_core(host, name)
            if not resp['success']:
                success = False
            data = {name : {'data' : resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                    resp['errors'], resp['warnings'])
        return ret
    extra = ['action=STATUS', 'core={0}'.format(core_name)]
    url = _format_url('admin/cores', host=host, core_name=None, extra=extra)
    print url
    return _http_request(url)

################### DIH (Direct Import Handler) COMMANDS #####################

def reload_import_config(handler, host=None,core_name=None, verbose=False):
    '''
    MASTER ONLY
    re-loads the handler config XML file.
    This command can only be run if the minion is a 'master' type
    
    Param: str handler: The name of the data import handler.
    Param: str host (None): The hostname of the slave to run the command on
    Param: str core (None): The core the handler belongs to. If running
                            'multi-core' you must specify the core name.
    Param: bool verbose (False): Run the command with verbose output.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.reload_import_config dataimport music {'clean':True}
    '''

    #make sure that it's a master minion
    if not _is_master() and host is None:
        err = ['solr.pre_indexing_check can only be called by "master" minions']
        return _get_return_dict(False, err)

    if core_name is None and _check_for_cores():
        err = ['No core specified when minion is configured as "multi-core".']
        return _get_return_dict(False, err)

    params = ['command=reload-config']
    if verbose:
        params.append("verbose=true")
    url = _format_url(handler,host=host,core_name=core_name,extra=params)    
    return _http_request(url)

def abort_import(handler, host=None,core_name=None, verbose=False):
    '''
    MASTER ONLY
    Aborts an existing import command to the specified handler.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str host (None): The hostname of the slave to run the command on
    Param: str core (None): The core the handler belongs to. if using 
                            multi-core, you must specify the name of the core.
    Param: bool verbose (False): Run the command with verbose output.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.abort_import dataimport music {'clean':True}
    '''
    if not _is_master() and host is None:
        err = ['solr.abort_import can only be called on "master" minions']
        return _get_return_dict(False, errors=err)
    
    if core_name is None and _check_for_cores():
        err = ['No core specified when minion is configured as "multi-core".']
        return _get_return_dict(False, err)
    
    params = ['command=abort']
    if verbose:
        params.append("verbose=true")
    url = _format_url(handler,host=host,core_name=core_name,extra=params)    
    return _http_request(url)

def full_import(handler, host=None, core_name=None, options={}, extra=[]):
    '''
    MASTER ONLY
    Submits an import command to the specified handler using specified options.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str host (None): The hostname of the slave to run the command on
    Param: str core (None): The core the handler belongs to. if using 
                            multi-core, you must specify the name of the core.
    Param: dict options (__opts__): A list of options such as clean, optimize
                                    commit, verbose, and pause_replication.
                                    leave blank to use __opts__ defaults.
                                    options will be merged with __opts__
    Param: dict extra ([]): Extra name value pairs to pass to the handler.
                            e.g. ["name=value"]
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.full_import dataimport music {'clean':True}
    '''
    if not _is_master():
        err = ['solr.full_import can only be called on "master" minions']
        return _get_return_dict(False, errors=err)

    if core_name is None and _check_for_cores():
        err = ['No core specified when minion is configured as "multi-core".']
        return _get_return_dict(False, err)

    resp = _pre_index_check(handler, host,core_name)
    if not resp['success']:
        return resp
    options = _merge_options(options)
    if options['clean']:
        resp = set_replication_enabled(False, host=host, core_name=core_name)
        if not resp['success']:
            errors = ['Failed to set the replication status on the master.']
            return _get_return_dict(False, errors=errors)
    params = ['command=full-import']
    for (k,v) in options.items():
        params.append("&{0}={1}".format(k,v))
    url = _format_url(handler,host=host,core_name=core_name,extra=params + extra)    
    return _http_request(url)

def delta_import(handler, host=None, core_name=None, options={}, extra=[]):
    '''
    Submits an import command to the specified handler using specified options.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str host (None): The hostname of the slave to run the command on
    Param: str core (None): The core the handler belongs to. if using 
                            multi-core, you must specify the name of the core.
    Param: dict options (__opts__): A list of options such as clean, optimize
                                    commit, verbose, and pause_replication.
                                    leave blank to use __opts__ defaults.
                                    options will be merged with __opts__
    Param dict extra ([]): Extra name value pairs to pass to the handler.
                            eg ["name=value"]
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.delta_import dataimport music {'clean':True}
    '''
    if not _is_master() and host is None:
        err = ['solr.delta_import can only be called on "master" minions']
        return _get_return_dict(False, errors=err)

    resp = _pre_index_check(handler, host=host, core_name=core_name)
    if not resp['success']:
        return resp
    options = _merge_options(options)
    #if we're nuking data, and we're multi-core disable replication for safty
    if options['clean'] and _check_for_cores():
        resp = set_replication_enabled(False, host=host,core_name=core_name)
        if not resp['success']:
            errors = ['Failed to set the replication status on the master.']
            return _get_return_dict(False, errors=errors)
    params = ['command=delta-import']
    for (k,v) in options.items():
        params.append("{0}={1}".format(k,v))
    url = _format_url(handler, host=host,core_name=core_name, extra=params + extra)
    return _http_request(url)

def import_status(handler, host=None,core_name=None, verbose=False):
    '''
    Submits an import command to the specified handler using specified options.
    This command can only be run if the minion is is configured with
    solr.type: 'master'
    
    Param: str handler: The name of the data import handler.
    Param: str host (None): The hostname of the slave to run the command on
    Param: str core (None): The core the handler belongs to. if using 
                            multi-core, you must specify the name of the core.
    Param: bool verbose (False): Specifies verbose output
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example
    salt '*' solr.import_status dataimport music False
    '''
    if not _is_master() and host is None:
        errors = ['solr.import_status can only be called by "master" minions']
        return _get_return_dict(False, errors=errors)

    extra = ["command=status"]
    if verbose:
        extra.append("verbose=true")
    url = _format_url(handler, host=host,core_name=core_name,extra=extra)
    return _http_request(url)
