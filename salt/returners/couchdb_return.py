'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults.

couchdb.db:     'salt'
couchdb.url:        'http://salt:5984/'

'''
import logging
import time
import urllib2
import json

log = logging.getLogger(__name__)

# Import the required modules.
try:
    import couchdb
    HAS_COUCHDB = True
except ImportError:
    HAS_COUCHDB = False


def __virtual__():
    if not HAS_COUCHDB:
        return False
    return 'couchdb'


def _get_options():
    '''
    Get the couchdb options from salt. Apply defaults
    if required.
    '''
    server_url = __salt__['config.option']('couchdb.url')
    if not server_url:
        log.debug("Using default url.")
        server_url = "http://salt:5984/"

    db_name = __salt__['config.option']('couchdb.db')
    if not db_name:
        log.debug("Using default database.")
        db_name = "salt"

    return {"url": server_url, "db": db_name}


def _generate_doc(ret, options):
    '''
    Create a object that will be saved into the database based on
    options.
    '''

    # Create a copy of the object that we will return.
    r = ret

    # Set the ID of the document to be the JID.
    r["_id"] = ret["jid"]

    # Add a timestamp field to the document
    r["timestamp"] = time.time( )

    return r

def _request(method,url,content_type=None,_data=None):
    '''
    Makes a HTTP request. Returns the JSON parse.
    '''
    opener		= urllib2.build_opener( urllib2.HTTPHandler )
    request		= urllib2.Request( url, data=_data )
    if content_type:
        request.add_header( 'Content-Type', content_type )
    request.get_method	= lambda: method
    handler		= opener.open( request )
    return json.reads( handler.read( ) )

def returner(ret):
    '''
    Take in the return and shove it into the couchdb database.
    '''

    options = _get_options( )

    # Check to see if the database exists.
    _response = _request( "GET", options['url '] + "_all_dbs" )

    if options['db'] not in _response:

        # Make a PUT request to create the database.
        response = _request( "PUT", options['url'] + options['db'] )

        # Confirm that the response back was simple 'ok': true.
        if not hasattr( response, "ok" ) or response["ok"] != True:
            return log.error( 'Unable to create database "{0}"'.format(options['db']) )

    doc = _generate_doc(ret, options)

    _response = _request( "PUT", options['url'] + options['db'] + "/" + doc['_id'], 'application/json', doc )
    #if hasattr( _response, 'ok' ) and _response['ok'] == True:
    #    log.debug( 'Successfully added the document.' )
