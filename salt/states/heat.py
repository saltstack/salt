# -*- coding: utf-8 -*-
'''
Management of Heat
==================

.. versionadded:: 2017.7.0

:depends:   - heat Python module
:configuration: See :py:mod:`salt.modules.heat` for setup instructions.

The heat module is used to create, show, list and delete Heat staks.
Stack can be set as either absent or deploy.

.. code-block:: yaml

  heat.deployed:
    - name:
    - template: #Required
    - enviroment:
    - params: {}
    - poll: 5
    - rollback: False
    - timeout: 60

  heat.absent:
    - name:
    - poll: 5

mysql:
  heat.deployed:
    - template: salt://templates/mysql.heat.yaml
    - params:
      image: Debian 7
    - rollback: True

'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.exceptions
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six

# pylint: disable=import-error
HAS_OSLO = False
try:
    from oslo_serialization import jsonutils
    HAS_OSLO = True
except ImportError:
    pass

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the mysql module is in __salt__
    '''
    if HAS_OSLO:
        return 'heat'
    return (False, 'The heat state module cannot be loaded: '
                   'the oslo_serialization python library is not available.')


def _parse_template(tmpl_str):
    '''
    Parsing template
    '''
    tmpl_str = tmpl_str.strip()
    if tmpl_str.startswith('{'):
        tpl = salt.utils.json.loads(tmpl_str)
    else:
        try:
            tpl = salt.utils.yaml.safe_load(tmpl_str)
        except salt.utils.yaml.YAMLError as exc:
            raise ValueError(six.text_type(exc))
        else:
            if tpl is None:
                tpl = {}
    if not ('HeatTemplateFormatVersion' in tpl
            or 'heat_template_version' in tpl
            or 'AWSTemplateFormatVersion' in tpl):
        raise ValueError(('Template format version not found.'))
    return tpl


def deployed(name, template=None, enviroment=None, params=None, poll=5,
             rollback=False, timeout=60, update=False, profile=None,
             **connection_args):
    '''
    Deploy stack with the specified properties

    name
        The name of the stack

    template
        File of template

    enviroment
        File of enviroment

    params
        Parameter dict used to create the stack

    poll
        Poll(in sec.) and report events until stack complete

    rollback
        Enable rollback on create failure

    timeout
        Stack creation timeout in minutes

    profile
        Profile to use

    '''
    log.debug('Deployed with(' +
              '{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}, {9})'
              .format(name, template, enviroment, params, poll, rollback,
                      timeout, update, profile, connection_args))
    ret = {'name': None,
           'comment': '',
           'changes': {},
           'result': True}

    if not name:
        ret['result'] = False
        ret['comment'] = 'Name ist not valid'
        return ret

    ret['name'] = name,

    existing_stack = __salt__['heat.show_stack'](name, profile=profile)

    if existing_stack['result'] and not update:
        ret['comment'] = 'Stack {0} is deployed'.format(name)
        return ret
    if existing_stack['result'] and update:
        if template:
            template_tmp_file = salt.utils.files.mkstemp()
            tsfn, source_sum, comment_ = __salt__['file.get_managed'](
                name=template_tmp_file,
                template=None,
                source=template,
                source_hash=None,
                user=None,
                group=None,
                mode=None,
                saltenv='base',
                context=None,
                defaults=None,
                skip_verify=False,
                kwargs=None)

            template_manage_result = __salt__['file.manage_file'](
                name=template_tmp_file,
                sfn=tsfn,
                ret=None,
                source=template,
                source_sum=source_sum,
                user=None,
                group=None,
                mode=None,
                saltenv='base',
                backup=None,
                makedirs=True,
                template=None,
                show_changes=False,
                contents=None,
                dir_mode=None)

            if (template_manage_result['result']) or \
                    ((__opts__['test']) and (template_manage_result['result'] is not False)):
                with salt.utils.files.fopen(template_tmp_file, 'r') as tfp_:
                    tpl = salt.utils.stringutils.to_unicode(tfp_.read())
                    salt.utils.files.safe_rm(template_tmp_file)
                    try:
                        template_parse = _parse_template(tpl)
                        if 'heat_template_version' in template_parse:
                            template_new = salt.utils.yaml.safe_dump(template_parse)
                        else:
                            template_new = jsonutils.dumps(template_parse, indent=2, ensure_ascii=False)
                        salt.utils.files.safe_rm(template_tmp_file)
                    except ValueError as ex:
                        ret['result'] = False
                        ret['comment'] = 'Error parsing template {0}'.format(ex)
            else:
                ret['result'] = False
                ret['comment'] = 'Can not open template: {0} {1}'.format(template, comment_)
        else:
            ret['result'] = False
            ret['comment'] = 'Can not open template'
        if ret['result'] is True:
            template_stack = __salt__['heat.template_stack'](name=name, profile=profile)
            if not template_stack['result']:
                ret['result'] = False
                ret['comment'] = template_stack['comment']
        if ret['result'] is False:
            return ret

        try:
            checksum_template = __salt__['hashutil.digest'](template_new)
            checksum_stack = __salt__['hashutil.digest'](template_stack['template'])
        except salt.exceptions.CommandExecutionError as cmdexc:
            ret['result'] = False
            ret['comment'] = '{0}'.format(cmdexc)

        if ret['result'] is True:
            if checksum_template == checksum_stack:
                if __opts__['test']:
                    ret['result'] = True
                    ret['comment'] = 'Stack {0} is deployed'.format(name)
                    return ret
                else:
                    ret['result'] = False
                    ret['comment'] = 'Templates have same checksum: {0} {1}'\
                        .format(checksum_template, checksum_stack)
        if ret['result'] is False:
            return ret
        if __opts__['test']:
            stack = {
                'result': None,
                'comment': 'Stack {0} is set to be updated'.format(name)
            }
        else:
            stack = __salt__['heat.update_stack'](name=name,
                                                  template_file=template,
                                                  enviroment=enviroment,
                                                  parameters=params, poll=poll,
                                                  rollback=rollback,
                                                  timeout=timeout,
                                                  profile=profile)
            ret['changes']['stack_name'] = name
            ret['changes']['comment'] = 'Update stack'
    else:
        if __opts__['test']:
            stack = {
                'result': None,
                'comment': 'Stack {0} is set to be created'.format(name)
            }
        else:
            stack = __salt__['heat.create_stack'](name=name,
                                                  template_file=template,
                                                  enviroment=enviroment,
                                                  parameters=params, poll=poll,
                                                  rollback=rollback,
                                                  timeout=timeout,
                                                  profile=profile)
            ret['changes']['stack_name'] = name
            ret['changes']['comment'] = 'Create stack'
    ret['result'] = stack['result']
    ret['comment'] = stack['comment']

    return ret


def absent(name, poll=5, timeout=60, profile=None):
    '''
    Ensure that the named stack is absent

    name
        The name of the stack to remove

    poll
        Poll(in sec.) and report events until stack complete

    timeout
        Stack creation timeout in minutes

    profile
        Profile to use

    '''
    log.debug('Absent with(' +
              '{0}, {1} {2})'.format(name, poll, profile))
    ret = {'name': None,
           'comment': '',
           'changes': {},
           'result': True}
    if not name:
        ret['result'] = False
        ret['comment'] = 'Name ist not valid'
        return ret

    ret['name'] = name,

    existing_stack = __salt__['heat.show_stack'](name, profile=profile)

    if not existing_stack['result']:
        ret['result'] = True
        ret['comment'] = 'Stack not exist'
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Stack {0} is set to be removed'.format(name)
        return ret

    stack = __salt__['heat.delete_stack'](name=name, poll=poll,
                                          timeout=timeout, profile=profile)

    ret['result'] = stack['result']
    ret['comment'] = stack['comment']
    ret['changes']['stack_name'] = name
    ret['changes']['comment'] = 'Delete stack'
    return ret
