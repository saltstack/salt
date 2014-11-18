# -*- coding: utf-8 -*-
'''
Utils for making various web calls. Primarily designed for REST, SOAP, webhooks
and the like, but also useful for basic HTTP testing.
'''
from __future__ import absolute_import

# Import python libs
import pprint
import os.path
import json
import logging
import salt.utils.six.moves.http_cookiejar  # pylint: disable=E0611
from salt._compat import ElementTree as ET

# Import salt libs
import salt.utils
import salt.utils.xmlutil as xml
import salt.loader
import salt.config
from salt.template import compile_template
from salt import syspaths

# Import 3rd party libs
import requests
import msgpack

log = logging.getLogger(__name__)
JARFILE = os.path.join(syspaths.CACHE_DIR, 'cookies.txt')
SESSIONJARFILE = os.path.join(syspaths.CACHE_DIR, 'cookies.session.p')


def query(url,
          method='GET',
          params=None,
          data=None,
          data_file=None,
          header_dict=None,
          header_list=None,
          header_file=None,
          username=None,
          password=None,
          decode=True,
          decode_type='auto',
          status=False,
          headers=False,
          text=False,
          cookies=None,
          cookie_jar=JARFILE,
          cookie_format='lwp',
          persist_session=False,
          session_cookie_jar=SESSIONJARFILE,
          data_render=False,
          data_renderer=None,
          header_render=False,
          header_renderer=None,
          template_dict=None,
          test=False,
          test_url=None,
          node='minion',
          opts=None,
          **kwargs):
    '''
    Query a resource, and decode the return data
    '''
    ret = {}

    requests_log = logging.getLogger('requests')
    requests_log.setLevel(logging.WARNING)

    if opts is None:
        if node == 'master':
            opts = salt.config.master_config('/etc/salt/master')
        elif node == 'minion':
            opts = salt.config.master_config('/etc/salt/minion')
        else:
            opts = {}

    if data_file is not None:
        data = _render(
            data_file, data_render, data_renderer, template_dict, opts
        )
    log.trace('POST Data: {0}'.format(pprint.pformat(data)))

    if header_file is not None:
        header_tpl = _render(
            header_file, header_render, header_renderer, template_dict, opts
        )
        if isinstance(header_tpl, dict):
            header_dict = header_tpl
        else:
            header_list = header_tpl.splitlines()

    if header_dict is None:
        header_dict = {}

    if header_list is None:
        header_list = []

    if persist_session is True:
        # TODO: This is hackish; it will overwrite the session cookie jar with
        # all cookies from this one connection, rather than behaving like a
        # proper cookie jar. Unfortunately, since session cookies do not
        # contain expirations, they can't be stored in a proper cookie jar.
        if os.path.isfile(session_cookie_jar):
            with salt.utils.fopen(session_cookie_jar, 'r') as fh_:
                session_cookies = msgpack.load(fh_)
            if isinstance(session_cookies, dict):
                header_dict.update(session_cookies)
        else:
            with salt.utils.fopen(session_cookie_jar, 'w') as fh_:
                msgpack.dump('', fh_)

    for header in header_list:
        comps = header.split(':')
        if len(comps) < 2:
            continue
        header_dict[comps[0].strip()] = comps[1].strip()

    if username and password:
        auth = (username, password)
    else:
        auth = None

    sess = requests.Session()
    sess.auth = auth
    sess.headers.update(header_dict)
    log.trace('Request Headers: {0}'.format(sess.headers))

    if cookies is not None:
        if cookie_format == 'mozilla':
            sess.cookies = salt.utils.six.moves.http_cookiejar.MozillaCookieJar(cookie_jar)
        else:
            sess.cookies = salt.utils.six.moves.http_cookiejar.LWPCookieJar(cookie_jar)
        if not os.path.isfile(cookie_jar):
            sess.cookies.save()
        else:
            sess.cookies.load()

    if test is True:
        if test_url is None:
            return {}
        else:
            url = test_url
            ret['test'] = True

    result = sess.request(
        method, url, params=params, data=data
    )
    log.debug('Response Status Code: {0}'.format(result.status_code))
    log.trace('Response Headers: {0}'.format(result.headers))
    log.trace('Response Text: {0}'.format(result.text))
    log.trace('Response Cookies: {0}'.format(result.cookies.get_dict()))

    if cookies is not None:
        sess.cookies.save()

    if persist_session is True:
        # TODO: See persist_session above
        if 'set-cookie' in result.headers:
            with salt.utils.fopen(session_cookie_jar, 'w') as fh_:
                session_cookies = result.headers.get('set-cookie', None)
                if session_cookies is not None:
                    msgpack.dump({'Cookie': session_cookies}, fh_)
                else:
                    msgpack.dump('', fh_)

    if status is True:
        ret['status'] = result.status_code

    if headers is True:
        ret['headers'] = result.headers

    if decode is True:
        if decode_type == 'auto':
            content_type = result.headers.get(
                'content-type', 'application/json'
            )
            if 'xml' in content_type:
                decode_type = 'xml'
            elif 'json' in content_type:
                decode_type = 'json'
            else:
                decode_type = 'plain'

        valid_decodes = ('json', 'xml', 'plain')
        if decode_type not in valid_decodes:
            ret['error'] = (
                'Invalid decode_type specified. '
                'Valid decode types are: {0}'.format(
                    pprint.pformat(valid_decodes)
                )
            )
            log.error(ret['error'])
            return ret

        if decode_type == 'json':
            ret['dict'] = json.loads(result.text)
        elif decode_type == 'xml':
            ret['dict'] = []
            items = ET.fromstring(result.text)
            for item in items:
                ret['dict'].append(xml.to_dict(item))
        else:
            text = True

    if text is True:
        ret['text'] = result.text

    return ret


def _render(template, render, renderer, template_dict, opts):
    '''
    Render a template
    '''
    if render:
        if template_dict is None:
            template_dict = {}
        if not renderer:
            renderer = opts.get('renderer', 'yaml_jinja')
        rend = salt.loader.render(opts, {})
        return compile_template(template, rend, renderer, **template_dict)
    with salt.utils.fopen(template, 'r') as fh_:
        return fh_.read()
