# -*- coding: utf-8 -*-
'''
Splunk Search State Module

.. versionadded:: 2015.5.0

This state is used to ensure presence of splunk searches.

.. code-block:: yaml

    server-warning-message:
      splunk_search.present:
        - name: This is the splunk search name
        - search: index=main sourcetype=
'''
from __future__ import absolute_import, unicode_literals, print_function


def __virtual__():
    '''
    Only load if the splunk_search module is available in __salt__
    '''
    return 'splunk_search' if 'splunk_search.get' in __salt__ else False


def present(name, profile="splunk", **kwargs):
    '''
    Ensure a search is present

    .. code-block:: yaml

        API Error Search:
          splunk_search.present:
            search: index=main sourcetype=blah
            template: alert_5min

    The following parameters are required:

    name
        This is the name of the search in splunk
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': ''
    }

    target = __salt__['splunk_search.get'](name, profile=profile)
    if target:
        if __opts__['test']:
            ret['comment'] = "Would update {0}".format(name)
            return ret
        # found a search... updating
        result = __salt__['splunk_search.update'](
            name, profile=profile, **kwargs
        )
        if not result:
            # no update
            ret['result'] = True
            ret['comment'] = "No changes"
        else:
            (newvalues, diffs) = result
            old_content = dict(target.content)
            old_changes = {}
            for x in newvalues:
                old_changes[x] = old_content.get(x, None)
            ret['result'] = True
            ret['changes']['diff'] = diffs
            ret['changes']['old'] = old_changes
            ret['changes']['new'] = newvalues
    else:
        if __opts__['test']:
            ret['comment'] = "Would create {0}".format(name)
            return ret
        # creating a new search
        result = __salt__['splunk_search.create'](
            name, profile=profile, **kwargs
        )
        if result:
            ret['result'] = True
            ret['changes']['old'] = False
            ret['changes']['new'] = kwargs
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0}'.format(name)
    return ret


def absent(name, profile="splunk"):
    '''
    Ensure a search is absent

    .. code-block:: yaml

        API Error Search:
          splunk_search.absent

    The following parameters are required:

    name
        This is the name of the search in splunk
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '{0} is absent.'.format(name)
    }

    target = __salt__['splunk_search.get'](name, profile=profile)
    if target:
        if __opts__['test']:
            ret = {}
            ret["name"] = name
            ret['comment'] = "Would delete {0}".format(name)
            ret['result'] = None
            return ret

        result = __salt__['splunk_search.delete'](name, profile=profile)
        if result:
            ret['comment'] = '{0} was deleted'.format(name)
        else:
            ret['comment'] = 'Failed to delete {0}'.format(name)
            ret['result'] = False
    return ret
