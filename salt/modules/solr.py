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

import urllib
import json

# Override these in the minion config. 
'''
solr.cores: A list of core names eg ['core1','core2'].
            An empty list indicates non-multicore setup.
solr.baseurl: The root level url to access solr via http
solr.type: Possible values are 'master' or 'slave'
solr.init_script: The full path to your init script with start/stop options
solr.dih.options: A list of options to pass to the dih
solr.dih.options.clean: Clear the index before importing
solr.dih.options.commit: Commit the documents to the index upon completion
solr.dih.options.optimize: Optimize the index after commit is complete
solr.dih.options.verbose: Get verbose output
'''
__opts__ = {'solr.cores': [],
            'solr.baseurl': 'http://localhost:8983/solr',
            'solr.type':'master',
            'solr.init_script': '/etc/rc.d/solr',
            'solr.dih.import_options': {'clean':False, 'optimize':True,
                                        'commit':True, 'verbose':False}
            }

def __virtual__():
    '''
    PRIVATE METHOD
    Solr needs to be installed to use this.

    Return: str/bool Indicates weather solr is present or not

    TODO: currently __salt__ is not available to call in this method because 
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

def _update_return_dict(ret, success, data, errors, warnings=[]):
    '''
    PRIVATE METHOD
    Updates the return dictionary and returns it.

    Param: dict ret: The origional returning dictionary to update
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


def _format_url(handler,core_name=None,extra=[]):
    '''
    PRIVATE METHOD
    Formats the url based on parameters, and if cores are used or not

    Param: str request_handler: The request handler to hit
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.  
    Param: list extra ([]): A list of additional name value pairs ['name=value]
    Return: str formatted url
    '''
    baseurl = __opts__['solr.baseurl']
    if core_name is None:
        if extra is None:
            return "{0}/{1}?wt=json".format(baseurl, handler)
        else:
            return "{0}/{1}?wt=json&{2}".format(baseurl, handler,"&".join(extra))
    else:
        if extra is None:
            return "{0}/{1}/{2}?wt=json".format(baseurl, core_name, handler)
        else:
            return "{0}/{1}/{2}?wt=json&{3}".format(baseurl, core_name, 
                                                    handler,"&".join(extra))

def _http_request(url):
    '''
    PRIVATE METHOD
    Uses json.load to fetch the json results from the solr api.

    Param: str Url (A formatted url to and to urllib)
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    TODO://Add a timeout param.
    '''
    try:
        data = json.load(urllib.urlopen(url))
        return _get_return_dict(True, data,[])
    except Exception as e:
        return _get_return_dict(False, {}, ["{0} : {1}".format(url,e)])

def _replication_request(replication_command, core_name=None, params=[]):
    '''
    PRIVATE METHOD
    Performs the requested replication command and returns a dictionary with 
    success, errors and data as keys. The data object will contain the json 
    response.

    Param: str replication_command: The replication command to execute
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Param: list params ([]): Any additional parameters you want send.  
                             Should be a list of strings in name=value format.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    extra = ["command={0}".format(replication_command)] + params
    url = _format_url('replication',core_name=core_name,extra=extra)
    return _http_request(url)

def _get_admin_info(command, core_name=None):
    '''
    PRIVATE METHOD
    Calls the _http_request method and passes the admin command to execute 
    and stores the data. This data is fairly static but should be refreshed 
    periodically to make sure everying this ok. The data object will contain 
    the json response. 

    Param: str command: The admin command to run
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    url = _format_url("admin/{0}".format(command), core_name=core_name)
    resp =  _http_request(url)
    return resp

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
    here as all the cores will run under the same servelet container and so 
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

def optimize(core_name=None):
    '''
    RUN ON THE MASTER ONLY
    Optimize the solr index.  This should be done on a daily basis and only on
    solr masters. It may take a LONG time to run and depending on timeout 
    settings may time out the http request.
    
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return:  dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    
    CLI Example:
    salt '*' solr.optimize music
    '''
    ret = _get_return_dict()

    # since only masters can call this let's check the config:
    if __opts__['solr.type'] != 'master':
        errors = ['Only minions configured as solr masters can run this']
        return ret.update({'success':False, 'errors':errors})

    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            url = _format_url('update',core_name=name,extra=["optimize=true"])
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
        url = _format_url('update',core_name=core_name,extra=["optimize=true"])
        return _http_request(url)

def ping(core_name=None):
    '''
    Does a health check on solr, makes sure solr can talk to the indexes. 

    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.ping music
    '''
    ret = _get_return_dict()
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = _get_admin_info('ping', core_name=name)
            if resp['success']:
                data = {name:{'status':resp['data']['status']}}
            else:
                success=False
                data = {name:{'status':None}}
            ret = _update_return_dict(ret,success, data, resp['errors'])
        return ret
    else:
        resp = _get_admin_info('ping', core_name=core_name)
        if resp['success']:
            return _get_return_dict(ret,True, resp['data'], resp['errors'])
        else:
            return resp

def is_replication_enabled(core_name=None):
    '''
    USED ONLY BY SLAVES
    Check for errors, and determine if a slave is replicating or not.

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
    if __opts__['solr.type'] != 'slave':
        errors = ['Only minions configured as solr slaves can run this']
        return ret.update({'success':False, 'errors':errors})
    #define a convenience method so we dont duplicate code
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
                #if replication is turned off on the master, or polling is 
                #isabled we need to return false. These may not not errors, 
                #but the purpose of this call is to check to see if the slaves 
                #can replicate.
            if enabled == 'false':
                resp['warnings'].append("Replicaiton is disabled on master.")
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
            response = _replication_request('details', core_name=name)
            ret, success = _checks(ret, success, response,name)
    else:
        response = _replication_request('details', core_name=core_name)
        ret, success = _checks(ret, success, response,core_name)

    return ret

def match_index_versions(core_name=None):
    '''
    SLAVE ONLY
    Verifies that the master and the slave versions are in sync by 
    comparing the index version. If you are constantly pushing updates
    the index versions on the slaves will usually be out of date.

    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.match_index_versions music
    '''
    #get the defualt return dict
    ret = _get_return_dict()
    success = True
    # since only slaves can call this let's check the config:
    if __opts__['solr.type'] != 'slave':
        errors = ['Only minions configured as solr slaves can run this']
        return ret.update({'success':False, 'errors':errors})

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
        return (ret, success)
                
    #check all cores?        
    if core_name is None and _check_for_cores():
        success = True
        for name in __opts__['solr.cores']:
            response = _replication_request('details', core_name=name)
            ret, success = _match(ret, success, response, name) 
    else:
        response = _replication_request('details', core_name=core_name)
        ret, success = _match(ret , success, response, core_name)

    return ret

def replication_details(core_name=None):
    '''
    Get the full replication details.

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
            resp = _replication_request('details', core_name=name)
            data = {name : {'data':resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
    else:
        resp = _replication_request('details', core_name=core_name)
        if resp['success']:
            ret =  _update_return_dict(ret, success, resp['data'], 
                                        resp['errors'], resp['warnings'])
        else:
            return resp
    return ret
    
def backup_master(core_name=None, path=None):
    '''
    Tell the master to make a backup. If you don't pass a core name and you are
    using cores it will backup all cores and append the name of the core to the
    backup path.

    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Param: str path (/srv/media/solr/backup): The base backup path. 
                                              DO NOT INCLUDE THE CORE NAME!
                                              if the core name is specified or
                                              if you are using cores and leave
                                              core_name blank the name of the
                                              core will be appened to it.
                                              
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.backup_master music
    '''
    if path is None:
        path = "/srv/media/solr/backup{0}"
    else:
        path = path + "{0}"
    ret = _get_return_dict()
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            extra = "&location={0}".format(path + name)
            resp = _replication_request('backup', core_name=name, extra=extra)
            if not resp['success']:
                success=False
            data = {name : {'data': resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
        return ret
    else:
        if core_name is None:
            path = path.format("")
        else:
            path = path.format("/{0}".format(core_name))
        params = ["location={0}".format(path)]
        resp = _replication_request('backup',core_name=core_name,params=params)
        return resp

def set_is_polling(polling, core_name=None):
    '''
    SLAVE ONLY
    Prevent the slaves from polling the master for updates.
    
    Param: bool polling: True will enable polling. False will disable it.
    Param: str core_name (None): The name of the solr core if using cores. 
                                 Leave this blank if you are not using cores or
                                 if you want to check all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    
    CLI Example:
    salt '*' solr.set_is_polling False
    '''

    ret = _get_return_dict()        
    # since only slaves can call this let's check the config:
    if __opts__['solr.type'] != 'slave':
        err = ['Only minions configured as solr slaves can run this']
        return ret.update({'success':False, 'errors':err})

    cmd = "enablepoll" if polling else "disapblepoll"
    if core_name is None and _check_for_cores():
        success=True
        for name in __opts__['solr.cores']:
            resp = set_is_polling(cmd, core_name=name)
            if not resp['success']:
                success = False
            data = {name : {'data' : resp['data']}}
            ret = _update_return_dict(ret, success, data, 
                                        resp['errors'], resp['warnings'])
        return ret
    else:
        resp = _replication_request(cmd, core_name=name)
        return resp

def set_replication_enabled(status, core_name):
    '''
    MASTER ONLY
    Sets the master to ignore poll requests from the slaves. Useful while 
    clearning the content

    Param bool status: True/False will set replicationEnabled to status specified
    Param str core_name (None): The name of the solr core if using cores.
                                Leave this blank if you are not using cores or
                                if you want to set the status on all cores.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    if __opts__['solr.type'] != 'master':
        return _get_return_dict(False, errors=['Only minions configured as master can run this'])

    if core_name is None and _check_for_cores():
        ret = _get_return_dict()
        success=True
        for name in __opts__['solr.cores']:
            resp = set_replication_enabled(status, name)
            if not resp['success']:
                success = False
            data = {name : {'data' : resp['data']}}
            ret = _update_return_dict(ret, success, data, resp['errors'], resp['warnings'])
        return ret
    else:
        if status:
            return  _replication_request('enablereplication', core_name=core_name)
        else:
            return  _replication_request('disablereplication', core_name=core_name)

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
    
    ret = _get_return_dict()
    valid_signals = 'start stop restart'
    if not valid_signals.count(signal):
        return
    
    cmd = "{0} {1}".format(__opts__['solr.init_script'], signal)
    out = __salt__['cmd.run'](cmd)

def find_value(ret_dict, key, path=None):
    '''
    Traverses a nested dictionary of dictionaries/lists to find key
    and return the value stored.

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
                    ret = ret + find_value(x, key, path)
        if type(v) is dict:
            ret = ret + find_value(v, key, path)
    return ret

def reload_core(core_name):
    '''
    MULTI-CORE HOSTS ONLY
    Load a new core from the same configuration as an existing registered core.
    While the "new" core is initalizing, the "old" one will continue to 
    accept requests. Once it has finished, all new request will go to the 
    "new" core, and the "old" core will be unloaded.

    Param: str core_name: The name of the core to reload
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    extra = ['action=RELOAD', 'core={0}'.format(core_name)]
    url = _format_url('admin/cores', None, extra=extra)
    return _http_request(url)

def core_status(core_name):
    '''
    MULTI-CORE HOSTS ONLY
    Get the status for a given core or all cores if no core is specified

    Param: str core_name: The name of the core to reload
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}
    '''
    extra = ['action=STATUS', 'core={0}'.format(core_name)]
    url = _format_url('admin/cores', None, extra=extra)
    print url
    return _http_request(url)

### DIH COMMANDS NEW IN 0.2 ###

def _pre_indexing_check(handler, core_name, options):
    #make sure that it's a master minion
    if not __opts__['solr.type'] == 'master':
        errors = ['solr.full_import can only be accessed if the solr.type is "master"']
        return _get_return_dict(False, errors=errors)
    #solr can run out of memory quickly if the dih is run on multiple cores at the same time
    if core_name is None and _check_for_cores(): 
        errors = ['solr.full_import is not safe to run on all cores at the same time']
        return _get_return_dict(False, errors=errors)
    #check to make sure that we're not already indexing
    resp = import_status(handler, core_name)
    if resp['success']:
        if resp['data']['status'] == 'busy':
            warn = ['An indexing process is already running.']
            return _get_return_dict(True, warnings=warn)
        if resp['data']['status'] != 'idle':
            errors = ['Unable to determine the import status prior to pushing command']
            return _get_return_dict(False, data=resp['data'],errors=errors)
    else:
        errors = ['Unable to determine the import status prior to pushing command']
        return _get_return_dict(False, data=resp['data'],errors=errors)
    if not resp['success']:
        return resp
    #merge the options with the defaults
    if type(options) is dict:
         __opts__['solr.dih.import_options'].update(options)
    #check to see if replication is enabled.
    if 'clean' in __opts__['solr.dih.import_options'] and __opts__['solr.dih.import_options']['clean']:
        resp = set_replication_enabled(False, core_name)
        if not resp['success']:
            errors = ['Failed to set the replication status on the master.']
            return _get_return_dict(False, errors=errors)
    return _get_return_dict()

def reload_import_config(handler, core_name=None, verbose=False):
    '''
    re-loads the handler config xml file.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str core (None): The core the handler belongs to.
    Param: bool verbose (False): Run the command with verbose output.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.full_import /music/trackimport {'clean':True}
    '''
    params = ['command=reload-config']
    if verbose:
        params.append("verbose=true")
    url = _format_url(handler,core_name=core_name,extra=params)    
    return _http_request(url)

def abort_import(handler, core_name=None, verbose=False):
    '''
    Aborts an existing import command to the specified handler.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str core (None): The core the handler belongs to.
    Param: bool verbose (False): Run the command with verbose output.
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.full_import /music/trackimport {'clean':True}
    '''
    params = ['command=abort']
    if verbose:
        params.append("verbose=true")
    url = _format_url(handler,core_name=core_name,extra=params)    
    return _http_request(url)


def full_import(handler, core_name=None, options={}, extra={}):
    '''
    Submits an import command to the specified handler using specified options.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str core (None): The core the handler belongs to.
    Param: dict options (__opts__): A list of options such as clean, optimize
                                    commit, verbose, and pause_replication.
                                    leave blank to use __opts__ defaults.
                                    options will be merged with __opts__
    Param: dict extra ({}): Extra name value pairs to pass to the handler.
                            eg ["name=value"]
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.full_import /music/trackimport {'clean':True}
    '''
    resp = _pre_indexing_check(handler, core_name)
    if not resp['success']:
        return resp
    params = ['command=full-import']
    for (k,v) in __opts__['solr.dih.import_options']:
        params.append("{0}={1}".format(k,v))
    url = _format_url(handler,core_name=core_name,extra=params + extra)    
    return _http_request(url)

def delta_import(handler, core_name=None, options={}, extra={}):
    '''
    Submits an import command to the specified handler using specified options.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str core (None): The core the handler belongs to.
    Param: dict options (__opts__): A list of options such as clean, optimize
                                    commit, verbose, and pause_replication.
                                    leave blank to use __opts__ defaults.
                                    options will be merged with __opts__
    Param dict extra ({}): Extra name value pairs to pass to the handler.
                            eg ["name=value"]
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example:
    salt '*' solr.delta_import /music/trackimport {'clean':True}
    '''
    resp = _pre_indexing_check(handler, core_name)
    if not resp['success']:
        return resp
    params = ['command=delta-import']
    for (k,v) in __opts__['solr.dih.import_options']:
        params.append("{0}={1}".format(k,v))
    url = _format_url(handler, core_name=core_name, extra=params + extra)
    return _http_request(url)

def import_status(handler, core_name=None, verbose=False):
    '''
    Submits an import command to the specified handler using specified options.
    This command can only be run if the minion is is configured with
    solr.type=master
    
    Param: str handler: The name of the data import handler.
    Param: str core (None): The core the handler belongs to.
    Param: bool verbose (False): Specifies verbose output
    Return: dict {'success':bool, 'data':dict, 'errors':list, 'warnings':list}

    CLI Example
    salt '*' solr.import_status /music/trackimport False
    '''
    if not __opts__['solr.type'] == 'master':
        errors = ['solr.import_status can only be accessed if the solr.type is "master"']
        return _get_return_dict(False, errors=errors)
    extra = ["command=status"]
    if verbose:
        extra.append("verbose=true")
    url = _format_url(handler,core_name=core_name,extra=extra)
    return _http_request(url)
