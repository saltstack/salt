# -*- coding: utf-8 -*-
'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults:

.. code-block:: yaml

    couchdb.db: 'salt'
    couchdb.url: 'http://salt:5984/'
    couchdb.user: None
    couchdb.passwd: None
    couchdb.redact_pws: None
    couchdb.minimum_return: None

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.couchdb.db: 'salt'
    alternative.couchdb.url: 'http://salt:5984/'

To use the couchdb returner, append ``--return couchdb`` to the salt command. Example:

.. code-block:: bash

    salt '*' test.ping --return couchdb

To use the alternative configuration, append ``--return_config alternative`` to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return couchdb --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return couchdb --return_kwargs '{"db": "another-salt"}'

On concurrent database access
==============================

As this returner creates a couchdb document with the salt job id as document id
and as only one document with a given id can exist in a given couchdb database,
it is advised for most setups that every minion be configured to write to it own
database (the value of ``couchdb.db`` may be suffixed with the minion id),
otherwise multi-minion targeting can lead to losing output:

* the first returning minion is able to create a document in the database
* other minions fail with ``{'error': 'HTTP Error 409: Conflict'}``
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time

# Import 3rd-party libs
# pylint: disable=no-name-in-module,import-error
from salt.ext.six.moves.urllib.error import HTTPError
from salt.ext.six.moves.urllib.request import (
        Request as _Request,
        HTTPHandler as _HTTPHandler,
        build_opener as _build_opener,
)
# pylint: enable=no-name-in-module,import-error

# Import Salt libs
import salt.utils.jid
import salt.utils.json
import salt.returners

# boltons lib for redact_pws and minimum_return
try:
    from boltons.iterutils import remap
    boltons_lib = True
except ImportError:
    boltons_lib = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'couchdb'


def __virtual__():
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the couchdb options from salt.
    '''
    attrs = {'url': 'url',
             'db': 'db',
             'user': 'user',
             'passwd': 'passwd',
             'redact_pws': 'redact_pws',
             'minimum_return': 'minimum_return'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    if 'url' not in _options:
        log.debug("Using default url.")
        _options['url'] = "http://salt:5984/"

    if 'db' not in _options:
        log.debug("Using default database.")
        _options['db'] = "salt"

    if 'user' not in _options:
        log.debug("Not athenticating with a user.")
        _options['user'] = None

    if 'passwd' not in _options:
        log.debug("Not athenticating with a password.")
        _options['passwd'] = None

    if 'redact_pws' not in _options:
        log.debug("Not redacting passwords.")
        _options['redact_pws'] = None

    if 'minimum_return' not in _options:
        log.debug("Not minimizing the return object.")
        _options['minimum_return'] = None

    return _options


def _redact_passwords(path, key, value):
    if 'password' in str(key) and value:
        return key, 'XXX-REDACTED-XXX'
    return key, value


def _minimize_return(path, key, value):
    if isinstance(key, str) and key.startswith('__pub'):
        return False
    return True


def _generate_doc(ret):
    '''
    Create a object that will be saved into the database based on
    options.
    '''

    # Create a copy of the object that we will return.
    retc = ret.copy()

    # Set the ID of the document to be the JID.
    retc["_id"] = ret["jid"]

    # Add a timestamp field to the document
    retc["timestamp"] = time.time()

    return retc


def _request(method, url, content_type=None, _data=None, user=None, passwd=None):
    '''
    Makes a HTTP request. Returns the JSON parse, or an obj with an error.
    '''
    opener = _build_opener(_HTTPHandler)
    request = _Request(url, data=_data)
    if content_type:
        request.add_header('Content-Type', content_type)
    if user and passwd:
        auth_encode = '{0}:{1}'.format(user, passwd).encode('base64')[:-1]
        auth_basic = "Basic {0}".format(auth_encode)
        request.add_header('Authorization', auth_basic)
        request.add_header('Accept', 'application/json')
    request.get_method = lambda: method
    try:
        handler = opener.open(request)
    except HTTPError as exc:
        return {'error': '{0}'.format(exc)}
    return salt.utils.json.loads(handler.read())


def _generate_event_doc(event):
    '''
    Create a object that will be saved into the database based in
    options.
    '''

    # Create a copy of the object that we will return.
    eventc = event.copy()

    # Set the ID of the document to be the JID.
    eventc["_id"] = '{}-{}'.format(
                                    event.get('tag', '').split('/')[2],
                                    event.get('tag', '').split('/')[3]
                                  )

    # Add a timestamp field to the document
    eventc["timestamp"] = time.time()

    # remove any return data as it's captured in the "returner" function
    if eventc.get('data').get('return'):
        del eventc['data']['return']

    return eventc


def returner(ret):
    '''
    Take in the return and shove it into the couchdb database.
    '''

    options = _get_options(ret)

    # Check to see if the database exists.
    _response = _request("GET",
                         options['url'] + "_all_dbs",
                         user=options['user'],
                         passwd=options['passwd'])
    if options['db'] not in _response:

        # Make a PUT request to create the database.
        _response = _request("PUT",
                             options['url'] + options['db'],
                             user=options['user'],
                             passwd=options['passwd'])

        # Confirm that the response back was simple 'ok': true.
        if 'ok' not in _response or _response['ok'] is not True:
            log.error('Nothing logged! Lost data. Unable to create database "%s"', options['db'])
            log.debug('_response object is: %s', _response)
            return
        log.info('Created database "%s"', options['db'])

    if boltons_lib:
        # redact all passwords if options['redact_pws'] is True
        if options['redact_pws']:
            ret_remap_pws = remap(ret, visit=_redact_passwords)
        else:
            ret_remap_pws = ret

        # remove all return values starting with '__pub' if options['minimum_return'] is True
        if options['minimum_return']:
            ret_remapped = remap(ret_remap_pws, visit=_minimize_return)
        else:
            ret_remapped = ret_remap_pws
    else:
        log.info('boltons library not installed. pip install boltons. https://github.com/mahmoud/boltons.')
        ret_remapped = ret

    # Call _generate_doc to get a dict object of the document we're going to shove into the database.
    doc = _generate_doc(ret_remapped)

    # Make the actual HTTP PUT request to create the doc.
    _response = _request("PUT",
                         options['url'] + options['db'] + "/" + doc['_id'],
                         'application/json',
                         salt.utils.json.dumps(doc))

    # Sanity check regarding the response..
    if 'ok' not in _response or _response['ok'] is not True:
        log.error('Nothing logged! Lost data. Unable to create document: "%s"', _response)


def event_return(events):
    '''
    Return event to CouchDB server
    Requires that configuration be enabled via 'event_return'
    option in master config.

    Example:

    event_return:
      - couchdb

    '''
    log.debug('events data is: %s', events)

    options = _get_options()

    # Check to see if the database exists.
    _response = _request("GET", options['url'] + "_all_dbs")
    event_db = '{}-events'.format(options['db'])
    if event_db not in _response:

        # Make a PUT request to create the database.
        log.info('Creating database "%s"', event_db)
        _response = _request("PUT",
                             options['url'] + event_db,
                             user=options['user'],
                             passwd=options['passwd'])

        # Confirm that the response back was simple 'ok': true.
        if 'ok' not in _response or _response['ok'] is not True:
            log.error('Nothing logged! Lost data. Unable to create database "%s"', event_db)
            return
        log.info('Created database "%s"', event_db)

    for event in events:
        # Call _generate_doc to get a dict object of the document we're going to shove into the database.
        log.debug('event data is: %s', event)
        doc = _generate_event_doc(event)

        # Make the actual HTTP PUT request to create the doc.
        _response = _request("PUT",
                             options['url'] + event_db + "/" + doc['_id'],
                             'application/json',
                             salt.utils.json.dumps(doc))
        # Sanity check regarding the response..
        if 'ok' not in _response or _response['ok'] is not True:
            log.error('Nothing logged! Lost data. Unable to create document: "%s"', _response)


def get_jid(jid):
    '''
    Get the document with a given JID.
    '''
    options = _get_options(ret=None)
    _response = _request("GET", options['url'] + options['db'] + '/' + jid)
    if 'error' in _response:
        log.error('Unable to get JID "%s" : "%s"', jid, _response)
        return {}
    return {_response['id']: _response}


def get_jids():
    '''
    List all the jobs that we have..
    '''
    options = _get_options(ret=None)
    _response = _request("GET", options['url'] + options['db'] + "/_all_docs?include_docs=true")

    # Make sure the 'total_rows' is returned.. if not error out.
    if 'total_rows' not in _response:
        log.error('Didn\'t get valid response from requesting all docs: %s', _response)
        return {}

    # Return the rows.
    ret = {}
    for row in _response['rows']:
        # Because this shows all the documents in the database, including the
        # design documents, verify the id is salt jid
        jid = row['id']
        if not salt.utils.jid.is_jid(jid):
            continue

        ret[jid] = salt.utils.jid.format_jid_instance(jid, row['doc'])

    return ret


def get_fun(fun):
    '''
    Return a dict with key being minion and value
    being the job details of the last run of function 'fun'.
    '''

    # Get the options..
    options = _get_options(ret=None)

    # Define a simple return object.
    _ret = {}

    # get_minions takes care of calling ensure_views for us. For each minion we know about
    for minion in get_minions():

        # Make a query of the by-minion-and-timestamp view and limit the count to 1.
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
            log.warning('Got an error when querying for last command '
                        'by a minion: %s', _response['error'])
            continue

        # Skip the minion if we didn't get any rows back. ( IE function that
        # they're looking for has a typo in it or some such ).
        if not _response['rows']:
            continue

        # Set the respnse ..
        _ret[minion] = _response['rows'][0]['value']

    return _ret


def get_minions():
    '''
    Return a list of minion identifiers from a request of the view.
    '''
    options = _get_options(ret=None)

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
        log.error('Unable to get available minions: %s', _response)
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
    options = _get_options(ret=None)

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

    options = _get_options(ret=None)

    # Create the new object that we will shove in as the design doc.
    new_doc = {}
    new_doc['views'] = get_valid_salt_views()
    new_doc['language'] = "javascript"

    # Make the request to update the design doc.
    _response = _request("PUT",
                         options['url'] + options['db'] + "/_design/salt",
                         "application/json", salt.utils.json.dumps(new_doc))
    if 'error' in _response:
        log.warning('Unable to set the salt design document: %s', _response['error'])
        return False
    return True


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def save_load(jid, load):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Included for API consistency
    '''
    options = _get_options(ret=None)
    _response = _request("GET", options['url'] + options['db'] + '/' + jid)
    if 'error' in _response:
        log.error('Unable to get JID "%s" : "%s"', jid, _response)
        return {}
    return {_response['id']: _response}
