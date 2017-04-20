# -*- coding: utf-8 -*-
'''
Utils for making various web calls. Primarily designed for REST, SOAP, webhooks
and the like, but also useful for basic HTTP testing.

.. versionadded:: 2015.5.0
'''

# Import python libs
from __future__ import absolute_import
import cgi
import json
import logging
import os.path
import pprint
import socket
import urllib
import yaml

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
        try:
            from salt.ext.ssl_match_hostname import CertificateError
            from salt.ext.ssl_match_hostname import match_hostname
            HAS_MATCHHOSTNAME = True
        except ImportError:
            HAS_MATCHHOSTNAME = False

# Import salt libs
import salt.utils
import salt.utils.xmlutil as xml
import salt.utils.args
import salt.loader
import salt.config
import salt.version
from salt._compat import ElementTree as ET
from salt.template import compile_template
from salt import syspaths

# Import 3rd party libs
import salt.ext.six as six
# pylint: disable=import-error,no-name-in-module
import salt.ext.six.moves.http_client
import salt.ext.six.moves.http_cookiejar
import salt.ext.six.moves.urllib.request as urllib_request
from salt.ext.six.moves.urllib.error import URLError
from salt.ext.six.moves.urllib.parse import splitquery
# pylint: enable=import-error,no-name-in-module

# Don't need a try/except block, since Salt depends on tornado
import tornado.httputil
import tornado.simple_httpclient
from tornado.httpclient import HTTPClient

try:
    import tornado.curl_httpclient
    HAS_CURL_HTTPCLIENT = True
except ImportError:
    HAS_CURL_HTTPCLIENT = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

log = logging.getLogger(__name__)
USERAGENT = 'Salt/{0}'.format(salt.version.__version__)


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
          auth=None,
          decode=False,
          decode_type='auto',
          status=False,
          headers=False,
          text=False,
          cookies=None,
          cookie_jar=None,
          cookie_format='lwp',
          persist_session=False,
          session_cookie_jar=None,
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
          backend=None,
          requests_lib=None,
          ca_bundle=None,
          verify_ssl=None,
          cert=None,
          text_out=None,
          headers_out=None,
          decode_out=None,
          stream=False,
          streaming_callback=None,
          header_callback=None,
          handle=False,
          agent=USERAGENT,
          hide_fields=None,
          raise_error=True,
          **kwargs):
    '''
    Query a resource, and decode the return data
    '''
    ret = {}

    if opts is None:
        if node == 'master':
            opts = salt.config.master_config(
                os.path.join(syspaths.CONFIG_DIR, 'master')
            )
        elif node == 'minion':
            opts = salt.config.minion_config(
                os.path.join(syspaths.CONFIG_DIR, 'minion')
            )
        else:
            opts = {}

    if not backend:
        if requests_lib is not None or 'requests_lib' in opts:
            salt.utils.warn_until('Oxygen', '"requests_lib:True" has been replaced by "backend:requests", '
                                            'please change your config')
            # beware the named arg above
            if 'backend' in opts:
                backend = opts['backend']
            elif requests_lib or opts.get('requests_lib', False):
                backend = 'requests'
            else:
                backend = 'tornado'
        else:
            backend = opts.get('backend', 'tornado')

    if backend == 'requests':
        if HAS_REQUESTS is False:
            ret['error'] = ('http.query has been set to use requests, but the '
                            'requests library does not seem to be installed')
            log.error(ret['error'])
            return ret
        else:
            requests_log = logging.getLogger('requests')
            requests_log.setLevel(logging.WARNING)

    # Some libraries don't support separation of url and GET parameters
    # Don't need a try/except block, since Salt depends on tornado
    url_full = tornado.httputil.url_concat(url, params) if params else url

    if ca_bundle is None:
        ca_bundle = get_ca_bundle(opts)

    if verify_ssl is None:
        verify_ssl = opts.get('verify_ssl', True)

    if cert is None:
        cert = opts.get('cert', None)

    if data_file is not None:
        data = _render(
            data_file, data_render, data_renderer, template_dict, opts
        )

    # Make sure no secret fields show up in logs
    log_url = sanitize_url(url_full, hide_fields)

    log.debug('Requesting URL {0} using {1} method'.format(log_url, method))
    if method == 'POST' and log.isEnabledFor(logging.TRACE):
        # Make sure no secret fields show up in logs
        if isinstance(data, dict):
            log_data = data.copy()
            if isinstance(hide_fields, list):
                for item in data:
                    for field in hide_fields:
                        if item == field:
                            log_data[item] = 'XXXXXXXXXX'
            log.trace('Request POST Data: {0}'.format(pprint.pformat(log_data)))
        else:
            log.trace('Request POST Data: {0}'.format(pprint.pformat(data)))

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

    if cookie_jar is None:
        cookie_jar = os.path.join(opts.get('cachedir', syspaths.CACHE_DIR), 'cookies.txt')
    if session_cookie_jar is None:
        session_cookie_jar = os.path.join(opts.get('cachedir', syspaths.CACHE_DIR), 'cookies.session.p')

    if persist_session is True and HAS_MSGPACK:
        # TODO: This is hackish; it will overwrite the session cookie jar with
        # all cookies from this one connection, rather than behaving like a
        # proper cookie jar. Unfortunately, since session cookies do not
        # contain expirations, they can't be stored in a proper cookie jar.
        if os.path.isfile(session_cookie_jar):
            with salt.utils.fopen(session_cookie_jar, 'rb') as fh_:
                session_cookies = msgpack.load(fh_)
            if isinstance(session_cookies, dict):
                header_dict.update(session_cookies)
        else:
            with salt.utils.fopen(session_cookie_jar, 'wb') as fh_:
                msgpack.dump('', fh_)

    for header in header_list:
        comps = header.split(':')
        if len(comps) < 2:
            continue
        header_dict[comps[0].strip()] = comps[1].strip()

    if not auth:
        if username and password:
            auth = (username, password)

    if agent == USERAGENT:
        agent = '{0} http.query()'.format(agent)
    header_dict['User-agent'] = agent

    if backend == 'requests':
        sess = requests.Session()
        sess.auth = auth
        sess.headers.update(header_dict)
        log.trace('Request Headers: {0}'.format(sess.headers))
        sess_cookies = sess.cookies
        sess.verify = verify_ssl
    elif backend == 'urllib2':
        sess_cookies = None
    else:
        # Tornado
        sess_cookies = None

    if cookies is not None:
        if cookie_format == 'mozilla':
            sess_cookies = salt.ext.six.moves.http_cookiejar.MozillaCookieJar(cookie_jar)
        else:
            sess_cookies = salt.ext.six.moves.http_cookiejar.LWPCookieJar(cookie_jar)
        if not os.path.isfile(cookie_jar):
            sess_cookies.save()
        sess_cookies.load()

    if test is True:
        if test_url is None:
            return {}
        else:
            url = test_url
            ret['test'] = True

    if backend == 'requests':
        req_kwargs = {}
        if stream is True:
            if requests.__version__[0] == '0':
                # 'stream' was called 'prefetch' before 1.0, with flipped meaning
                req_kwargs['prefetch'] = False
            else:
                req_kwargs['stream'] = True

        # Client-side cert handling
        if cert is not None:
            if isinstance(cert, six.string_types):
                if os.path.exists(cert):
                    req_kwargs['cert'] = cert
            elif isinstance(cert, list):
                if os.path.exists(cert[0]) and os.path.exists(cert[1]):
                    req_kwargs['cert'] = cert
            else:
                log.error('The client-side certificate path that was passed is '
                          'not valid: {0}'.format(cert))

        result = sess.request(
            method, url, params=params, data=data, **req_kwargs
        )
        result.raise_for_status()
        if stream is True:
            # fake a HTTP response header
            header_callback('HTTP/1.0 {0} MESSAGE'.format(result.status_code))
            # fake streaming the content
            streaming_callback(result.content)
            return {
                'handle': result,
            }

        if handle is True:
            return {
                'handle': result,
                'body': result.content,
            }

        log.debug('Final URL location of Response: {0}'.format(sanitize_url(result.url, hide_fields)))

        result_status_code = result.status_code
        result_headers = result.headers
        result_text = result.content
        result_cookies = result.cookies
        body = result.content
        if not isinstance(body, six.text_type):
            body = body.decode(result.encoding or 'utf-8')
        ret['body'] = body
    elif backend == 'urllib2':
        request = urllib_request.Request(url_full, data)
        handlers = [
            urllib_request.HTTPHandler,
            urllib_request.HTTPCookieProcessor(sess_cookies)
        ]

        if url.startswith('https'):
            hostname = request.get_host()
            handlers[0] = urllib_request.HTTPSHandler(1)
            if not HAS_MATCHHOSTNAME:
                log.warning('match_hostname() not available, SSL hostname checking '
                         'not available. THIS CONNECTION MAY NOT BE SECURE!')
            elif verify_ssl is False:
                log.warning('SSL certificate verification has been explicitly '
                         'disabled. THIS CONNECTION MAY NOT BE SECURE!')
            else:
                if ':' in hostname:
                    hostname, port = hostname.split(':')
                else:
                    port = 443
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((hostname, int(port)))
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

                # Client-side cert handling
                if cert is not None:
                    cert_chain = None
                    if isinstance(cert, six.string_types):
                        if os.path.exists(cert):
                            cert_chain = (cert)
                    elif isinstance(cert, list):
                        if os.path.exists(cert[0]) and os.path.exists(cert[1]):
                            cert_chain = cert
                    else:
                        log.error('The client-side certificate path that was '
                                  'passed is not valid: {0}'.format(cert))
                        return
                    if hasattr(ssl, 'SSLContext'):
                        # Python >= 2.7.9
                        context = ssl.SSLContext.load_cert_chain(*cert_chain)
                        handlers.append(urllib_request.HTTPSHandler(context=context))  # pylint: disable=E1123
                    else:
                        # Python < 2.7.9
                        cert_kwargs = {
                            'host': request.get_host(),
                            'port': port,
                            'cert_file': cert_chain[0]
                        }
                        if len(cert_chain) > 1:
                            cert_kwargs['key_file'] = cert_chain[1]
                        handlers[0] = salt.ext.six.moves.http_client.HTTPSConnection(**cert_kwargs)

        opener = urllib_request.build_opener(*handlers)
        for header in header_dict:
            request.add_header(header, header_dict[header])
        request.get_method = lambda: method
        try:
            result = opener.open(request)
        except URLError as exc:
            return {'Error': str(exc)}
        if stream is True or handle is True:
            return {
                'handle': result,
                'body': result.content,
            }

        result_status_code = result.code
        result_headers = dict(result.info())
        result_text = result.read()
        if 'Content-Type' in result_headers:
            res_content_type, res_params = cgi.parse_header(result_headers['Content-Type'])
            if res_content_type.startswith('text/') and \
                    'charset' in res_params and \
                    not isinstance(result_text, six.text_type):
                result_text = result_text.decode(res_params['charset'])
        ret['body'] = result_text
    else:
        # Tornado
        req_kwargs = {}

        # Client-side cert handling
        if cert is not None:
            if isinstance(cert, six.string_types):
                if os.path.exists(cert):
                    req_kwargs['client_cert'] = cert
            elif isinstance(cert, list):
                if os.path.exists(cert[0]) and os.path.exists(cert[1]):
                    req_kwargs['client_cert'] = cert[0]
                    req_kwargs['client_key'] = cert[1]
            else:
                log.error('The client-side certificate path that was passed is '
                          'not valid: {0}'.format(cert))

        if isinstance(data, dict):
            data = urllib.urlencode(data)

        if verify_ssl:
            req_kwargs['ca_certs'] = ca_bundle

        max_body = opts.get('http_max_body', salt.config.DEFAULT_MINION_OPTS['http_max_body'])
        timeout = opts.get('http_request_timeout', salt.config.DEFAULT_MINION_OPTS['http_request_timeout'])

        client_argspec = None

        proxy_host = opts.get('proxy_host', None)
        proxy_port = opts.get('proxy_port', None)
        proxy_username = opts.get('proxy_username', None)
        proxy_password = opts.get('proxy_password', None)

        # We want to use curl_http if we have a proxy defined
        if proxy_host and proxy_port:
            if HAS_CURL_HTTPCLIENT is False:
                ret['error'] = ('proxy_host and proxy_port has been set. This requires pycurl, but the '
                                'pycurl library does not seem to be installed')
                log.error(ret['error'])
                return ret

            tornado.httpclient.AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
            client_argspec = salt.utils.args.get_function_argspec(
                    tornado.curl_httpclient.CurlAsyncHTTPClient.initialize)
        else:
            client_argspec = salt.utils.args.get_function_argspec(
                    tornado.simple_httpclient.SimpleAsyncHTTPClient.initialize)

        supports_max_body_size = 'max_body_size' in client_argspec.args

        try:
            download_client = HTTPClient(max_body_size=max_body) \
                if supports_max_body_size \
                else HTTPClient()
            result = download_client.fetch(
                url_full,
                method=method,
                headers=header_dict,
                auth_username=username,
                auth_password=password,
                body=data,
                validate_cert=verify_ssl,
                allow_nonstandard_methods=True,
                streaming_callback=streaming_callback,
                header_callback=header_callback,
                request_timeout=timeout,
                proxy_host=proxy_host,
                proxy_port=proxy_port,
                proxy_username=proxy_username,
                proxy_password=proxy_password,
                raise_error=raise_error,
                decompress_response=False,
                **req_kwargs
            )
        except tornado.httpclient.HTTPError as exc:
            ret['status'] = exc.code
            ret['error'] = str(exc)
            return ret
        except socket.gaierror as exc:
            if status is True:
                ret['status'] = 0
            ret['error'] = str(exc)
            return ret

        if stream is True or handle is True:
            return {
                'handle': result,
                'body': result.body,
            }

        result_status_code = result.code
        result_headers = result.headers
        result_text = result.body
        if 'Content-Type' in result_headers:
            res_content_type, res_params = cgi.parse_header(result_headers['Content-Type'])
            if res_content_type.startswith('text/') and \
                    'charset' in res_params and \
                    not isinstance(result_text, six.text_type):
                result_text = result_text.decode(res_params['charset'])
        ret['body'] = result_text
        if 'Set-Cookie' in result_headers.keys() and cookies is not None:
            result_cookies = parse_cookie_header(result_headers['Set-Cookie'])
            for item in result_cookies:
                sess_cookies.set_cookie(item)
        else:
            result_cookies = None

    if isinstance(result_headers, list):
        result_headers_dict = {}
        for header in result_headers:
            comps = header.split(':')
            result_headers_dict[comps[0].strip()] = ':'.join(comps[1:]).strip()
        result_headers = result_headers_dict

    log.debug('Response Status Code: {0}'.format(result_status_code))
    log.trace('Response Headers: {0}'.format(result_headers))
    log.trace('Response Cookies: {0}'.format(sess_cookies))
    try:
        log.trace('Response Text: {0}'.format(result_text))
    except UnicodeEncodeError as exc:
        log.trace(('Cannot Trace Log Response Text: {0}. This may be due to '
                  'incompatibilities between requests and logging.').format(exc))

    if text_out is not None:
        with salt.utils.fopen(text_out, 'w') as tof:
            tof.write(result_text)

    if headers_out is not None and os.path.exists(headers_out):
        with salt.utils.fopen(headers_out, 'w') as hof:
            hof.write(result_headers)

    if cookies is not None:
        sess_cookies.save()

    if persist_session is True and HAS_MSGPACK:
        # TODO: See persist_session above
        if 'set-cookie' in result_headers:
            with salt.utils.fopen(session_cookie_jar, 'wb') as fh_:
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
            elif 'yaml' in content_type:
                decode_type = 'yaml'
            else:
                decode_type = 'plain'

        valid_decodes = ('json', 'xml', 'yaml', 'plain')
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
            ret['dict'] = json.loads(salt.utils.to_str(result_text))
        elif decode_type == 'xml':
            ret['dict'] = []
            items = ET.fromstring(result_text)
            for item in items:
                ret['dict'].append(xml.to_dict(item))
        elif decode_type == 'yaml':
            ret['dict'] = yaml.safe_load(result_text)
        else:
            text = True

        if decode_out:
            with salt.utils.fopen(decode_out, 'w') as dof:
                dof.write(result_text)

    if text is True:
        ret['text'] = result_text

    return ret


def get_ca_bundle(opts=None):
    '''
    Return the location of the ca bundle file. See the following article:

        http://tinyurl.com/k7rx42a
    '''
    if hasattr(get_ca_bundle, '__return_value__'):
        return get_ca_bundle.__return_value__

    if opts is None:
        opts = {}

    opts_bundle = opts.get('ca_bundle', None)
    if opts_bundle is not None and os.path.exists(opts_bundle):
        return opts_bundle

    file_roots = opts.get('file_roots', {'base': [syspaths.SRV_ROOT_DIR]})

    # Please do not change the order without good reason

    # Check Salt first
    for salt_root in file_roots.get('base', []):
        for path in ('cacert.pem', 'ca-bundle.crt'):
            cert_path = os.path.join(salt_root, path)
            if os.path.exists(cert_path):
                return cert_path

    locations = (
        # Debian has paths that often exist on other distros
        '/etc/ssl/certs/ca-certificates.crt',
        # RedHat is also very common
        '/etc/pki/tls/certs/ca-bundle.crt',
        '/etc/pki/tls/certs/ca-bundle.trust.crt',
        # RedHat's link for Debian compatibility
        '/etc/ssl/certs/ca-bundle.crt',
        # SUSE has an unusual path
        '/var/lib/ca-certificates/ca-bundle.pem',
        # OpenBSD has an unusual path
        '/etc/ssl/cert.pem',
    )
    for path in locations:
        if os.path.exists(path):
            return path

    if salt.utils.is_windows() and HAS_CERTIFI:
        return certifi.where()

    return None


def update_ca_bundle(
        target=None,
        source=None,
        opts=None,
        merge_files=None,
    ):
    '''
    Attempt to update the CA bundle file from a URL

    If not specified, the local location on disk (``target``) will be
    auto-detected, if possible. If it is not found, then a new location on disk
    will be created and updated.

    The default ``source`` is:

        http://curl.haxx.se/ca/cacert.pem

    This is based on the information at:

        http://curl.haxx.se/docs/caextract.html

    A string or list of strings representing files to be appended to the end of
    the CA bundle file may also be passed through as ``merge_files``.
    '''
    if opts is None:
        opts = {}

    if target is None:
        target = get_ca_bundle(opts)

    if target is None:
        log.error('Unable to detect location to write CA bundle to')
        return

    if source is None:
        source = opts.get('ca_bundle_url', 'http://curl.haxx.se/ca/cacert.pem')

    log.debug('Attempting to download {0} to {1}'.format(source, target))
    query(
        source,
        text=True,
        decode=False,
        headers=False,
        status=False,
        text_out=target
    )

    if merge_files is not None:
        if isinstance(merge_files, six.string_types):
            merge_files = [merge_files]

        if not isinstance(merge_files, list):
            log.error('A value was passed as merge_files which was not either '
                      'a string or a list')
            return

        merge_content = ''

        for cert_file in merge_files:
            if os.path.exists(cert_file):
                log.debug(
                    'Queueing up {0} to be appended to {1}'.format(
                        cert_file, target
                    )
                )
                try:
                    with salt.utils.fopen(cert_file, 'r') as fcf:
                        merge_content = '\n'.join((merge_content, fcf.read()))
                except IOError as exc:
                    log.error(
                        'Reading from {0} caused the following error: {1}'.format(
                            cert_file, exc
                        )
                    )

        if merge_content:
            log.debug('Appending merge_files to {0}'.format(target))
            try:
                with salt.utils.fopen(target, 'a') as tfp:
                    tfp.write('\n')
                    tfp.write(merge_content)
            except IOError as exc:
                log.error(
                    'Writing to {0} caused the following error: {1}'.format(
                        target, exc
                    )
                )


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
        blacklist = opts.get('renderer_blacklist')
        whitelist = opts.get('renderer_whitelist')
        ret = compile_template(template, rend, renderer, blacklist, whitelist, **template_dict)
        ret = ret.read()
        if str(ret).startswith('#!') and not str(ret).startswith('#!/'):
            ret = str(ret).split('\n', 1)[1]
        return ret
    with salt.utils.fopen(template, 'r') as fh_:
        return fh_.read()


def parse_cookie_header(header):
    '''
    Parse the "Set-cookie" header, and return a list of cookies.

    This function is here because Tornado's HTTPClient doesn't handle cookies.
    '''
    attribs = ('expires', 'path', 'domain', 'version', 'httponly', 'secure', 'comment', 'max-age')

    # Split into cookie(s); handles headers with multiple cookies defined
    morsels = []
    for item in header.split(';'):
        item = item.strip()
        if ',' in item and 'expires' not in item:
            for part in item.split(','):
                morsels.append(part)
        else:
            morsels.append(item)

    # Break down morsels into actual cookies
    cookies = []
    cookie = {}
    value_set = False
    for morsel in morsels:
        parts = morsel.split('=')
        if parts[0].lower() in attribs:
            if parts[0] in cookie:
                cookies.append(cookie)
                cookie = {}
            if len(parts) > 1:
                cookie[parts[0]] = '='.join(parts[1:])
            else:
                cookie[parts[0]] = True
        else:
            if value_set is True:
                # This is a new cookie; save the old one and clear for this one
                cookies.append(cookie)
                cookie = {}
                value_set = False
            cookie[parts[0]] = '='.join(parts[1:])
            value_set = True

    if cookie:
        # Set the last cookie that was processed
        cookies.append(cookie)

    # These arguments are required by cookielib.Cookie()
    reqd = (
        'version',
        'port',
        'port_specified',
        'domain',
        'domain_specified',
        'domain_initial_dot',
        'path',
        'path_specified',
        'secure',
        'expires',
        'discard',
        'comment',
        'comment_url',
        'rest',
    )

    ret = []
    for cookie in cookies:
        name = None
        value = None
        for item in cookie:
            if item in attribs:
                continue
            name = item
            value = cookie[item]
            del cookie[name]

        # cookielib.Cookie() requires an epoch
        if 'expires' in cookie:
            cookie['expires'] = salt.ext.six.moves.http_cookiejar.http2time(cookie['expires'])

        # Fill in missing required fields
        for req in reqd:
            if req not in cookie.keys():
                cookie[req] = ''
        if cookie['version'] == '':
            cookie['version'] = 0
        if cookie['rest'] == '':
            cookie['rest'] = {}
        if cookie['expires'] == '':
            cookie['expires'] = 0

        if 'httponly' in cookie:
            del cookie['httponly']
        ret.append(salt.ext.six.moves.http_cookiejar.Cookie(name=name, value=value, **cookie))

    return ret


def sanitize_url(url, hide_fields):
    '''
    Make sure no secret fields show up in logs
    '''
    if isinstance(hide_fields, list):
        url_comps = splitquery(url)
        log_url = url_comps[0]
        if len(url_comps) > 1:
            log_url += '?'
        for pair in url_comps[1:]:
            url_tmp = None
            for field in hide_fields:
                comps_list = pair.split('&')
                if url_tmp:
                    url_tmp = url_tmp.split('&')
                    url_tmp = _sanitize_url_components(url_tmp, field)
                else:
                    url_tmp = _sanitize_url_components(comps_list, field)
            log_url += url_tmp
        return log_url.rstrip('&')
    else:
        return str(url)


def _sanitize_url_components(comp_list, field):
    '''
    Recursive function to sanitize each component of the url.
    '''
    if len(comp_list) == 0:
        return ''
    elif comp_list[0].startswith('{0}='.format(field)):
        ret = '{0}=XXXXXXXXXX&'.format(field)
        comp_list.remove(comp_list[0])
        return ret + _sanitize_url_components(comp_list, field)
    else:
        ret = '{0}&'.format(comp_list[0])
        comp_list.remove(comp_list[0])
        return ret + _sanitize_url_components(comp_list, field)
