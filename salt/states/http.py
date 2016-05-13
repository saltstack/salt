# -*- coding: utf-8 -*-
'''
HTTP monitoring states

Perform an HTTP query and statefully return the result

.. versionadded:: 2015.5.0
'''

# Import python libs
from __future__ import absolute_import
import re

__monitor__ = [
        'query',
        ]


def query(name, match=None, match_type='string', status=None, **kwargs):
    '''
    Perform an HTTP query and statefully return the result

    .. versionadded:: 2015.5.0

    name
        The name of the query.

    match
        Specifies a pattern to look for in the return text. By default, this will
        perform a string comparison of looking for the value of match in the return
        text.

    match_type
        Specifies the type of pattern matching to use. Default is ``string``, but
        can also be set to ``pcre`` to use regular expression matching if a more
        complex pattern matching is required.

        .. note::

            Despite the name of ``match_type`` for this argument, this setting
            actually uses Python's ``re.search()`` function rather than Python's
            ``re.match()`` function.

    status
        The status code for a URL for which to be checked. Can be used instead of
        or in addition to the ``match`` setting.

    If both ``match`` and ``status`` options are set, both settings will be checked.
    However, note that if only one option is ``True`` and the other is ``False``,
    then ``False`` will be returned. If this case is reached, the comments in the
    return data will contain troubleshooting information.

    For more information about the ``http.query`` state, refer to the
    :ref:`HTTP Tutorial <tutorial-http>`.

    .. code-block:: yaml

        query_example:
          http.query:
            - name: 'http://example.com/'
            - status: '200'

    '''
    # Monitoring state, but changes may be made over HTTP
    ret = {'name': name,
           'result': None,
           'comment': '',
           'changes': {},
           'data': {}}  # Data field for monitoring state

    if match is None and status is None:
        ret['result'] = False
        ret['comment'] += (
            ' Either match text (match) or a status code (status) is required.'
        )
        return ret

    if 'decode' not in kwargs:
        kwargs['decode'] = False
    kwargs['text'] = True
    kwargs['status'] = True
    if __opts__['test']:
        kwargs['test'] = True

    data = __salt__['http.query'](name, **kwargs)

    if match is not None:
        if match_type == 'string':
            if match in data.get('text', ''):
                ret['result'] = True
                ret['comment'] += ' Match text "{0}" was found.'.format(match)
            else:
                ret['result'] = False
                ret['comment'] += ' Match text "{0}" was not found.'.format(match)
        elif match_type == 'pcre':
            if re.search(match, data['text']):
                ret['result'] = True
                ret['comment'] += ' Match pattern "{0}" was found.'.format(match)
            else:
                ret['result'] = False
                ret['comment'] += ' Match pattern "{0}" was not found.'.format(match)

    if status is not None:
        if data.get('status', '') == status:
            ret['comment'] += 'Status {0} was found, as specified.'.format(status)
            if ret['result'] is None:
                ret['result'] = True
        else:
            ret['comment'] += 'Status {0} was not found, as specified.'.format(status)
            ret['result'] = False

    if __opts__['test'] and ret['result'] is True:
        ret['result'] = None
        ret['comment'] += ' (TEST MODE'
        if 'test_url' in kwargs:
            ret['comment'] += ', TEST URL WAS: {0}'.format(kwargs['test_url'])
        ret['comment'] += ')'

    ret['data'] = data
    return ret
