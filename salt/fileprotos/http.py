# -*- coding: utf-8 -*-
'''
HTTP Client Module Directory
'''
from __future__ import unicode_literals

# Import salt Libraries
from salt.exceptions import MinionError

# Import salt ext Libraries
from salt.ext.six.moves.urllib.error import HTTPError, URLError

__virtualname__ = 'http'
__virtual_aliases__ = ('https')


def __virtual__():
    return __virtualname__


def needscache():
    '''
    Need cache setup for this driver
    '''
    return True


def get(url, dest, no_cache=False, **kwargs):
    '''
    Get file from http or https
    '''
    url_data, _, _ = __salt__['cp.get_url_data'](url)
    get_kwargs = {}
    if url_data.username is not None \
            and url_data.scheme in ('http', 'https'):
        netloc = url_data.netloc
        at_sign_pos = netloc.rfind('@')
        if at_sign_pos != -1:
            netloc = netloc[at_sign_pos + 1:]
        fixed_url = urlunparse(
            (url_data.scheme, netloc, url_data.path,
             url_data.params, url_data.query, url_data.fragment))
        get_kwargs['auth'] = (url_data.username, url_data.password)
    else:
        fixed_url = url

    destfp = None
    try:
        # Tornado calls streaming_callback on redirect response bodies.
        # But we need streaming to support fetching large files (> RAM
        # avail). Here we are working around this by disabling recording
        # the body for redirections. The issue is fixed in Tornado 4.3.0
        # so on_header callback could be removed when we'll deprecate
        # Tornado<4.3.0. See #27093 and #30431 for details.

        # Use list here to make it writable inside the on_header callback.
        # Simple bool doesn't work here: on_header creates a new local
        # variable instead. This could be avoided in Py3 with 'nonlocal'
        # statement. There is no Py2 alternative for this.
        #
        # write_body[0] is used by the on_chunk callback to tell it whether
        #   or not we need to write the body of the request to disk. For
        #   30x redirects we set this to False because we don't want to
        #   write the contents to disk, as we will need to wait until we
        #   get to the redirected URL.
        #
        # write_body[1] will contain a tornado.httputil.HTTPHeaders
        #   instance that we will use to parse each header line. We
        #   initialize this to False, and after we parse the status line we
        #   will replace it with the HTTPHeaders instance. If/when we have
        #   found the encoding used in the request, we set this value to
        #   False to signify that we are done parsing.
        #
        # write_body[2] is where the encoding will be stored
        write_body = [None, False, None]

        def on_header(hdr):
            if write_body[1] is not False and write_body[2] is None:
                if not hdr.strip() and 'Content-Type' not in write_body[1]:
                    # If write_body[0] is True, then we are not following a
                    # redirect (initial response was a 200 OK). So there is
                    # no need to reset write_body[0].
                    if write_body[0] is not True:
                        # We are following a redirect, so we need to reset
                        # write_body[0] so that we properly follow it.
                        write_body[0] = None
                    # We don't need the HTTPHeaders object anymore
                    write_body[1] = False
                    return
                # Try to find out what content type encoding is used if
                # this is a text file
                write_body[1].parse_line(hdr)  # pylint: disable=no-member
                if 'Content-Type' in write_body[1]:
                    content_type = write_body[1].get('Content-Type')  # pylint: disable=no-member
                    if not content_type.startswith('text'):
                        write_body[1] = write_body[2] = False
                    else:
                        encoding = 'utf-8'
                        fields = content_type.split(';')
                        for field in fields:
                            if 'encoding' in field:
                                encoding = field.split('encoding=')[-1]
                        write_body[2] = encoding
                        # We have found our encoding. Stop processing headers.
                        write_body[1] = False

                    # If write_body[0] is False, this means that this
                    # header is a 30x redirect, so we need to reset
                    # write_body[0] to None so that we parse the HTTP
                    # status code from the redirect target. Additionally,
                    # we need to reset write_body[2] so that we inspect the
                    # headers for the Content-Type of the URL we're
                    # following.
                    if write_body[0] is write_body[1] is False:
                        write_body[0] = write_body[2] = None

            # Check the status line of the HTTP request
            if write_body[0] is None:
                try:
                    hdr = parse_response_start_line(hdr)
                except HTTPInputError:
                    # Not the first line, do nothing
                    return
                write_body[0] = hdr.code not in [301, 302, 303, 307]
                write_body[1] = HTTPHeaders()

        if no_cache:
            result = []

            def on_chunk(chunk):
                if write_body[0]:
                    if write_body[2]:
                        chunk = chunk.decode(write_body[2])
                    result.append(chunk)
        else:
            dest_tmp = u"{0}.part".format(dest)
            # We need an open filehandle to use in the on_chunk callback,
            # that's why we're not using a with clause here.
            destfp = __utils__['files.fopen'](dest_tmp, 'wb')  # pylint: disable=resource-leakage

            def on_chunk(chunk):
                if write_body[0]:
                    destfp.write(chunk)

        query = __utils__['http.query'](
            fixed_url,
            stream=True,
            streaming_callback=on_chunk,
            header_callback=on_header,
            username=url_data.username,
            password=url_data.password,
            opts=self.opts,
            **get_kwargs
        )
        if 'handle' not in query:
            raise MinionError('Error: {0} reading {1}'.format(query['error'], url))
        if no_cache:
            if write_body[2]:
                return ''.join(result)
            return b''.join(result)
        else:
            destfp.close()
            destfp = None
            __utils__['files.rename'](dest_tmp, dest)
            return dest
    except HTTPError as exc:
        raise MinionError('HTTP error {0} reading {1}: {3}'.format(
            exc.code,
            url,
            *BaseHTTPServer.BaseHTTPRequestHandler.responses[exc.code]))
    except URLError as exc:
        raise MinionError('Error reading {0}: {1}'.format(url, exc.reason))
    finally:
        if destfp is not None:
            destfp.close()
