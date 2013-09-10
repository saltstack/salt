#!/usr/local/bin/python2.7

''' Runs wsgi web server using bottle framework
    
    To get usage
    
    $ python server_bottle.py -h
    
    Runs embedded wsgi server when run directly as __main__.
    The server is at http://localhost:port or http://127.0.0.1:port
    The default port is 8080
    The root path is http://localhost:port
    and routes below are relative to this root path so
    "/" is http://localhost:port/
     
'''
import sys
import os
import time
import datetime
import hashlib

try:
    import simplejson as json
except ImportError as ex:
    import json

import aiding

gevented = False

logger = aiding.getLogger(name="Bottle")

# Web application specific static files
STATIC_APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app')

# Third party static web libraries
STATIC_LIB_PATH =  os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')



def loadWebUI(app):
    ''' Load endpoints for bottle app'''
        
    #catch all for page refreshes of any app url
    @app.route('/app/<path:path>') # /app/<path>
    @app.route('/app/') # /app/
    @app.route('/app') # /app
    @app.route('/') # /
    def appGet(path=''):
        return bottle.static_file('main.html', root=STATIC_APP_PATH)
    
    @app.route('/static/lib/<filepath:re:.*\.(woff)>')
    def staticFontWoffGet(filepath):
        return bottle.static_file(filepath, root=STATIC_LIB_PATH, mimetype='application/font-woff')    
        
    @app.route('/static/app/<filepath:path>')
    def staticAppGet(filepath):
        return bottle.static_file(filepath, root=STATIC_APP_PATH)
    
    @app.route('/static/lib/<filepath:path>')
    def staticLibGet(filepath):
        return bottle.static_file(filepath, root=STATIC_LIB_PATH)
    
    @app.get('/test') 
    def testGet():
        '''
        Test endpoint for bottle application
        Shows location of this file
        Shows all routes in current bottle app
        '''
        bottle.response.set_header('content-type', 'text/plain')
        content =  "Web app file is located at %s" % os.path.dirname(os.path.abspath(__file__))
        siteMap = ""
        
        currentApp = bottle.app()
        
        for route in currentApp.routes:
            siteMap = "%s%s%s %s" %  (siteMap, '\n' if siteMap else '', route.rule, route.method)
            target = route.config.get('mountpoint', {}).get('target')
            if target:
                for way in target.routes:
                    siteMap = "%s\n    %s %s" %  (siteMap, way.rule, way.method)
                    
        content = "%s\n%s" %  (content, siteMap)
        return content
    
    
    @app.get('/echo')
    @app.get('/echo/<action>')
    def echoGet(action=None):
        '''
        Ajax test endpoint for web application service
        Echos back query args and content
        '''
        #convert to json serializible dict
        query = { key: val for key, val in bottle.request.query.items()}
        
        data = dict(verb='GET',
                    url=bottle.request.url,
                    action=action,
                    query=query,
                    content=bottle.request.json)
    
        return data
    
    @app.get('/ping') 
    def pingGet():
        ''' Send salt ping'''
        import salt.client
        import salt.config
        __opts__ = salt.config.client_config(
                    os.environ.get('SALT_MASTER_CONFIG', '/etc/salt/master'))
        local = salt.client.LocalClient(__opts__['conf_file'])
        local.cmd('*', 'test.ping',  username="saltwui", password='dissolve', eauth='pam')
        
        return dict(result = "Sent Ping")
    
    @app.get('/stream')
    def streamGet():
        ''' Create server sent event stream with counter'''
        bottle.response.set_header('Content-Type',  'text/event-stream') #text
        bottle.response.set_header('Cache-Control',  'no-cache')
        # Set client-side auto-reconnect timeout, ms.
        yield 'retry: 1000\n\n'
        yield 'data: START\n\n'
        n = 1
        end = time.time() + 600 # Keep connection alive no more then... (s)
        while time.time() < end:
            yield 'data: %i\n\n' % n
            n += 1
            gevent.sleep(1.0) if gevented else time.sleep(1.0)
            
        yield "data: END\n\n"
        
def tokenify(cmd, token=None):
    '''
    If token is not None Then assign token to 'token' key of dict cmd and return cmd
    Otherwise return cmd
    '''
    if token is not None:
        cmd['token'] = token
    return cmd

def loadSaltApi(app):
    ''' Load endpoints for Salt-API '''
    from salt.exceptions import EauthAuthenticationError
    import salt.client.api
    
    sleep = gevent.sleep if gevented else time.sleep
    
    @app.post('/login') 
    def loginPost():
        ''' Login and respond with login credentials'''
        data = bottle.request.json
        if not data:
            bottle.abort(400, "Login data missing.")        
        
        creds = dict(username=data.get("username"),
                     password=data.get("password"),
                     eauth=data.get("eauth"))
        
        client = salt.client.api.APIClient()
        try:
            creds = client.create_token(creds)
        except EauthAuthenticationError as ex:
            bottle.abort(401, text=repr(ex))
            
        bottle.response.set_header('X-Auth-Token', creds['token'])
        return {"return": [creds]} 
    
    @app.post('/logout') 
    def logoutPost():
        '''
        Logout
        {return: "Logout suceeded."}
        '''
        token = bottle.request.get_header('X-Auth-Token')
        if token:
            result = {"return": "Logout suceeded."}
        else:
            result = {}
        return result
    
    @app.post(['/signature', '/signature/<token>'])
    def signaturePost(token = None):
        '''
        Fetch module function signature(s) with either credentials in post data
        or token from url or token from X-Auth-Token header
        '''
        if not token:
            token = bottle.request.get_header('X-Auth-Token')
        
        cmds = bottle.request.json
        if not cmds:
            bottle.abort(code=400, text='Missing command(s).')
            
        if hasattr(cmds, 'get'): #convert to array
            cmds =  [cmds]
        
        client = salt.client.api.APIClient()
        try:
            results = [client.signature(tokenify(cmd, token)) for cmd in cmds]
        except EauthAuthenticationError as ex:
            bottle.abort(code=401, text=repr(ex))
        except Exception as ex:
            bottle.abort(code=400, text=repr(ex))            
            
        return {"return": results}
    
    @app.post(['/run', '/run/<token>'])
    def runPost(token = None):
        '''
        Execute salt command with either credentials in post data
        or token from url or token from X-Auth-Token headertoken 
        '''
        if not token:
            token = bottle.request.get_header('X-Auth-Token')
        
        cmds = bottle.request.json
        if not cmds:
            bottle.abort(code=400, text='Missing command(s).')
            
        if hasattr(cmds, 'get'): #convert to array
            cmds =  [cmds]
        
        client = salt.client.api.APIClient()
        try:
            results = [client.run(tokenify(cmd, token)) for cmd in cmds]
        except EauthAuthenticationError as ex:
            bottle.abort(code=401, text=repr(ex))
        except Exception as ex:
            bottle.abort(code=400, text=repr(ex))            
            
        return {"return": results}   
        
    @app.get('/event/<token>')
    def eventGet(token):
        '''
        Create server sent event stream from salt
        and authenticate with the given token
        Also optional query arg tag allows with
        filter events based on tag
        '''
        if not token:
            bottle.abort(401, "Missing token.")
        
        client = salt.client.api.APIClient()
        
        if not client.verify_token(token): #auth.get_tok(token):
            bottle.abort(401, "Invalid token.")
            
        tag = bottle.request.query.get('tag', '')
        
        bottle.response.set_header('Content-Type',  'text/event-stream') #text
        bottle.response.set_header('Cache-Control',  'no-cache')
    
        # Set client-side auto-reconnect timeout, ms.
        yield 'retry: 250\n\n'
    
        while True:
            data =  client.get_event(wait=0.025, tag=tag, full=True)
            if data:
                yield 'data: {0}\n\n'.format(json.dumps(data))
            else:
                sleep(0.1)
             
    @app.post(['/fire', '/fire/<token>'])
    def firePost(token=None):
        '''
        Fire event(s)
        Each event is a dict of the form
        {
          tag: 'tagstring',
          data: {datadict},
        }
        Post body is either list of events or single event
        '''
        if not token:
            token = bottle.request.get_header('X-Auth-Token')        
        if not token:
            bottle.abort(401, "Missing token.")
        
        client = salt.client.api.APIClient()
        
        if not client.verify_token(token): #auth.get_tok(token):
            bottle.abort(401, "Invalid token.")
        
        events = bottle.request.json
        if not events:
            bottle.abort(code=400, text='Missing event(s).')
        
        if hasattr(events, 'get'): #convert to list if not
            events = [events]
        
        results = [dict(tag=event['tag'],
                        result=client.fire_event(event['data'], event['tag']))
                   for event in events]
        
        bottle.response.set_header('Content-Type',  'application/json')
        return json.dumps(results)
        
    return app

def loadCors(app):
    '''
    Load support for CORS Cross Origin Resource Sharing
    '''
    corsRoutes = ['/login', '/logout',
                  '/signature', '/signature/<token>', 
                  '/run', 'run/<token>',
                  '/event/<token>',
                  '/fire', '/fire/<token>'
                  ]
    
    @app.hook('after_request')
    def enableCors():
        '''
        Add CORS headers to each response
        Don't use the wildcard '*' for Access-Control-Allow-Origin in production.
        '''
        #bottle.response.set_header('Access-Control-Allow-Credentials', 'true')
        bottle.response.set_header('Access-Control-Max-Age:', '3600')
        bottle.response.set_header('Access-Control-Allow-Origin', '*')
        bottle.response.set_header('Access-Control-Allow-Methods',
                            'PUT, GET, POST, DELETE, OPTIONS')
        bottle.response.set_header('Access-Control-Allow-Headers', 
            'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, X-Auth-Token')
    
    @app.route(corsRoutes, method='OPTIONS')
    def allowOption(path=None):
        '''
        Respond to OPTION request method
        '''
        return {}
    
    return app

def loadErrors(app):
    '''
    Load decorated Error functions for bottle web application
    Error functions do not automatically jsonify dicts so must manually do so.
    '''

    @app.error(400)
    def error400(ex):
        bottle.response.set_header('content-type', 'application/json')
        return json.dumps(dict(error=ex.body))
    
    @app.error(401)
    def error401(ex):
        bottle.response.set_header('content-type', 'application/json')
        return json.dumps(dict(error=ex.body))    
    
    @app.error(404)
    def error404(ex):
        ''' Use json 404 if request accepts json otherwise use html'''
        if 'application/json' not in bottle.request.get_header('Accept', ""):
            bottle.response.set_header('content-type', 'text/html')
            return bottle.tonat(bottle.template(bottle.ERROR_PAGE_TEMPLATE, e=ex))
        
        bottle.response.set_header('content-type', 'application/json')    
        return json.dumps(dict(error=ex.body))
    
    @app.error(405)
    def error405(ex):
        bottle.response.set_header('content-type', 'application/json')
        return json.dumps(dict(error=ex.body))
    
    @app.error(409)
    def error409(ex):
        bottle.response.set_header('content-type', 'application/json')
        return json.dumps(dict(error=ex.body))

def remount(base):
    '''
    Remount current app to new app at base mountpoint such as '/demo'
    This enables different root path such as required by web server proxy
    '''
    if not base: # no remount needed
        return bottle.app()
    oldApp = bottle.app.pop() # remove current app
    newApp = bottle.app.push() # create new app
    newApp.mount(base, oldApp) # remount old on new path
    return newApp

def rebase(base):
    ''' Create new app using current app routes prefixed with base'''
    if not base: #no rebase needed
        return bottle.app()
    
    oldApp = bottle.app.pop()
    newApp = bottle.app.push()
    for route in oldApp.routes:
        route.rule = "{0}{1}".format(base, route.rule)
        newApp.add_route(route)
        route.reset() #reapply plugins on next call
    return newApp

def startServer(level='info',
                server='paste',
                host='0.0.0.0',
                port='8080',
                base='',
                cors=False, 
                tls=False, 
                certpath='/etc/pki/tls/certs/localhost.crt',
                keypath='/etc/pki/tls/certs/localhost.key',
                pempath='/etc/pki/tls/certs/localhost.pem',
                **kwas
                ):
    '''
    Starts up and runs web application server and salt api server
    Parameters:
        level = logging level string, default is 'info'
        server = server name string, default is 'paste'
        host = host address or domain name string, default is '0.0.0.0'
        port = port number string, default is '8080'
        base = url path base prefix string, default is ''
        cors = enable CORS if truthy, default is False
        tls = use tls/ssl if Truthy, default is False
        certpath = pathname string to ssl certificate file, default is
                   '/etc/pki/tls/certs/localhost.crt'
        keypath = pathname string to ssl private key file, default is
                   '/etc/pki/tls/certs/localhost.key'
        pempath = pathname string to ssl pem file with both cert and private key,
                   default is '/etc/pki/tls/certs/localhost.pem'
        kwas = additional keyword arguments dict that are passed as server options           
    Does not return.
    '''
    #so when using gevent can monkey patch before import bottle
    global gevented, gevent, bottle 
    
    logger.setLevel(aiding.LOGGING_LEVELS[level])
    gevented = False
    if server in ['gevent']:
        try:
            import gevent
            from gevent import monkey
            monkey.patch_all()
            gevented = True
        except ImportError as ex: #gevent support not available
            args.server = 'paste' # use default server
    
    tlsOptions = {}
    tlsOptions['paste'] = {'ssl_pem': pempath}
    tlsOptions['gevent'] = {'keyfile': keypath, 'certfile': certpath}
    tlsOptions['cherrypy'] = {'keyfile': keypath, 'certfile': certpath}
    
    options = dict(**kwas)
    if tls and args.server in tlsOptions:
        options.update(**tlsOptions[args.server]) # retrieve ssl options for server
    
    import bottle
    
    app = bottle.default_app() # create bottle app
    
    loadErrors(app)
    loadWebUI(app)
    loadSaltApi(app)
    if cors:
        loadCors(app)
    app = rebase(base=base)
    
    logger.info("Running web application server '{0}' on {1}:{2}.".format(
        server, host, port))
    
    if base:
        logger.info("URL paths rebased after base '{0}".format(base))
    logger.info("CORS is {0}.".format('enabled' if cors else 'disabled'))
    logger.info("TLS/SSL is {0}.".format('enabled' if tls else 'disabled'))
    logger.info("Server options: \n{0}".format(options))
     
    bottle.run( app=app,
                server=server,
                host=host,
                port=port,
                debug=True, 
                reloader=False, 
                interval=1,
                quiet=False,
                **options)    


def parseArgs():
    '''
    Process command line args using argparse or if not available the optparse
       in a backwards compatible way
       
    Returns tuple of (args, remnants) where args is object with attributes
       corresponding to named arguments and remnants is list of remaining
       unnamed positional arguments
    '''
    
    try: # make backwards compatible with deprecated optparse
        from argparse import ArgumentParser as Parser
        Parser.add = Parser.add_argument
        Parser.add_group =  Parser.add_argument_group
        Parser.parse = Parser.parse_known_args
    except ImportError as ex:
        from optparse import OptionParser as Parser
        Parser.add =  Parser.add_option
        Parser.add_group = Parser.add_option_group
        Parser.parse =  Parser.parse_args
    
    d = "Runs localhost web application wsgi service on given host address and port. "
    d += "\nDefault host:port is 0.0.0.0:8080."
    d += "\n(0.0.0.0 is any interface on localhost)"
    p = Parser(description = d)
    p.add('-l','--level',
            action='store',
            default='info',
            choices=aiding.LOGGING_LEVELS.keys(),
            help="Logging level.")
    p.add('-s','--server', 
            action = 'store',
            default='paste',
            help = "Web application WSGI server type.")
    p.add('-a','--host', 
            action = 'store',
            default='0.0.0.0',
            help = "Web application WSGI server ip host address.")
    p.add('-p','--port', 
            action = 'store',
            default='8080',
            help = "Web application WSGI server ip port.")    
    p.add('-b','--base',
            action = 'store',
            default = '',
            help = "Base Url path prefix for client side web application.")
    p.add('-x','--cors',
            action = 'store_true',
            default = False,
            help = "Enable CORS Cross Origin Resource Sharing on server.")    
    p.add('-t','--tls',
            action = 'store_true',
            default = False,
            help = "Use TLS/SSL (https).")
    p.add('-c','--cert',
            action = 'store',
            default = '/etc/pki/tls/certs/localhost.crt',
            help = "File path to tls/ssl cacert certificate file.")
    p.add('-k','--key',
            action = 'store',
            default = '/etc/pki/tls/certs/localhost.key',
            help = "File path to tls/ssl private key file.")
    p.add('-e','--pem',
            action = 'store',
            default = '/etc/pki/tls/certs/localhost.pem',
            help = "File path to tls/ssl pem file with both cert and key.")    
    return (p.parse())   


if __name__ == "__main__":
    '''
    Processes command line arguments and then runs web application server
    
    Invoke with '-h' command line option to get usage string
    '''
    args, remnants = parseArgs()
    startServer(level=args.level,
                server=args.server,
                host=args.host,
                port=args.port, 
                base=args.base,
                cors=args.cors,
                tls=args.tls,
                certpath=args.cert,
                keypath=args.key,
                pempath=args.pem
                 )
