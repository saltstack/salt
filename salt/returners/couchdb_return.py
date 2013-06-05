'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults.

couchdb.hooks
    * is a list of dict objects.
    * in each dict there is a key and value.
    * the value is eval()'d
    * optional "eval", which is executed beforehand.

couchdb.db:     'salt'
couchdb.url:        'http://salt:5984/'
couchdb.hooks:      [ { "key": "timestamp", "value": "time.time()", "eval": "import time" } ]

'''
import logging

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

    hooks = __salt__['config.option']('couchdb.hooks')
    if not hooks:
        log.debug("Using default hooks")
        hooks = [{"key": "timestamp", "value": "time.time()", "eval": "import time"}]

    return {"url": server_url, "db": db_name, "hooks": hooks}


def _generate_doc(ret, options):
    '''
    Create a object that will be saved into the database based on
    options.
    '''

    # Just set the document ID to the jid.
    r = ret
    r["_id"] = ret["jid"]

    for hook in options["hooks"]:

        # Eval if specified.
        if hasattr(hook, "eval"):
            eval(hook["eval"])

        r[hook["key"]] = eval(hook["value"])

    return r


def returner(ret):
    '''
    Take in the return and shove it into the couchdb database.
    '''

    # Get the options from configuration.
    options = _get_options()

    # Create a connection to the server.
    server = couchdb.client.Server(options['url'])

    # Create the database if the configuration calls for it.
    if options['db'] not in server:
        log.debug('Creating database "{0}"'.format(options['db']))
        server.create(options['db'])

    # Save the document that comes out of _generate_doc.
    server[options['db']].save(_generate_doc(ret, options))
