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
import salt.ext.six.moves.http_cookiejar  # pylint: disable=E0611
from salt._compat import ElementTree as ET

import ssl
try:
    from ssl import CertificateError  # pylint: disable=E0611
    from ssl import match_hostname  # pylint: disable=E0611
    HAS_MATCHHOSTNAME = True
except ImportError:
    try:
        from backports.ssl_match_hostname import CertificateError
        from backports.ssl_match_hostname import match_hostname
        HAS_MATCHHOSTNAME = True
    except ImportError:
        HAS_MATCHHOSTNAME = False
import socket
import urllib2

# Import salt libs
import salt.utils
import salt.utils.xmlutil as xml
import salt.loader
import salt.config
from salt.template import compile_template
from salt import syspaths

# Import 3rd party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
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
          port=80,
          opts=None,
          requests_lib=None,
          ca_bundle=None,
          verify_ssl=None,
          **kwargs):
    '''
    Query a resource, and decode the return data
    '''
    ret = {}

    if opts is None:
        if node == 'master':
            opts = salt.config.master_config('/etc/salt/master')
        elif node == 'minion':
            opts = salt.config.master_config('/etc/salt/minion')
        else:
            opts = {}

    if requests_lib is None:
        requests_lib = opts.get('requests_lib', False)

    if requests_lib is True:
        if HAS_REQUESTS is False:
            ret['error'] = ('http.query has been set to use requests, but the '
                            'requests library does not seem to be installed')
            log.error(ret['error'])
            return ret
    else:
        requests_log = logging.getLogger('requests')
        requests_log.setLevel(logging.WARNING)

    if verify_ssl is None:
        verify_ssl = opts.get('verify_ssl', True)

    if ca_bundle is None:
        ca_bundle = get_ca_bundle(opts)

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

    if requests_lib is True:
        sess = requests.Session()
        sess.auth = auth
        sess.headers.update(header_dict)
        log.trace('Request Headers: {0}'.format(sess.headers))
        sess_cookies = sess.cookies
        sess.verify = verify_ssl
    else:
        sess_cookies = None

    if cookies is not None:
        if cookie_format == 'mozilla':
            sess_cookies = salt.ext.six.moves.http_cookiejar.MozillaCookieJar(cookie_jar)
        else:
            sess_cookies = salt.ext.six.moves.http_cookiejar.LWPCookieJar(cookie_jar)
        if not os.path.isfile(cookie_jar):
            sess_cookies.save()
        else:
            sess_cookies.load()

    if test is True:
        if test_url is None:
            return {}
        else:
            url = test_url
            ret['test'] = True

    if requests_lib is True:
        result = sess.request(
            method, url, params=params, data=data
        )
        result_status_code = result.status_code
        result_headers = result.headers
        result_text = result.text
        result_cookies = result.cookies
    else:
        request = urllib2.Request(url)

        if url.startswith('https') or port == 443:
            if not HAS_MATCHHOSTNAME:
                log.warn(('match_hostname() not available, SSL hostname checking'
                         'not available. THIS CONNECTION MAY NOT BE SECURE!'))
            elif verify_ssl is False:
                log.warn(('SSL certificate verification has been explicitly '
                         'disabled. THIS CONNECTION MAY NOT BE SECURE!'))
            else:
                hostname = request.get_host()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((hostname, 443))
                sockwrap = ssl.wrap_socket(
                    sock,
                    ca_certs=ca_bundle,
                    cert_reqs=ssl.CERT_REQUIRED
                )
                try:
                    match_hostname(sockwrap.getpeercert(), hostname)
                except CertificateError as exc:
                    ret['error'] = (
                        'The certificate was invalid. '
                        'Error returned was: {0}'.format(
                            pprint.pformat(exc)
                        )
                    )
                    return ret

        opener = urllib2.build_opener(
            urllib2.HTTPHandler,
            urllib2.HTTPCookieProcessor(sess_cookies)
        )
        for header in header_dict:
            request.add_header(header, header_dict[header])
        request.get_method = lambda: method
        result = opener.open(request)

        result_status_code = result.code
        result_headers = result.headers.headers
        result_text = result.read()

    log.debug('Response Status Code: {0}'.format(result_status_code))
    log.trace('Response Headers: {0}'.format(result_headers))
    log.trace('Response Cookies: {0}'.format(sess_cookies))
    try:
        log.trace('Response Text: {0}'.format(result_text))
    except UnicodeEncodeError as exc:
        log.trace(('Cannot Trace Log Response Text: {0}. This may be due to '
                  'incompatibilities between requests and logging.').format(exc))

    if cookies is not None:
        sess_cookies.save()

    if persist_session is True:
        # TODO: See persist_session above
        if 'set-cookie' in result_headers:
            with salt.utils.fopen(session_cookie_jar, 'w') as fh_:
                session_cookies = result_headers.get('set-cookie', None)
                if session_cookies is not None:
                    msgpack.dump({'Cookie': session_cookies}, fh_)
                else:
                    msgpack.dump('', fh_)

    if status is True:
        ret['status'] = result_status_code

    if headers is True:
        ret['headers'] = result_headers

    if decode is True:
        if decode_type == 'auto':
            content_type = result_headers.get(
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
            ret['dict'] = json.loads(result_text)
        elif decode_type == 'xml':
            ret['dict'] = []
            items = ET.fromstring(result_text)
            for item in items:
                ret['dict'].append(xml.to_dict(item))
        else:
            text = True

    if text is True:
        ret['text'] = result_text

    return ret


def get_ca_bundle(opts):
    '''
    Return the location of the ca bundle file. See the following article:

        http://tinyurl.com/k7rx42a
    '''
    if hasattr(get_ca_bundle, '__return_value__'):
        return get_ca_bundle.__return_value__

    opts_bundle = opts.get('ca_bundle', None)
    if opts_bundle is not None and os.path.exists(opts_bundle):
        return opts_bundle

    for path in (
        '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem',
        '/etc/pki/tls/certs/ca-bundle.crt',
        '/etc/pki/tls/certs/ca-bundle.trust.crt',
        '/etc/ssl/certs/ca-bundle.crt',
        '/etc/ssl/certs/ca-certificates.crt',
        '/var/lib/ca-certificates/ca-bundle.pem',
    ):
        if os.path.exists(path):
            return path

    return None


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
