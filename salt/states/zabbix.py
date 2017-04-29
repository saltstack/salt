# -*- coding: utf-8 -*-
'''
zabbix module for salt
============================

The user module is used to config zabbix

'''

# Import python libs
import logging
import sys

# Import salt libs
import salt.utils

from zapi import *

log = logging.getLogger(__name__)

zapi = ZabbixAPI(url='{{web_api}}', user='{{web_user}}', password='{{web_pass}}')
zapi.login()


#{% raw %}
def _hostgroup(name):
    if not zapi.Hostgroup.find({"name":name}):
        zapi.Hostgroup.create({"name":name})

    if not zapi.Hostgroup.find({"name":name}):
        return False
    else:
        return True


def hostgroup(name):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Hostgroup {0} set to create'.format(name)
        return ret

    ret['result'] = _hostgroup(name)
    ret['comment'] = 'Create Hostgroup {0}'.format(name)

    return ret


def _host(name, hostgroups, interface="127.0.0.1", templates=None):
    for hostgroup in hostgroups:
        _hostgroup(hostgroup)
    hgs = zapi.Hostgroup.find({"name":hostgroups})
    hgids = map(lambda x: {'groupid': x['groupid']}, hgs)

    tpids = []
    if templates:
        tps = zapi.Template.find({"name":templates})
        tpids = map(lambda x: {'templateid': x['templateid']}, tps)

    if not zapi.Host.find({"name":name}):
        zapi.Host.create({
            "host":name,
            "groups":hgids,
            "templates":tpids,
            "interfaces":[{"type":"1","main":"1","useip":"1",
                        "ip":interface,"dns":"","port":"10050"}]
            })
    else:
        zapi.Host.update({
            "hostid":zapi.Host.find({"name":name})[0]["hostid"],
            "groups":hgids,
            "templates":tpids,
#            "interfaces":[{"type":"1","main":"1","useip":"1",
#                        "ip":interface,"dns":"","port":"10050"}]
            })

    if not zapi.Host.find({"name":name}):
        return False
    else:
        return True


def host(name, hostgroups, interface="127.0.0.1", templates=None):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Host {0} set to create'.format(name)
        return ret

    ret['result'] = _host(name, hostgroups, interface, templates)
    ret['comment'] = 'Create Host {0}'.format(name)

    return ret


def _template(name):
    if not zapi.Template.find({"host":name}):
        zapi.Template.create({"host":name, "groups":{"groupid":"1"}})

    if not zapi.Template.find({"host":name}):
        return False
    else:
        return True


def _application(name, template):
    _template(template)

    tp = zapi.Template.find({"name":template})
    if not tp:
        return False
    tpid = tp[0]["templateid"]

    if not zapi.Application.find({"name":name, "hostid":tpid}):
        zapi.Application.create({"name":name, "hostid":tpid})

    if not zapi.Application.find({"name":name, "hostid":tpid}):
        return False
    else:
        return True


def application(name):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Application {0} set to create'.format(name)
        return ret

    ret['result'] = _application(name, name)
    ret['comment'] = 'Create Application {0}'.format(name)

    return ret


def _item(name, key, template, application, itemtype=0, valuetype=0, datatype=0, delta=0, delay=60):
    _application(application, template)

    tp = zapi.Template.find({"name":template})
    if not tp:
        return False
    tpid = tp[0]["templateid"]

    app = zapi.Application.find({"name":application, "hostid":tpid})
    if not app:
        return False
    appid = app[0]["applicationid"]

    if not zapi.Item.find({"name":name, "key_":key, "hostid":tpid, "application":appid}):
        zapi.Item.create({"name":name, "key_":key, "hostid":tpid, "applications":[appid], \
                "type":itemtype, "value_type":valuetype, "data_type":datatype, \
                "delta":delta, "delay":delay})
    else:
        itemid = zapi.Item.find({"name":name, "key_":key, "hostid":tpid, "application":appid})[0]["itemid"]
        zapi.Item.update({"itemid":itemid, \
                "type":itemtype, "value_type":valuetype, "data_type":datatype, \
                "delta":delta, "delay":delay})

    if not zapi.Item.find({"name":name, "key_":key, "hostid":tpid, "application":appid}):
        return False
    else:
        return True


def item(name, key, application, itemtype=0, valuetype=0, datatype=0, delta=0, delay=60):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Item {0} set to create'.format(name)
        return ret

    ret['result'] = _item(name, key, application, application, itemtype, valuetype, datatype, delta, delay)
    ret['comment'] = 'Create Item {0}'.format(name)

    return ret

#  code for generate color array
#  color = ["00", "55", "aa", "ff"]
#  for i in range(64):
#      a0 = i & 3
#      a1 = (i >> 2) & 3
#      a2 = (i >> 4) & 3
#      b0 = (a0 & 1) + (a1 & 2)
#      b1 = ((a0 & 2) >> 1) + ((a2 & 1) << 1)
#      b2 = (a1 & 1) + (a2 & 2)
#      print "%s%s%s" % (color[b0], color[b1], color[b2])

color = [
    "000000",
    "550000",
    "005500",
    "555500",
    "000055",
    "550055",
    "005555",
    "555555",
    "aa0000",
    "ff0000",
    "aa5500",
    "ff5500",
    "aa0055",
    "ff0055",
    "aa5555",
    "ff5555",
    "00aa00",
    "55aa00",
    "00ff00",
    "55ff00",
    "00aa55",
    "55aa55",
    "00ff55",
    "55ff55",
    "aaaa00",
    "ffaa00",
    "aaff00",
    "ffff00",
    "aaaa55",
    "ffaa55",
    "aaff55",
    "ffff55",
    "0000aa",
    "5500aa",
    "0055aa",
    "5555aa",
    "0000ff",
    "5500ff",
    "0055ff",
    "5555ff",
    "aa00aa",
    "ff00aa",
    "aa55aa",
    "ff55aa",
    "aa00ff",
    "ff00ff",
    "aa55ff",
    "ff55ff",
    "00aaaa",
    "55aaaa",
    "00ffaa",
    "55ffaa",
    "00aaff",
    "55aaff",
    "00ffff",
    "55ffff",
    "aaaaaa",
    "ffaaaa",
    "aaffaa",
    "ffffaa",
    "aaaaff",
    "ffaaff",
    "aaffff",
    "ffffff"
]

def _graph(name, width, height, template, application, keys, graphtype=0, ymax_type=0, yaxismax=0, ymin_type=0, yaxismin=0):
    _template(template)

    tp = zapi.Template.find({"name":template})
    if not tp:
        return False
    tpid = tp[0]["templateid"]

    app = zapi.Application.find({"name":application, "hostid":tpid})
    if not app:
        return False
    appid = app[0]["applicationid"]

    gitems = []
    for key in keys:
        if not zapi.Item.find({"key_":key, "hostid":tpid, "application":appid}):
            return False
        gitems.append({"itemid":zapi.Item.find({"key_":key, "hostid":tpid, "application":appid})[0]["itemid"], "color":color[len(gitems)]})

    if not zapi.Graph.find({"name":name}):
        zapi.Graph.create({"name":name, "width":width, "height":height, \
                "graphtype":graphtype, "ymax_type":ymax_type, "yaxismax":yaxismax, \
                "ymin_type":ymin_type, "yaxismin":yaxismin, \
                "gitems":gitems})
    else:
        graphid = zapi.Graph.find({"name":name})[0]["graphid"]
        zapi.Graph.update({"graphid":graphid, "width":width, "height":height, \
                "graphtype":graphtype, "ymax_type":ymax_type, "yaxismax":yaxismax, \
                "ymin_type":ymin_type, "yaxismin":yaxismin, \
                "gitems":gitems})

    if not zapi.Graph.find({"name":name}):
        return False
    else:
        return True


def graph(name, width, height, application, keys, graphtype=0, ymax_type=0, yaxismax=0, ymin_type=0, yaxismin=0):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Graph {0} set to create'.format(name)
        return ret

    ret['result'] = _graph(name, width, height, application, application, keys, graphtype, ymax_type, yaxismax, ymin_type, yaxismin)
    ret['comment'] = 'Create Graph {0}'.format(name)

    return ret


def _usergroup(name, debug_mode=0, gui_access=0, status=0):
    if not zapi.Usergroup.find({"name":name}):
        zapi.Usergroup.create({"name":name, "debug_mode":debug_mode, \
                "gui_access":gui_access, "users_status":status})
    else:
        ugid = zapi.Usergroup.find({"name":name})[0]["usrgrpid"]
        zapi.Usergroup.update({"usrgrpid":ugid, "debug_mode":debug_mode, \
                "gui_access":gui_access, "users_status":status})

    if not zapi.Usergroup.find({"name":name}):
        return False
    else:
        return True


def usergroup(name, debug_mode=0, gui_access=0, status=0):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Usergroup {0} set to create'.format(name)
        return ret

    ret['result'] = _usergroup(name, debug_mode, gui_access, status)
    ret['comment'] = 'Create Usergroup {0}'.format(name)

    return ret


def _user(name, lastname, firstname, passwd, usergroups, sendto, usertype="3", mediatype="Send Email", period="1-7,00:00-24:00", severity="63"):
    for usergroup in usergroups:
        _usergroup(usergroup)
    ugs = zapi.Usergroup.find({"name":usergroups})
    ugids = map(lambda x: {'usrgrpid': x['usrgrpid']}, ugs)

    if not zapi.User.find({"alias":name}):
        zapi.User.create({"alias":name, "name":lastname, "surname":firstname, "passwd":passwd, "type":usertype, "usrgrps":ugids})
    else:
        uid = zapi.User.find({"alias":name})[0]["userid"]
        zapi.User.update({"userid":uid, "name":lastname, "surname":firstname, "passwd":passwd, "type":usertype, "usrgrps":ugids})

    _mediatype(mediatype, "0")
    _mediatype("Send Cloud", "1", "sendcloud")

    _media(name, mediatype, sendto, 0, period, severity)
    _media(name, "Send Cloud", sendto, 0, period, severity)

    if not zapi.User.find({"alias":name}):
        return False
    else:
        return True


def user(name, lastname, firstname, passwd, usergroups, sendto, usertype="3", mediatype="Send Email", period="1-7,00:00-24:00", severity="63"):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'User {0} set to create'.format(name)
        return ret

    ret['result'] = _user(name, lastname, firstname, passwd, usergroups, sendto, usertype, mediatype, period, severity)
    ret['comment'] = 'Create User {0}'.format(name)

    return ret


def _trigger(name, expression, priority=1, status=0):
    if not zapi.Trigger.find({"description":name}):
        zapi.Trigger.create({"description":name, "expression":expression, "priority":priority, "status":status})
    else:
        triggerid = zapi.Trigger.find({"description":name})[0]["triggerid"]
        zapi.Trigger.update({"triggerid":triggerid, \
                "expression":expression, "priority":priority, "status":status})

    if not zapi.Trigger.find({"description":name}):
        return False
    else:
        return True


def trigger(name, expression, priority=1, status=0):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Trigger {0} set to create'.format(name)
        return ret

    expression = expression.replace('\\', '')
    ret['result'] = _trigger(name, expression, priority, status)
    ret['comment'] = 'Create Trigger {0}'.format(name)

    return ret


def _script(name, command, execute_on=1):
    if not zapi.Script.find({"name":name}):
        zapi.Script.create({"name":name, "command":command, "execute_on":execute_on})
    else:
        scriptid = zapi.Script.find({"name":name})[0]["scriptid"]
        zapi.Script.update({"scriptid":scriptid, \
                "command":command, "execute_on":execute_on})

    if not zapi.Script.find({"name":name}):
        return False
    else:
        return True


def script(name, command, execute_on=1):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Script {0} set to create'.format(name)
        return ret

    ret['result'] = _script(name, command, execute_on=1)
    ret['comment'] = 'Create Script {0}'.format(name)

    return ret


def _mediatype(name, mtype, script=""):
    if int(mtype) != 0 and int(mtype) != 1:
        return False

    if not zapi.Mediatype.find({"description":name}):
        if int(mtype) == 0:
            zapi.Mediatype.create({"description":name,"type":mtype, \
                    "smtp_email":"zabbix@localhost", "smtp_helo":"localhost", \
                    "smtp_server":"localhost"})
        else:
            zapi.Mediatype.create({"description":name,"type":mtype, "exec_path":script})
    else:
        mediatypeid = zapi.Mediatype.find({"description":name})[0]["mediatypeid"]
        if int(mtype) == 0:
            zapi.Mediatype.update({"mediatypeid":mediatypeid, "type":mtype, \
                    "smtp_email":"zabbix@localhost", "smtp_helo":"localhost", \
                    "smtp_server":"localhost"})
        else:
            zapi.Mediatype.update({"mediatypeid":mediatypeid, \
                    "type":mtype, "exec_path":script})

    if not zapi.Mediatype.find({"description":name}):
        return False
    else:
        return True


def _media(user, mediatype, sendto, active=0, period="1-7,00:00-24:00", severity="63"):
    u = zapi.User.find({"alias":user})
    if not u:
        return False
    uid = u[0]["userid"]

    mt = zapi.Mediatype.find({"description":mediatype})
    if not mt:
        return False
    mtid = mt[0]["mediatypeid"]

    if not zapi.Usermedia.find({"userid":uid, "mediatypeid":mtid}):
        zapi.User.addmedia({"users":[{"userid":uid}], \
            "medias":{"mediatypeid":mtid, "sendto":sendto, "active":active, "period":period, "severity":severity}})
    else:
        zapi.User.updatemedia({"users":[{"userid":uid}], \
            "medias":{"mediatypeid":mtid, "sendto":sendto, "active":active, "period":period, "severity":severity}})

    if not zapi.Usermedia.find({"mediatypeid":mtid, "userid":uid}):
        return False
    else:
        return True


def _action(name, trigger_filter, notify_usergroup, mediatype="Send Email", status=0, esc_period=60, \
        def_shortdata="{HOST.HOST} {TRIGGER.NAME}: {TRIGGER.STATUS}", \
        def_longdata="Latest value: {{HOST.HOST}:{ITEM.KEY}.last(0)}\r\nMAX for 15 minutes: {{HOST.HOST}:{ITEM.KEY}.max(900)}\r\nMIN for 15 minutes: {{HOST.HOST}:{ITEM.KEY}.min(900)}\r\n\r\n{TRIGGER.URL}"):
    ug = zapi.Usergroup.find({"name":notify_usergroup})
    if not ug:
        return False
    ugid = ug[0]["usrgrpid"]

    _mediatype(mediatype, "0")
    _mediatype("Send Cloud", "1", "sendcloud")

    mt = zapi.Mediatype.find({"description":"Send Cloud"})
    if not mt:
        return False
    mtid = mt[0]["mediatypeid"]

    if not zapi.Action.find({"name":name}):
        zapi.Action.create({"name":name, "eventsource":"0", "evaltype":"0", "status":status, \
                "esc_period":esc_period, "def_shortdata":def_shortdata, "def_longdata":def_longdata, \
                "conditions":[{"conditiontype": 3, "operator": 2, "value": trigger_filter}], \
                "operations":[{"operationtype": 0, "esc_period": 0, "esc_step_from": 1, "esc_step_to": 1, \
                                 "evaltype": 0, "opmessage_grp": [{"usrgrpid": ugid}], \
                                 "opmessage": {"default_msg": 1, "mediatypeid":mtid}}]})
    else:
        actionid = zapi.Action.find({"name":name})[0]["actionid"]
        zapi.Action.update({"actionid":actionid, "eventsource":"0", "evaltype":"0", "status":status, \
                "esc_period":esc_period, "def_shortdata":def_shortdata, "def_longdata":def_longdata, \
                "conditions":[{"conditiontype": 3, "operator": 2, "value": trigger_filter}], \
                "operations":[{"operationtype": 0, "esc_period": 0, "esc_step_from": 1, "esc_step_to": 1, \
                                 "evaltype": 0, "opmessage_grp": [{"usrgrpid": ugid}], \
                                 "opmessage": {"default_msg": 1, "mediatypeid":mtid}}]})

    if not zapi.Action.find({"name":name}):
        return False
    else:
        return True


def action(name, trigger_filter, notify_usergroup, mediatype="Send Email", status=0, esc_period=60, \
        def_shortdata="{HOST.HOST} {TRIGGER.NAME}: {TRIGGER.STATUS}", \
        def_longdata="Latest value: {{HOST.HOST}:{ITEM.KEY}.last(0)}\r\nMAX for 15 minutes: {{HOST.HOST}:{ITEM.KEY}.max(900)}\r\nMIN for 15 minutes: {{HOST.HOST}:{ITEM.KEY}.min(900)}\r\n\r\n{TRIGGER.URL}"):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Action {0} set to create'.format(name)
        return ret

    ret['result'] = _action(name, trigger_filter, notify_usergroup, mediatype, status, esc_period, def_shortdata, def_longdata)
    ret['comment'] = 'Create Action {0}'.format(name)

    return ret
#{% endraw %}
