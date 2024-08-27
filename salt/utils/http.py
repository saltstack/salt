"""
Utils for making various web calls. Primarily designed for REST, SOAP, webhooks
and the like, but also useful for basic HTTP testing.

.. versionadded:: 2015.5.0
"""

import email.message
import gzip
import http.client
import http.cookiejar
import io
import logging
import os
import pprint
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib

import tornado.httpclient
import tornado.httputil
import tornado.simple_httpclient
from tornado.httpclient import AsyncHTTPClient

import salt.config
import salt.loader
import salt.syspaths
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.msgpack
import salt.utils.network
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.url
import salt.utils.xmlutil as xml
import salt.utils.yaml
import salt.version
from salt.template import compile_template
from salt.utils.asynchronous import SyncWrapper
from salt.utils.decorators.jinja import jinja_filter

try:
    from ssl import CertificateError, match_hostname

    HAS_MATCHHOSTNAME = True
except ImportError:
    # pylint: disable=no-name-in-module
    try:
        from backports.ssl_match_hostname import CertificateError, match_hostname

        HAS_MATCHHOSTNAME = True
    except ImportError:
        try:
            from salt.ext.ssl_match_hostname import CertificateError, match_hostname

            HAS_MATCHHOSTNAME = True
        except ImportError:
            HAS_MATCHHOSTNAME = False
    # pylint: enable=no-name-in-module

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import certifi

    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

log = logging.getLogger(__name__)
USERAGENT = f"Salt/{salt.version.__version__}"


def __decompressContent(coding, pgctnt):
    """
    Decompress returned HTTP content depending on the specified encoding.
    Currently supports identity/none, deflate, and gzip, which should
    cover 99%+ of the content on the internet.
    """
    if not pgctnt:
        return pgctnt

    log.trace(
        "Decompressing %s byte content with compression type: %s", len(pgctnt), coding
    )

    if coding == "deflate":
        pgctnt = zlib.decompress(pgctnt, -zlib.MAX_WBITS)

    elif coding == "gzip":
        buf = io.BytesIO(pgctnt)
        f = gzip.GzipFile(fileobj=buf)
        pgctnt = f.read()

    elif coding == "sdch":
        raise ValueError("SDCH compression is not currently supported")
    elif coding == "br":
        raise ValueError("Brotli compression is not currently supported")
    elif coding == "compress":
        raise ValueError("LZW compression is not currently supported")

    log.trace("Content size after decompression: %s", len(pgctnt))
    return pgctnt


def _decode_result_text(result_text, backend, decode_body=None, result=None):
    """
    Decode only the result_text
    """
    if backend == "requests":
        if not isinstance(result_text, str) and decode_body:
            result_text = result_text.decode(result.encoding or "utf-8")
    else:
        if isinstance(result_text, bytes) and decode_body:
            result_text = result_text.decode("utf-8")
    return result_text


def _decode_result(result_text, result_headers, backend, decode_body=None, result=None):
    """
    Decode the result_text and headers.
    """
    if "Content-Type" in result_headers:
        msg = email.message.EmailMessage()
        msg.add_header("Content-Type", result_headers["Content-Type"])
        if msg.get_content_type().startswith("text/"):
            content_charset = msg.get_content_charset()
            if content_charset and not isinstance(result_text, str):
                result_text = result_text.decode(content_charset)
    result_text = _decode_result_text(
        result_text, backend, decode_body=decode_body, result=result
    )

    return result_text, result_headers


@jinja_filter("http_query")
def query(
    url,
    method="GET",
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
    decode_type="auto",
    status=False,
    headers=False,
    text=False,
    cookies=None,
    cookie_jar=None,
    cookie_format="lwp",
    persist_session=False,
    session_cookie_jar=None,
    data_render=False,
    data_renderer=None,
    header_render=False,
    header_renderer=None,
    template_dict=None,
    test=False,
    test_url=None,
    node="minion",
    port=80,
    opts=None,
    backend=None,
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
    formdata=False,
    formdata_fieldname=None,
    formdata_filename=None,
    decode_body=True,
    **kwargs,
):
    """
    Query a resource, and decode the return data
    """
    ret = {}

    if opts is None:
        if node == "master":
            opts = salt.config.master_config(
                os.path.join(salt.syspaths.CONFIG_DIR, "master")
            )
        elif node == "minion":
            opts = salt.config.minion_config(
                os.path.join(salt.syspaths.CONFIG_DIR, "minion")
            )
        else:
            opts = {}

    if not backend:
        backend = opts.get("backend", "tornado")

    proxy_host = opts.get("proxy_host", None)
    if proxy_host:
        proxy_host = salt.utils.stringutils.to_str(proxy_host)
    proxy_port = opts.get("proxy_port", None)
    proxy_username = opts.get("proxy_username", None)
    if proxy_username:
        proxy_username = salt.utils.stringutils.to_str(proxy_username)
    proxy_password = opts.get("proxy_password", None)
    if proxy_password:
        proxy_password = salt.utils.stringutils.to_str(proxy_password)
    no_proxy = opts.get("no_proxy", [])

    if urllib.parse.urlparse(url).hostname in no_proxy:
        proxy_host = None
        proxy_port = None
        proxy_username = None
        proxy_password = None

    http_proxy_url = None
    if proxy_host and proxy_port:
        if backend != "requests":
            log.debug("Switching to request backend due to the use of proxies.")
            backend = "requests"

        if proxy_username and proxy_password:
            http_proxy_url = (
                f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
            )
        else:
            http_proxy_url = f"http://{proxy_host}:{proxy_port}"

    match = re.match(
        r"https?://((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)($|/)",
        url,
    )
    if not match:
        salt.utils.network.refresh_dns()

    if backend == "requests":
        if HAS_REQUESTS is False:
            ret["error"] = (
                "http.query has been set to use requests, but the "
                "requests library does not seem to be installed"
            )
            log.error(ret["error"])
            return ret
        else:
            requests_log = logging.getLogger("requests")
            requests_log.setLevel(logging.WARNING)

    # Some libraries don't support separation of url and GET parameters
    # Don't need a try/except block, since Salt depends on tornado
    url_full = tornado.httputil.url_concat(url, params) if params else url

    if ca_bundle is None:
        ca_bundle = get_ca_bundle(opts)

    if verify_ssl is None:
        verify_ssl = opts.get("verify_ssl", True)

    if cert is None:
        cert = opts.get("cert", None)

    if data_file is not None:
        data = _render(data_file, data_render, data_renderer, template_dict, opts)

    # Make sure no secret fields show up in logs
    log_url = sanitize_url(url_full, hide_fields)

    log.debug("Requesting URL %s using %s method", log_url, method)
    log.debug("Using backend: %s", backend)

    if method == "POST" and log.isEnabledFor(logging.TRACE):
        # Make sure no secret fields show up in logs
        if isinstance(data, dict):
            log_data = data.copy()
            if isinstance(hide_fields, list):
                for item in data:
                    for field in hide_fields:
                        if item == field:
                            log_data[item] = "XXXXXXXXXX"
            log.trace("Request POST Data: %s", pprint.pformat(log_data))
        else:
            log.trace("Request POST Data: %s", pprint.pformat(data))

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
        cookie_jar = os.path.join(
            opts.get("cachedir", salt.syspaths.CACHE_DIR), "cookies.txt"
        )
    if session_cookie_jar is None:
        session_cookie_jar = os.path.join(
            opts.get("cachedir", salt.syspaths.CACHE_DIR), "cookies.session.p"
        )

    if persist_session is True and salt.utils.msgpack.HAS_MSGPACK:
        # TODO: This is hackish; it will overwrite the session cookie jar with
        # all cookies from this one connection, rather than behaving like a
        # proper cookie jar. Unfortunately, since session cookies do not
        # contain expirations, they can't be stored in a proper cookie jar.
        if os.path.isfile(session_cookie_jar):
            with salt.utils.files.fopen(session_cookie_jar, "rb") as fh_:
                session_cookies = salt.utils.msgpack.load(fh_)
            if isinstance(session_cookies, dict):
                header_dict.update(session_cookies)
        else:
            with salt.utils.files.fopen(session_cookie_jar, "wb") as fh_:
                salt.utils.msgpack.dump("", fh_)

    for header in header_list:
        comps = header.split(":")
        if len(comps) < 2:
            continue
        header_dict[comps[0].strip()] = comps[1].strip()

    if not auth:
        if username and password:
            auth = (username, password)

    if agent == USERAGENT:
        agent = f"{agent} http.query()"
    header_dict["User-agent"] = agent

    if (
        proxy_host
        and proxy_port
        and method == "POST"
        and "Content-Type" not in header_dict
    ):
        log.debug(
            "Content-Type not provided for POST request, assuming application/x-www-form-urlencoded"
        )
        header_dict["Content-Type"] = "application/x-www-form-urlencoded"
        if "Content-Length" not in header_dict:
            header_dict["Content-Length"] = f"{len(data)}"

    if backend == "requests":
        sess = requests.Session()
        sess.auth = auth
        sess.headers.update(header_dict)
        log.trace("Request Headers: %s", sess.headers)
        sess_cookies = sess.cookies
        sess.verify = verify_ssl
        if http_proxy_url is not None:
            sess.proxies = {
                "http": http_proxy_url,
                "https": http_proxy_url,
            }
    elif backend == "urllib2":
        sess_cookies = None
    else:
        # Tornado
        sess_cookies = None

    if cookies is not None:
        if cookie_format == "mozilla":
            sess_cookies = http.cookiejar.MozillaCookieJar(cookie_jar)
        else:
            sess_cookies = http.cookiejar.LWPCookieJar(cookie_jar)
        if not os.path.isfile(cookie_jar):
            sess_cookies.save()
        sess_cookies.load()

    if test is True:
        if test_url is None:
            return {}
        else:
            url = test_url
            ret["test"] = True

    if backend == "requests":
        req_kwargs = {}
        if stream is True:
            if requests.__version__[0] == "0":
                # 'stream' was called 'prefetch' before 1.0, with flipped meaning
                req_kwargs["prefetch"] = False
            else:
                req_kwargs["stream"] = True

        # Client-side cert handling
        if cert is not None:
            if isinstance(cert, str):
                if os.path.exists(cert):
                    req_kwargs["cert"] = cert
            elif isinstance(cert, list):
                if os.path.exists(cert[0]) and os.path.exists(cert[1]):
                    req_kwargs["cert"] = cert
            else:
                log.error(
                    "The client-side certificate path that was passed is not valid: %s",
                    cert,
                )

        if formdata:
            if not formdata_fieldname:
                ret["error"] = "formdata_fieldname is required when formdata=True"
                log.error(ret["error"])
                return ret
            result = sess.request(
                method,
                url,
                params=params,
                files={formdata_fieldname: (formdata_filename, io.StringIO(data))},
                **req_kwargs,
            )
        else:
            result = sess.request(method, url, params=params, data=data, **req_kwargs)
        result.raise_for_status()
        if stream is True:
            # fake a HTTP response header
            header_callback(f"HTTP/1.0 {result.status_code} MESSAGE")
            # fake streaming the content
            streaming_callback(result.content)
            return {
                "handle": result,
            }

        if handle is True:
            return {
                "handle": result,
                "body": result.content,
            }

        log.debug(
            "Final URL location of Response: %s", sanitize_url(result.url, hide_fields)
        )

        result_status_code = result.status_code
        result_headers = result.headers
        result_text = result.content
        result_cookies = result.cookies
        result_text = _decode_result_text(
            result_text, backend, decode_body=decode_body, result=result
        )
        ret["body"] = result_text
    elif backend == "urllib2":
        request = urllib.request.Request(url_full, data)
        handlers = [
            urllib.request.HTTPHandler,
            urllib.request.HTTPCookieProcessor(sess_cookies),
        ]

        if url.startswith("https"):
            hostname = request.get_host()
            handlers[0] = urllib.request.HTTPSHandler(1)
            if not HAS_MATCHHOSTNAME:
                log.warning(
                    "match_hostname() not available, SSL hostname checking "
                    "not available. THIS CONNECTION MAY NOT BE SECURE!"
                )
            elif verify_ssl is False:
                log.warning(
                    "SSL certificate verification has been explicitly "
                    "disabled. THIS CONNECTION MAY NOT BE SECURE!"
                )
            else:
                if ":" in hostname:
                    hostname, port = hostname.split(":")
                else:
                    port = 443
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((hostname, int(port)))
                sockwrap = ssl.wrap_socket(
                    sock, ca_certs=ca_bundle, cert_reqs=ssl.CERT_REQUIRED
                )
                try:
                    match_hostname(sockwrap.getpeercert(), hostname)
                except CertificateError as exc:
                    ret["error"] = (
                        "The certificate was invalid. Error returned was: {}".format(
                            pprint.pformat(exc)
                        )
                    )
                    return ret

                # Client-side cert handling
                if cert is not None:
                    cert_chain = None
                    if isinstance(cert, str):
                        if os.path.exists(cert):
                            cert_chain = cert
                    elif isinstance(cert, list):
                        if os.path.exists(cert[0]) and os.path.exists(cert[1]):
                            cert_chain = cert
                    else:
                        log.error(
                            "The client-side certificate path that was "
                            "passed is not valid: %s",
                            cert,
                        )
                        return
                    if hasattr(ssl, "SSLContext"):
                        # Python >= 2.7.9
                        context = ssl.SSLContext.load_cert_chain(*cert_chain)
                        handlers.append(
                            urllib.request.HTTPSHandler(context=context)
                        )  # pylint: disable=E1123
                    else:
                        # Python < 2.7.9
                        cert_kwargs = {
                            "host": request.get_host(),
                            "port": port,
                            "cert_file": cert_chain[0],
                        }
                        if len(cert_chain) > 1:
                            cert_kwargs["key_file"] = cert_chain[1]
                        handlers[0] = http.client.HTTPSConnection(**cert_kwargs)

        opener = urllib.request.build_opener(*handlers)
        for header in header_dict:
            request.add_header(header, header_dict[header])
        request.get_method = lambda: method
        try:
            result = opener.open(request)
        except urllib.error.URLError as exc:
            return {"Error": str(exc)}
        if stream is True or handle is True:
            return {
                "handle": result,
                "body": result.content,
            }

        result_status_code = result.code
        result_headers = dict(result.info())
        result_text = result.read()
        result_text, result_headers = _decode_result(
            result_text, result_headers, backend, decode_body=decode_body, result=result
        )
        ret["body"] = result_text
    else:
        # Tornado
        req_kwargs = {}

        # Client-side cert handling
        if cert is not None:
            if isinstance(cert, str):
                if os.path.exists(cert):
                    req_kwargs["client_cert"] = cert
            elif isinstance(cert, list):
                if os.path.exists(cert[0]) and os.path.exists(cert[1]):
                    req_kwargs["client_cert"] = cert[0]
                    req_kwargs["client_key"] = cert[1]
            else:
                log.error(
                    "The client-side certificate path that was passed is not valid: %s",
                    cert,
                )

        if isinstance(data, dict):
            data = urllib.parse.urlencode(data)

        if verify_ssl:
            req_kwargs["ca_certs"] = ca_bundle

        max_body = opts.get(
            "http_max_body", salt.config.DEFAULT_MINION_OPTS["http_max_body"]
        )
        connect_timeout = opts.get(
            "http_connect_timeout",
            salt.config.DEFAULT_MINION_OPTS["http_connect_timeout"],
        )
        timeout = opts.get(
            "http_request_timeout",
            salt.config.DEFAULT_MINION_OPTS["http_request_timeout"],
        )

        AsyncHTTPClient.configure(None)
        client_argspec = salt.utils.args.get_function_argspec(
            tornado.simple_httpclient.SimpleAsyncHTTPClient.initialize
        )

        supports_max_body_size = "max_body_size" in client_argspec.args

        req_kwargs.update(
            {
                "method": method,
                "headers": header_dict,
                "auth_username": username,
                "auth_password": password,
                "body": data,
                "validate_cert": verify_ssl,
                "allow_nonstandard_methods": True,
                "streaming_callback": streaming_callback,
                "header_callback": header_callback,
                "connect_timeout": connect_timeout,
                "request_timeout": timeout,
                "raise_error": raise_error,
                "decompress_response": False,
            }
        )

        # Unicode types will cause a TypeError when Tornado's curl HTTPClient
        # invokes setopt. Therefore, make sure all arguments we pass which
        # contain strings are str types.
        req_kwargs = salt.utils.data.decode(req_kwargs, to_str=True)

        try:
            download_client = SyncWrapper(
                AsyncHTTPClient,
                kwargs={"max_body_size": max_body} if supports_max_body_size else {},
                async_methods=["fetch"],
            )
            result = download_client.fetch(url_full, **req_kwargs)
        except tornado.httpclient.HTTPError as exc:
            ret["status"] = exc.code
            ret["error"] = str(exc)
            ret["body"], _ = _decode_result(
                exc.response.body,
                exc.response.headers,
                backend,
                decode_body=decode_body,
            )
            return ret
        except (socket.herror, OSError, socket.timeout, socket.gaierror) as exc:
            if status is True:
                ret["status"] = 0
            ret["error"] = str(exc)
            log.debug("Cannot perform 'http.query': %s - %s", url_full, ret["error"])
            return ret

        if stream is True or handle is True:
            return {
                "handle": result,
                "body": result.body,
            }

        result_status_code = result.code
        result_headers = result.headers
        result_text = result.body
        result_text, result_headers = _decode_result(
            result_text, result_headers, backend, decode_body=decode_body, result=result
        )
        ret["body"] = result_text
        if "Set-Cookie" in result_headers and cookies is not None:
            result_cookies = parse_cookie_header(result_headers["Set-Cookie"])
            for item in result_cookies:
                sess_cookies.set_cookie(item)
        else:
            result_cookies = None

    if isinstance(result_headers, list):
        result_headers_dict = {}
        for header in result_headers:
            comps = header.split(":")
            result_headers_dict[comps[0].strip()] = ":".join(comps[1:]).strip()
        result_headers = result_headers_dict

    log.debug("Response Status Code: %s", result_status_code)
    log.trace("Response Headers: %s", result_headers)
    log.trace("Response Cookies: %s", sess_cookies)
    # log.trace("Content: %s", result_text)

    coding = result_headers.get("Content-Encoding", "identity")

    # Requests will always decompress the content, and working around that is annoying.
    if backend != "requests":
        result_text = __decompressContent(coding, result_text)

    try:
        log.trace("Response Text: %s", result_text)
    except UnicodeEncodeError as exc:
        log.trace(
            "Cannot Trace Log Response Text: %s. This may be due to "
            "incompatibilities between requests and logging.",
            exc,
        )

    if text_out is not None:
        with salt.utils.files.fopen(text_out, "w") as tof:
            tof.write(result_text)

    if headers_out is not None and os.path.exists(headers_out):
        with salt.utils.files.fopen(headers_out, "w") as hof:
            hof.write(result_headers)

    if cookies is not None:
        sess_cookies.save()

    if persist_session is True and salt.utils.msgpack.HAS_MSGPACK:
        # TODO: See persist_session above
        if "set-cookie" in result_headers:
            with salt.utils.files.fopen(session_cookie_jar, "wb") as fh_:
                session_cookies = result_headers.get("set-cookie", None)
                if session_cookies is not None:
                    salt.utils.msgpack.dump({"Cookie": session_cookies}, fh_)
                else:
                    salt.utils.msgpack.dump("", fh_)

    if status is True:
        ret["status"] = result_status_code

    if headers is True:
        ret["headers"] = result_headers

    if decode is True:
        if decode_type == "auto":
            content_type = result_headers.get("content-type", "application/json")
            if "xml" in content_type:
                decode_type = "xml"
            elif "json" in content_type:
                decode_type = "json"
            elif "yaml" in content_type:
                decode_type = "yaml"
            else:
                decode_type = "plain"

        valid_decodes = ("json", "xml", "yaml", "plain")
        if decode_type not in valid_decodes:
            ret["error"] = (
                "Invalid decode_type specified. Valid decode types are: {}".format(
                    pprint.pformat(valid_decodes)
                )
            )
            log.error(ret["error"])
            return ret

        if decode_type == "json":
            ret["dict"] = salt.utils.json.loads(result_text)
        elif decode_type == "xml":
            ret["dict"] = []
            items = ET.fromstring(result_text)
            for item in items:
                ret["dict"].append(xml.to_dict(item))
        elif decode_type == "yaml":
            ret["dict"] = salt.utils.data.decode(salt.utils.yaml.safe_load(result_text))
        else:
            text = True

        if decode_out:
            with salt.utils.files.fopen(decode_out, "w") as dof:
                dof.write(result_text)

    if text is True:
        ret["text"] = result_text

    return ret


def get_ca_bundle(opts=None):
    """
    Return the location of the ca bundle file. See the following article:

        http://tinyurl.com/k7rx42a
    """
    if hasattr(get_ca_bundle, "__return_value__"):
        return get_ca_bundle.__return_value__

    if opts is None:
        opts = {}

    opts_bundle = opts.get("ca_bundle", None)
    if opts_bundle is not None and os.path.exists(opts_bundle):
        return opts_bundle

    file_roots = opts.get("file_roots", {"base": [salt.syspaths.SRV_ROOT_DIR]})

    # Please do not change the order without good reason

    # Check Salt first
    for salt_root in file_roots.get("base", []):
        for path in ("cacert.pem", "ca-bundle.crt"):
            cert_path = os.path.join(salt_root, path)
            if os.path.exists(cert_path):
                return cert_path

    locations = (
        # Debian has paths that often exist on other distros
        "/etc/ssl/certs/ca-certificates.crt",
        # RedHat is also very common
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/pki/tls/certs/ca-bundle.trust.crt",
        # RedHat's link for Debian compatibility
        "/etc/ssl/certs/ca-bundle.crt",
        # SUSE has an unusual path
        "/var/lib/ca-certificates/ca-bundle.pem",
        # OpenBSD has an unusual path
        "/etc/ssl/cert.pem",
    )
    for path in locations:
        if os.path.exists(path):
            return path

    if salt.utils.platform.is_windows() and HAS_CERTIFI:
        return certifi.where()

    return None


def update_ca_bundle(
    target=None,
    source=None,
    opts=None,
    merge_files=None,
):
    """
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
    """
    if opts is None:
        opts = {}

    if target is None:
        target = get_ca_bundle(opts)

    if target is None:
        log.error("Unable to detect location to write CA bundle to")
        return

    if source is None:
        source = opts.get("ca_bundle_url", "http://curl.haxx.se/ca/cacert.pem")

    log.debug("Attempting to download %s to %s", source, target)
    query(source, text=True, decode=False, headers=False, status=False, text_out=target)

    if merge_files is not None:
        if isinstance(merge_files, str):
            merge_files = [merge_files]

        if not isinstance(merge_files, list):
            log.error(
                "A value was passed as merge_files which was not either "
                "a string or a list"
            )
            return

        merge_content = ""

        for cert_file in merge_files:
            if os.path.exists(cert_file):
                log.debug("Queueing up %s to be appended to %s", cert_file, target)
                try:
                    with salt.utils.files.fopen(cert_file, "r") as fcf:
                        merge_content = "\n".join((merge_content, fcf.read()))
                except OSError as exc:
                    log.error(
                        "Reading from %s caused the following error: %s", cert_file, exc
                    )

        if merge_content:
            log.debug("Appending merge_files to %s", target)
            try:
                with salt.utils.files.fopen(target, "a") as tfp:
                    tfp.write("\n")
                    tfp.write(merge_content)
            except OSError as exc:
                log.error("Writing to %s caused the following error: %s", target, exc)


def _render(template, render, renderer, template_dict, opts):
    """
    Render a template
    """
    if render:
        if template_dict is None:
            template_dict = {}
        if not renderer:
            renderer = opts.get("renderer", "jinja|yaml")
        rend = salt.loader.render(opts, {})
        blacklist = opts.get("renderer_blacklist")
        whitelist = opts.get("renderer_whitelist")
        ret = compile_template(
            template, rend, renderer, blacklist, whitelist, **template_dict
        )
        if salt.utils.stringio.is_readable(ret):
            ret = ret.read()
        if str(ret).startswith("#!") and not str(ret).startswith("#!/"):
            ret = str(ret).split("\n", 1)[1]
        return ret
    with salt.utils.files.fopen(template, "r") as fh_:
        return fh_.read()


def parse_cookie_header(header):
    """
    Parse the "Set-cookie" header, and return a list of cookies.

    This function is here because Tornado's HTTPClient doesn't handle cookies.
    """
    attribs = (
        "expires",
        "path",
        "domain",
        "version",
        "httponly",
        "secure",
        "comment",
        "max-age",
        "samesite",
    )

    # Split into cookie(s); handles headers with multiple cookies defined
    morsels = []
    for item in header.split(";"):
        item = item.strip()
        if "," in item and "expires" not in item:
            for part in item.split(","):
                morsels.append(part)
        else:
            morsels.append(item)

    # Break down morsels into actual cookies
    cookies = []
    cookie = {}
    value_set = False
    for morsel in morsels:
        parts = morsel.split("=")
        parts[0] = parts[0].lower()
        if parts[0] in attribs:
            if parts[0] in cookie:
                cookies.append(cookie)
                cookie = {}
            if len(parts) > 1:
                cookie[parts[0]] = "=".join(parts[1:])
            else:
                cookie[parts[0]] = True
        else:
            if value_set is True:
                # This is a new cookie; save the old one and clear for this one
                cookies.append(cookie)
                cookie = {}
                value_set = False
            cookie[parts[0]] = "=".join(parts[1:])
            value_set = True

    if cookie:
        # Set the last cookie that was processed
        cookies.append(cookie)

    # These arguments are required by cookielib.Cookie()
    reqd = (
        "version",
        "port",
        "port_specified",
        "domain",
        "domain_specified",
        "domain_initial_dot",
        "path",
        "path_specified",
        "secure",
        "expires",
        "discard",
        "comment",
        "comment_url",
        "rest",
    )

    ret = []
    for cookie in cookies:
        name = None
        value = None
        for item in list(cookie):
            if item in attribs:
                continue
            name = item
            value = cookie.pop(item)

        # cookielib.Cookie() requires an epoch
        if "expires" in cookie:
            cookie["expires"] = http.cookiejar.http2time(cookie["expires"])

        # Fill in missing required fields
        for req in reqd:
            if req not in cookie:
                cookie[req] = ""
        if cookie["version"] == "":
            cookie["version"] = 0
        if cookie["rest"] == "":
            cookie["rest"] = {}
        if cookie["expires"] == "":
            cookie["expires"] = 0

        # Remove attribs that don't apply to Cookie objects
        cookie.pop("httponly", None)
        cookie.pop("samesite", None)
        ret.append(http.cookiejar.Cookie(name=name, value=value, **cookie))

    return ret


def sanitize_url(url, hide_fields):
    """
    Make sure no secret fields show up in logs
    """
    if isinstance(hide_fields, list):
        url_comps = urllib.parse.splitquery(url)
        log_url = url_comps[0]
        if len(url_comps) > 1:
            log_url += "?"
        for pair in url_comps[1:]:
            url_tmp = None
            for field in hide_fields:
                comps_list = pair.split("&")
                if url_tmp:
                    url_tmp = url_tmp.split("&")
                    url_tmp = _sanitize_url_components(url_tmp, field)
                else:
                    url_tmp = _sanitize_url_components(comps_list, field)
            log_url += url_tmp
        return log_url.rstrip("&")
    else:
        return str(url)


def _sanitize_url_components(comp_list, field):
    """
    Recursive function to sanitize each component of the url.
    """
    if not comp_list:
        return ""
    elif comp_list[0].startswith(f"{field}="):
        ret = f"{field}=XXXXXXXXXX&"
        comp_list.remove(comp_list[0])
        return ret + _sanitize_url_components(comp_list, field)
    else:
        ret = f"{comp_list[0]}&"
        comp_list.remove(comp_list[0])
        return ret + _sanitize_url_components(comp_list, field)


def session(user=None, password=None, verify_ssl=True, ca_bundle=None, headers=None):
    """
    create a requests session
    """
    session = requests.session()
    if user and password:
        session.auth = (user, password)
    if ca_bundle and not verify_ssl:
        log.error("You cannot use both ca_bundle and verify_ssl False together")
        return False
    if ca_bundle:
        opts = {"ca_bundle": ca_bundle}
        session.verify = get_ca_bundle(opts)
    if not verify_ssl:
        session.verify = False
    if headers:
        session.headers.update(headers)
    return session
