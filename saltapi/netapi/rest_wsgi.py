'''
A bare WSGI app that wraps salt-api's client interfaces
'''
import errno
import json
import os

# Import salt libs
import salt
import saltapi

# HTTP response codes to response headers map
H = {
    200: '200 OK',
    400: '400 BAD REQUEST',
    401: '401 UNAUTHORIZED',
    404: '404 NOT FOUND',
    405: '405 METHOD NOT ALLOWED',
    406: '406 NOT ACCEPTABLE',
    500: '500 INTERNAL SERVER ERROR',
}

def __virtual__():
    short_name = __name__.rsplit('.')[-1]
    mod_opts = __opts__.get(short_name, {})

    if 'port' in mod_opts:
        return __name__

    return False

class HTTPError(Exception):
    '''
    A custom exception that can take action based on an HTTP error code
    '''
    def __init__(self, code, message):
        self.code = code
        Exception.__init__(self, '{0}: {1}'.format(code, message))

def mkdir_p(path):
    '''
    mkdir -p
    http://stackoverflow.com/a/600612/127816
    '''
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def read_body(environ):
    '''
    Pull the body from the request and return it
    '''
    length = environ.get('CONTENT_LENGTH', '0')
    length = 0 if length == '' else int(length)

    return environ['wsgi.input'].read(length)

def get_json(environ):
    '''
    Return the request body as JSON
    '''
    content_type = environ.get('CONTENT_TYPE', '')
    if content_type != 'application/json':
        raise HTTPError(406, 'JSON required')

    try:
        return json.loads(read_body(environ))
    except ValueError as exc:
        raise HTTPError(400, exc)

def get_headers(data, extra_headers=None):
    '''
    Takes the response data as well as any additional headers and returns a
    tuple of tuples of headers suitable for passing to start_response()
    '''
    response_headers = {
        'Content-Length': str(len(data)),
    }

    if extra_headers:
        response_headers.update(extra_headers)

    return response_headers.items()

def run_chunk(environ, lowstate):
    '''
    Expects a list of lowstate dictionaries that are executed and returned in
    order
    '''
    client = environ['SALT_APIClient']

    for chunk in lowstate:
        yield client.run(chunk)

def dispatch(environ):
    '''
    Do any path/method dispatching here and return a JSON-serializable data
    structure appropriate for the response
    '''
    method = environ['REQUEST_METHOD'].upper()

    if method == 'GET':
        return ("They found me. I don't know how, but they found me. "
                "Run for it, Marty!")
    elif method == 'POST':
        data = get_json(environ)
        return run_chunk(environ, data)
    else:
        raise HTTPError(405, 'Method Not Allowed')

def saltenviron(environ):
    '''
    Make Salt's opts dict and the APIClient available in the WSGI environ
    '''
    environ['SALT_OPTS'] = __opts__
    environ['SALT_APIClient'] = saltapi.APIClient(__opts__)

def application(environ, start_response):
    '''
    Process the request and return a JSON response. Catch errors and return the
    appropriate HTTP code.
    '''
    # Instantiate APIClient once for the whole app
    saltenviron(environ)

    # Call the dispatcher
    try:
        resp = list(dispatch(environ))
        code = 200
    except HTTPError as exc:
        code = exc.code
        resp = str(exc)
    except salt.exceptions.EauthAuthenticationError as exc:
        code = 401
        resp = str(exc)
    except Exception as exc:
        code = 500
        resp = str(exc)

    # Convert the response to JSON
    try:
        ret = json.dumps({'return': resp})
    except TypeError as exc:
        code = 500
        ret = str(exc)

    # Return the response
    start_response(H[code], get_headers(ret, {
        'Content-Type': 'application/json',
    }))
    return (ret,)

def start():
    '''
    Start simple_server()
    '''
    from wsgiref.simple_server import make_server

    short_name = __name__.rsplit('.')[-1]
    mod_opts = __opts__.get(short_name, {})

    # pylint: disable-msg=C0103
    httpd = make_server('localhost', mod_opts['port'], application)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        raise SystemExit(0)

if __name__ == '__main__':
    start()
