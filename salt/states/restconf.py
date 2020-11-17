"""
State module for restconf Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.compat  # noqa: F401
import json  # noqa: F401
from salt.utils.odict import OrderedDict  # noqa: F401
from deepdiff import DeepDiff


def __virtual__():
    if "restconf.set_data" in __salt__:  # noqa: F821
        return True
    return (False, "restconf module could not be loaded")


def config_manage(name, uri, method, config, init_uri=None, init_method='PATCH'):
    """
    Ensure a specific value exists at a given path
    :param name: The name for this rule
    :type  name: ``str``
    :param uri: The restconf uri to set / get config
    :type  uri: ``str``
    :param method: rest method to use eg GET, PUT, POST, PATCH, DELETE
    :type method: ``str``
    :param config: The new value at the given path
    :type  config: ``dict``
    :param init_uri: Alternative URI incase the URI doesnt exist on first pass
    :type init_uri: ``str``
    :param init_method: Method to use on alternative URI when setting config, default: PATCH
    :type init_method: ``str``
    Examples:
    .. code-block:: yaml
        random name here:
          restconf.config_manage:
            - name: random_name_here
            - uri: restconf/data/Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F3
            - config:
                Cisco-IOS-XE-native:GigabitEthernet:
                    description:
                        harro
                    name:
                        1/0/3
    """
    # TODO: add template function so that config var does not need to be passed
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    found_working_uri = False
    uri_used = ''
    existing_raw = __salt__["restconf.get_data"](uri)  # noqa: F821
    request_uri = ''
    request_method = ''
    # TODO: this could probaby be a loop
    if existing_raw['status'] in [200]:
        existing = existing_raw['dict']
        found_working_uri = True
        uri_used = 'Primary'
        request_uri = uri
        request_method = method

    if not found_working_uri:
        existing_raw_init = __salt__["restconf.get_data"](init_uri)  # noqa: F821
        if existing_raw_init['status'] in [200]:
            existing = existing_raw_init['dict']
            found_working_uri = True
            uri_used = 'init'
            request_uri = init_uri
            request_method = init_method

    if not found_working_uri:
        ret["result"] = False
        ret["comment"] = 'restconf could not find a working URI to get initial config'
        return ret
    # TODO: END

    dict_config = json.loads(json.dumps(config))  # convert from orderedDict to Dict (which is now ordered by default in python3.8)

    if existing == dict_config:
        ret["result"] = True
        ret["comment"] = "Config is already set"

    elif __opts__["test"] is True:  # noqa: F821
        ret["result"] = None
        ret["comment"] = "Config will be added"
        diff = _restDiff(existing, dict_config)
        ret["changes"]["new"] = diff.added()
        ret["changes"]["removed"] = diff.removed()
        ret["changes"]["changed"] = diff.changed()

    else:
        resp = __salt__["restconf.set_data"](request_uri, request_method, dict_config)  # noqa: F821
        # Success
        if resp['status'] in [201, 200, 204]:
            ret["result"] = True
            ret["comment"] = "Successfully added config"
            diff = _restDiff(existing, dict_config)
            ret["changes"]["new"] = diff.added()
            ret["changes"]["removed"] = diff.removed()
            ret["changes"]["changed"] = diff.changed()
            if method == 'PATCH':
                ret["changes"]["removed"] = None
        # full failure
        else:
            ret["result"] = False
            if 'dict' in resp:
                why = resp['dict']
            elif 'body' in resp:
                why = resp['body']
            else:
                why = None
            ret["comment"] = "failed to add / modify config. API Statuscode: {s}, API Response: {w}, URI:{u}".format(w=why, s=resp['status'], u=uri_used)
            print("post_content: {b}".format(b=json.dumps(dict_config)))

    return ret


class _restDiff(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict = current_dict
        self.past_dict = past_dict
        self.diff = DeepDiff(current_dict, past_dict)
        print("DeepDiff:")
        print(self.diff)
        self.diff_pretty = self.diff.pretty()

    def added(self):
        # TODO: Potential for new adds to get missed here.
        # need to dig into deepdiff more
        if 'dictionary_item_added' in self.diff.keys():
            return str(self.diff['dictionary_item_added'])
        return None

    def removed(self):
        if 'dictionary_item_removed' in self.diff.keys():
            return str(self.diff['dictionary_item_removed'])
        return None

    def changed(self):
        if 'values_changed' in self.diff.keys():
            return str(self.diff['values_changed'])
        return None

    def unchanged(self):
        return None  # TODO: not implemented
