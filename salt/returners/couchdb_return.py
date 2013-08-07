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

def __virtual__():
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
    r["timestamp"] = time.time()

    return r

def _request(method, url, content_type=None, _data=None):
    '''
    Makes a HTTP request. Returns the JSON parse.
    '''
    opener		= urllib2.build_opener(urllib2.HTTPHandler)
    request		= urllib2.Request( url, data=_data)
    if content_type:
        request.add_header('Content-Type', content_type)
    request.get_method	= lambda: method
    try:
        handler		= opener.open(request)
    except urllib2.HTTPError as e:
        return {'error': '{0}'.format(e) }
    return json.loads(handler.read())

def _ensure_views():
    '''
    Ensure that basic views exist, such as getting a list of minions.
    '''

    # Get the options so we have the URL and DB..
    options = _get_options()

    # Make a request to check if the design document exists.
    _response = _request( "GET", options['url'] + options['db'] + "/design/salt" )
    
    _new_doc = { }

    # If the document doesn't exist..
    if 'error' in _response:
        # Build _new_doc.. return with the request to PUT it.. 
        return

    return None

def returner(ret):
    '''
    Take in the return and shove it into the couchdb database.
    '''

    options = _get_options()

    # Check to see if the database exists.
    _response = _request( "GET", options['url'] + "_all_dbs" )
    if options['db'] not in _response:

        # Make a PUT request to create the database.
        _response = _request( "PUT", options['url'] + options['db'] )

        # Confirm that the response back was simple 'ok': true.
        if not 'ok' in _response or _response['ok'] != True:
            return log.error( 'Unable to create database "{0}"'.format(options['db']) )
        log.info( 'Created database "{0}"'.format(options['db']) )

    # Call _generate_doc to get a dict object of the document we're going to 
    # shove into the database.
    doc = _generate_doc(ret, options)

    # Make the actual HTTP PUT request to create the doc.
    _response = _request( "PUT", options['url'] + options['db'] + "/" + doc['_id'], 'application/json', json.dumps(doc) )

    # Santiy check regarding the response..
    if not 'ok' in _response or _response['ok'] != True:
        log.error('Unable to create document: "{0}"'.format(_response))

def get_jid(jid):
    '''
    Get the document with a given JID.
    '''
    options = _get_options()
    _response = _request( "GET", options['url'] + options['db'] + '/' + jid )
    if 'error' in _response:
        log.error('Unable to get JID "{0}" : "{1}"'.format(jid, _response))
        return {}
    return { _response['id']: _response }

def get_jids():
    '''
    List all the jobs that we have..
    '''
    options = _get_options()
    _response = _request( "GET", options['url'] + options['db'] + "/_all_docs" )

    # Make sure the 'total_rows' is returned.. if not error out.
    if not 'total_rows' in _response:
        log.error('Didn\'t get valid response from requesting all docs: {0}'.format(_response))
        return []
    
    # Return the rows.
    ret = []
    for row in _response['rows']:
        # Because this shows all the documents in the database, including the design documents,
        # whitelist the matching salt jid's which is a 20 digit int.

        # See if the identifier is an int..
        try:
            _id = int( row['id'] )
        except Exception as exp:
            continue

        # Check the correct number of digits by simply casting to str and splitting.
        if len(str(row['id'])) == 20:
            ret.append( row['id'] )
    
    return ret

def get_fun(fun):
    '''
    Return a dict with key being minion and value being the last job.
    '''

    _ret = { }

    # For each minion we know about
    for minion in get_minions():

        # Make a query of the by-minion-and-date view and limit the count to 1.
        pass

    return _ret

def get_minions():
    '''
    Return a list of minion identifiers from a request of the view.
    '''
    options = _get_options()

    # Make the request for the view..
    _response = _request( "GET", options['url'] + options['db'] + "/_design/salt/_view/minions?group=true" )

    # Verify that we got a response back.
    if not 'rows' in _response:
        log.error('Unable to get available minions: {0}'.format(_response))
        return []
    
    # Iterate over the rows to build up a list return it.
    _ret = [ ]
    for row in _response['rows']:
        _ret.append( row['key'] )
    return _ret
