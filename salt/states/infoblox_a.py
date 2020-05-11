# -*- coding: utf-8 -*-
'''
Infoblox A record managment.

functions accept api_opts:

    api_verifyssl: verify SSL [default to True or pillar value]
    api_url: server to connect to [default to pillar value]
    api_username:  [default to pillar value]
    api_password:  [default to pillar value]
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def present(name=None, ipv4addr=None, data=None, ensure_data=True, **api_opts):
    '''
    Ensure infoblox A record.

    When you wish to update a hostname ensure `name` is set to the hostname
    of the current record. You can give a new name in the `data.name`.

    State example:

    .. code-block:: yaml

        infoblox_a.present:
            - name: example-ha-0.domain.com
            - data:
                name: example-ha-0.domain.com
                ipv4addr: 123.0.31.2
                view: Internal
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    if not data:
        data = {}
    if 'name' not in data:
        data.update({'name': name})
    if 'ipv4addr' not in data:
        data.update({'ipv4addr': ipv4addr})

    obj = __salt__['infoblox.get_a'](name=name, ipv4addr=ipv4addr, allow_array=False, **api_opts)
    if obj is None:
        # perhaps the user updated the name
        obj = __salt__['infoblox.get_a'](name=data['name'], ipv4addr=data['ipv4addr'], allow_array=False, **api_opts)
        if obj:
            # warn user that the data was updated and does not match
            ret['result'] = False
            ret['comment'] = '** please update the name: {0} to equal the updated data name {1}'.format(name, data['name'])
            return ret

    if obj:
        obj = obj[0]
        if not ensure_data:
            ret['result'] = True
            ret['comment'] = 'infoblox record already created (supplied fields not ensured to match)'
            return ret

        diff = __salt__['infoblox.diff_objects'](data, obj)
        if not diff:
            ret['result'] = True
            ret['comment'] = 'supplied fields already updated (note: removing fields might not update)'
            return ret

        if diff:
            ret['changes'] = {'diff': diff}
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'would attempt to update infoblox record'
                return ret
            ## TODO: perhaps need to review the output of new_obj
            new_obj = __salt__['infoblox.update_object'](obj['_ref'], data=data, **api_opts)
            ret['result'] = True
            ret['comment'] = 'infoblox record fields updated (note: removing fields might not update)'
            return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'would attempt to create infoblox record {0}'.format(data['name'])
        return ret

    new_obj_ref = __salt__['infoblox.create_a'](data=data, **api_opts)
    new_obj = __salt__['infoblox.get_a'](name=name, ipv4addr=ipv4addr, allow_array=False, **api_opts)

    ret['result'] = True
    ret['comment'] = 'infoblox record created'
    ret['changes'] = {'old': 'None', 'new': {'_ref': new_obj_ref, 'data': new_obj}}
    return ret


def absent(name=None, ipv4addr=None, **api_opts):
    '''
    Ensure infoblox A record is removed.

    State example:

    .. code-block:: yaml

        infoblox_a.absent:
            - name: example-ha-0.domain.com

        infoblox_a.absent:
            - name:
            - ipv4addr: 127.0.23.23
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    obj = __salt__['infoblox.get_a'](name=name, ipv4addr=ipv4addr, allow_array=False, **api_opts)

    if not obj:
        ret['result'] = True
        ret['comment'] = 'infoblox already removed'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['changes'] = {'old': obj, 'new': 'absent'}
        return ret

    if __salt__['infoblox.delete_a'](name=name, ipv4addr=ipv4addr, **api_opts):
        ret['result'] = True
        ret['changes'] = {'old': obj, 'new': 'absent'}
    return ret
