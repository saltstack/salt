# Import python libs
import time
import pdb

# Import salt libs
import salt.exceptions
import salt.utils.http

# Import third party libs
import requests
_has_datadog = True
try:
    import datadog
except ImportError:
    _has_datadog = False

# Define the module's virtual name
__virtualname__ = "datadog"

'''
An execution module that interacts with the Datadog API

Common parameters:

scope
    The scope of the request

api_key
    The datadog API key

app_key
    The datadog application key

Full argument reference is available on the Datadog API reference page
https://docs.datadoghq.com/api/
'''

def __virtual__():
    if _has_datadog:
        return "datadog"
    else:
        message = "Unable to import the python datadog module. Is it installed?"
        return False, message

def _configure_connection(api_key, app_key):
    options = {
        'api_key': api_key,
        'app_key': app_key
    }
    datadog.initialize(**options) 
    
def schedule_downtime(scope, api_key=None, app_key=None, monitor_id=None,
                      start=None, end=None, message=None, recurrence=None,
                      timezone=None, test=False):
    '''
    Schedule downtime for a scope of monitors.
    
    monitor_id
        The ID of the monitor
    start
        Start time in seconds since the epoch
    end
        End time in seconds since the epoch
    message
        A message to send in a notification for this downtime
    recurrence
        Repeat this downtime periodically
    timezone
        Specify the timezone

    CLI Example:

    .. code-block:: bash

        salt-call datadog.schdule_downtime "host:app2" stop=$(date --date='30 
        minutes' +%s)
    '''
    ret = {"result": False,
           "response": None,
           "comment": ""}
    if not scope:
        raise salt.exceptions.SaltInvocationError('scope must be specified')
    if api_key == None:
        raise salt.exceptions.SaltInvocationError('api_key must be specified')
    if app_key == None:
        raise salt.exceptions.SaltInvocationError('app_key must be specified')
    if test == True:
        ret["result"] = True
        ret["comment"] = "A schedule downtime API call would have been made." 
        return ret
    _configure_connection(api_key, app_key)
    
    # Schedule downtime
    try:
        response = datadog.api.Downtime.create(scope = scope, 
                                               monitor_id = monitor_id,
                                               start = start, 
                                               end = end, 
                                               message = message,
                                               recurrence = recurrence,
                                               timezone = timezone)
    except ValueError:
        comment = ("Unexpected exception in Datadog Schedule Downtime API "
                   "call. Are your keys correct?")
        ret["comment"] = comment
        return ret
 
    ret["response"] = response
    if "active" in response.keys():
        ret["result"] = True
        ret["comment"] = "Successfully scheduled downtime"
    return ret

def cancel_downtime(api_key=None, app_key=None, scope=None, id=None):
    '''
    Cancel a downtime by id or by scope. 
    
    Either scope or id is required.

    id
        The ID of the downtime

    CLI Example:

    .. code-block:: bash

        salt-call datadog.cancel_downtime scope='host:app01' api_key=<api_key>
        app_key=<app_key>`
    '''
    if api_key == None:
        raise salt.exceptions.SaltInvocationError('api_key must be specified')
    if app_key == None:
        raise salt.exceptions.SaltInvocationError('app_key must be specified')
    _configure_connection(api_key, app_key)

    ret = {"result": False,
           "response": None,
           "comment": ""}
    if id:
        response = datadog.api.Downtime.delete(id)
        ret["response"] = response
        if not response: # Then call has succeeded
            ret["result"] = True
            ret["comment"] = "Successfully cancelled downtime"
        return ret
    elif scope:
        params = { 
            "api_key": api_key,
            "application_key": app_key,
            "scope": scope
        }
        response = requests.post(
                    "https://app.datadoghq.com/api/v1/downtime/cancel/by_scope",
                    params=params
                    )
        if response.status_code == 200:
            ret["result"] = True
            ret["response"] = response.json()
            ret["comment"] = "Successfully cancelled downtime"
        else:
            ret["response"] = response.text
            ret["comment"] = "Status Code: {}".format(response.status_code)
        return ret
    else:
        raise salt.exceptions.SaltInvocationError('One of id or scope must be specified')

    return ret
