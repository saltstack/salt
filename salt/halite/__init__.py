""" halite package for Salt UI client side web application 
    
    

"""
import os

def start():
    '''
    Wrapper to start up and run server. Reads in the master config and supplies
    halite parameters to configure the server.
    
    The server serves both the static content and provide
    the dynamic api to salt used by the web application. This is meant to be run
    by Salt to provide out of the box WUI capability. For different installations
    use the appropriate server executable file such as server_bottle.py
    '''

    import salt.config
    import salt.syspaths
    from . import server_bottle
    
    hopts = salt.config.client_config(
                os.environ.get(
                    'SALT_MASTER_CONFIG',
                     os.path.join(salt.syspaths.CONFIG_DIR, 'master'))).get('halite')
    print hopts
    
    kwparms = {
            'level': 'info',
            'server': 'paste',
            'host': '0.0.0.0',
            'port': '8080',
            'base': '',
            'cors': False,
            'tls': True,
            'certpath': '/etc/pki/tls/certs/localhost.crt',
            'keypath': '/etc/pki/tls/certs/localhost.key',
            'pempath': '/etc/pki/tls/certs/localhost.pem',
        }
    
    if hopts:
        for key in kwparms.keys():
            if key in hopts:
                kwparms[key] = hopts[key]
    
    print kwparms
    server_bottle.startServer(**kwparms)
                        
    

