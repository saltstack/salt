# -*- coding: utf-8 -*-
'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults.

couchdb.db:     'salt'
couchdb.url:        'http://salt:5984/'

  To use the couchdb returner, append '--return couchdb' to the salt command. ex:

    salt '*' test.ping --return couchdb
'''
import logging
import time
import urllib2
import json

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'couchdb'


def __virtual__():
    return __virtualname__


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
    Makes a HTTP request. Returns the JSON parse, or an obj with an error.
    '''
    opener = urllib2.build_opener(urllib2.HTTPHandler)
    request = urllib2.Request(url, data=_data)
    if content_type:
        request.add_header('Content-Type', content_type)
    request.get_method = lambda: method
    try:
        handler = opener.open(request)
    except urllib2.HTTPError as e:
        return {'error': '{0}'.format(e)}
    return json.loads(handler.read())


def returner(ret):
    '''
    Take in the return and shove it into the couchdb database.
    '''

    options = _get_options()

    # Check to see if the database exists.
    _response = _request("GET", options['url'] + "_all_dbs")
    if options['db'] not in _response:

        # Make a PUT request to create the database.
        _response = _request("PUT", options['url'] + options['db'])

        # Confirm that the response back was simple 'ok': true.
        if 'ok' not in _response or _response['ok'] is not True:
            return log.error('Unable to create database "{0}"'
                             .format(options['db']))
        log.info('Created database "{0}"'.format(options['db']))

    # Call _generate_doc to get a dict object of the document we're going to
    # shove into the database.
    doc = _generate_doc(ret, options)

    # Make the actual HTTP PUT request to create the doc.
    _response = _request("PUT",
                         options['url'] + options['db'] + "/" + doc['_id'],
                         'application/json',
                         json.dumps(doc))

    # Santiy check regarding the response..
    if 'ok' not in _response or _response['ok'] is not True:
        log.error('Unable to create document: "{0}"'.format(_response))


def get_jid(jid):
    '''
    Get the document with a given JID.
    '''
    options = _get_options()
    _response = _request("GET", options['url'] + options['db'] + '/' + jid)
    if 'error' in _response:
        log.error('Unable to get JID "{0}" : "{1}"'.format(jid, _response))
        return {}
    return {_response['id']: _response}


def get_jids():
    '''
    List all the jobs that we have..
    '''
    options = _get_options()
    _response = _request("GET", options['url'] + options['db'] + "/_all_docs")

    # Make sure the 'total_rows' is returned.. if not error out.
    if 'total_rows' not in _response:
        log.error('Didn\'t get valid response from requesting all docs: {0}'
                  .format(_response))
        return []

    # Return the rows.
    ret = []
    for row in _response['rows']:
        # Because this shows all the documents in the database, including the
        # design documents, whitelist the matching salt jid's which is a 20
        # digit int.

        # See if the identifier is an int..
        try:
            int(row['id'])
        except Exception:
            continue

        # Check the correct number of digits by simply casting to str and
        # splitting.
        if len(str(row['id'])) == 20:
            ret.append(row['id'])

    return ret


def get_fun(fun):
    '''
    Return a dict with key being minion and value
    being the job details of the last run of function 'fun'.
    '''

    # Get the options..
    options = _get_options()

    # Define a simple return object.
    _ret = {}

    # get_minions takes care of calling ensure_views for us.
    # For each minion we know about
    for minion in get_minions():

        # Make a query of the by-minion-and-timestamp view and limit the count
        # to 1.
        _response = _request("GET",
                             options['url'] +
                                     options['db'] +
                                     ('/_design/salt/_view/by-minion-fun-times'
                                      'tamp?descending=true&endkey=["{0}","{1}'
                                      '",0]&startkey=["{2}","{3}",9999999999]&'
                                      'limit=1').format(minion,
                                                        fun,
                                                        minion,
                                                        fun))
        # Skip the minion if we got an error..
        if 'error' in _response:
            log.warning('Got an error when querying for last command by a '
                        'minion: {0}'.format(_response['error']))
            continue

        # Skip the minion if we didn't get any rows back. ( IE function that
        # they're looking for has a typo in it or some such ).
        if len(_response['rows']) < 1:
            continue

        # Set the respnse ..
        _ret[minion] = _response['rows'][0]['value']

    return _ret


def get_minions():
    '''
    Return a list of minion identifiers from a request of the view.
    '''
    options = _get_options()

    # Make sure the views are valid, which includes the minions..
    if not ensure_views():
        return []

    # Make the request for the view..
    _response = _request("GET",
                         options['url'] +
                                 options['db'] +
                                 "/_design/salt/_view/minions?group=true")

    # Verify that we got a response back.
    if 'rows' not in _response:
        log.error('Unable to get available minions: {0}'.format(_response))
        return []

    # Iterate over the rows to build up a list return it.
    _ret = []
    for row in _response['rows']:
        _ret.append(row['key'])
    return _ret


def ensure_views():
    '''
    This function makes sure that all the views that should
    exist in the design document do exist.
    '''

    # Get the options so we have the URL and DB..
    options = _get_options()

    # Make a request to check if the design document exists.
    _response = _request("GET",
                         options['url'] + options['db'] + "/_design/salt")

    # If the document doesn't exist, or for some reason there are not views.
    if 'error' in _response:
        return set_salt_view()

    # Determine if any views are missing from the design doc stored on the
    # server..  If we come across one, simply set the salt view and return out.
    # set_salt_view will set all the views, so we don't need to continue t
    # check.
    for view in get_valid_salt_views():
        if view not in _response['views']:
            return set_salt_view()

    # Valid views, return true.
    return True


def get_valid_salt_views():
    '''
    Returns a dict object of views that should be
    part of the salt design document.
    '''
    ret = {}

    ret['minions'] = {}
    ret['minions']['map'] = "function( doc ){ emit( doc.id, null ); }"
    ret['minions']['reduce'] = \
            "function( keys,values,rereduce ){ return key[0]; }"

    ret['by-minion-fun-timestamp'] = {}
    ret['by-minion-fun-timestamp']['map'] = \
            "function( doc ){ emit( [doc.id,doc.fun,doc.timestamp], doc ); }"
    return ret


def set_salt_view():
    '''
    Helper function that sets the salt design
    document. Uses get_valid_salt_views and some hardcoded values.
    '''

    options = _get_options()

    # Create the new object that we will shove in as the design doc.
    new_doc = {}
    new_doc['views'] = get_valid_salt_views()
    new_doc['language'] = "javascript"

    # Make the request to update the design doc.
    _response = _request("PUT",
                         options['url'] + options['db'] + "/_design/salt",
                         "application/json", json.dumps(new_doc))
    if 'error' in _response:
        log.warning("Unable to set the salt design document: {0}"
                    .format(_response['error']))
        return False
    return True
