#!/usr/bin/env python

try:
    import simplejson as json
except ImportError:
    import json

import urllib2, subprocess, re, time

class ZabbixAPIException(Exception):
    pass

class ZabbixAPI(object):
    __auth = ''
    __id = 0
    _state = {}
    def __new__(cls, *args, **kw):
        if not cls._state.has_key(cls):
            cls._state[cls] = super(ZabbixAPI, cls).__new__(cls, *args, **kw)
        return cls._state[cls]
    def __init__(self, url, user, password):
        self.__url = url.rstrip('/') + '/api_jsonrpc.php'
        self.__user = user
        self.__password = password
        self._zabbix_api_object_list = ('Action', 'Alert', 'APIInfo', 'Application', 'DCheck', 'DHost', 'DRule',
                'DService', 'Event', 'Graph', 'Grahpitem', 'History', 'Host', 'Hostgroup', 'Image', 'Item',
                'Maintenance', 'Map', 'Mediatype', 'Proxy', 'Screen', 'Script', 'Template', 'Trigger', 'User',
                'Usergroup', 'Usermacro', 'Usermedia')
    def __getattr__(self, name):
        if name not in self._zabbix_api_object_list:
            raise ZabbixAPIException('No such API object: %s' % name)
        if not self.__dict__.has_key(name):
            self.__dict__[name] = ZabbixAPIObjectFactory(self, name)
        return self.__dict__[name]
    def login(self):
        user_info = {'user'     : self.__user,
                     'password' : self.__password}
        obj = self.json_obj('user.login', user_info)
        content = self.postRequest(obj)
        try:
            self.__auth = content['result']
        except KeyError, e:
            e = content['error']['data']
            raise ZabbixAPIException(e)
    def isLogin(self):
        return self.__auth != ''
    def __checkAuth__(self):
        if not self.isLogin():
            raise ZabbixAPIException("NOT logged in")
    def json_obj(self, method, params):
        obj = { 'jsonrpc' : '2.0',
                'method'  : method,
                'params'  : params,
                'auth'    : self.__auth,
                'id'      : self.__id}
        return json.dumps(obj)
    def postRequest(self, json_obj):
        headers = { 'Content-Type' : 'application/json-rpc',
                    'User-Agent'   : 'python/zabbix_api'}
        req = urllib2.Request(self.__url, json_obj, headers)
        opener = urllib2.urlopen(req)
        content = json.loads(opener.read())
        self.__id += 1
        return content

    '''
    /usr/local/zabbix/bin/zabbix_get is the default path to zabbix_get, it depends on the 'prefix' while install zabbix.
    plus, the ip(computer run this script) must be put into the conf of agent.
    '''
    @staticmethod
    def zabbixGet(ip, key):
        zabbix_get = subprocess.Popen('/usr/local/zabbix/bin/zabbix_get -s %s -k %s' % (ip, key), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, err = zabbix_get.communicate()
        if err:
            return 'ERROR'
        return result.strip()

    def createObject(self, object_name, *args, **kwargs):
        return object_name(self, *args, **kwargs)

    def getHostByHostid(self, hostids):
        if not isinstance(hostids,list):
            hostids = [hostids]
        return [dict['host'] for dict in self.host.get({'hostids':hostids,'output':'extend'})]


def checkAuth(func):
    def ret(self, *args):
        self.__checkAuth__()
        return func(self, args)
    return ret

def postJson(method_name):
    def decorator(func):
        def wrapper(self, params):
            try:
                content = self.postRequest(self.json_obj(method_name, params))
                return content['result']
            except KeyError, e:
                e = content['error']['data']
                raise ZabbixAPIException(e)
        return wrapper
    return decorator

def ZabbixAPIObjectMethod(func):
    def wrapper(self, method_name, params):
        try:
            content = self.postRequest(self.json_obj(method_name, params))
            return content['result']
        except KeyError, e:
            e = content['error']['data']
            raise ZabbixAPIException(e)
    return wrapper


class ZabbixAPIObjectFactory(object):
    def __init__(self, zapi, object_name=''):
        self.__zapi = zapi
        self.__object_name = object_name
    def __checkAuth__(self):
        self.__zapi.__checkAuth__()
    def postRequest(self, json_obj):
        return self.__zapi.postRequest(json_obj)
    def json_obj(self, method, param):
        return self.__zapi.json_obj(method, param)
    def __getattr__(self, method_name):
        def method(params):
            return self.proxyMethod('%s.%s' % (self.__object_name,method_name), params)
        return method
    def find(self, params, attr_name=None, to_create=False):
        filtered_list = []
        result = self.proxyMethod('%s.get' % self.__object_name, {'output':'extend','filter': params})
        if to_create and len(result) == 0:
            result = self.proxyMethod('%s.create' % self.__object_name, params)
            return result.values()[0]
        if attr_name is not None:
            for element in result:
                filtered_list.append(element[attr_name])
            return filtered_list
        else:
            return result


    @ZabbixAPIObjectMethod
    @checkAuth
    def proxyMethod(self, method_name, params):
        pass

def testCase():
    zapi = ZabbixAPI(url='http://127.0.0.1/zabbix', user='admin', password='zabbix')
    zapi.login()
    #print zapi.Graph.find({'graphid':'49931'}, attr_name='graphid')[0]
    #hostid = zapi.Host.find({'ip':ip}, attr_name='hostid')[0]
    print zapi.Host.exists({'filter':{'host':'BJBSJ-Zabbix-Proxy-82-225'}})
    host = zapi.createObject(Host, 'HostToCreate')
    item = host.getItem('444107')
    zapi.host.get({'hostids':['16913','17411'],'output':'extend'})
    group = zapi.createObject(Hostgroup, '926')
    print zapi.getHostByHostid('16913')

if __name__ == '__main__':
    testCase()
