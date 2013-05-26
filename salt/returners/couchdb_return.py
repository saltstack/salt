'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults.

couchdb.db:		'salt'
couchdb.url:		'http://salt:5984/'

'''
import logging
import time

log = logging.getLogger( __name__ )

# Import the required modules.
try:
	import couchdb
	HAS_COUCHDB = True
except ImportError:
	HAS_COUCHDB = False

def __virtual__( ):
	if not HAS_COUCHDB:
		return False
	return 'couchdb'

def _get_options( ):
	'''
	Get the couchdb options from salt. Apply defaults
	if required.
	'''
	server_url = __salt__['config.option']('couchdb.url')
	if not server_url:
		server_url = "http://salt:5984/"

	db_name = __salt__['config.option']('couchdb.db')
	if not db_name:
		db_name = "salt"

	doc = __salt__['config.option']('couchdb.doc')
	if not doc:
		doc = [ { "import": ["time"], "key": "timestamp", "value": "time.time()" } ]

	return { "url": server_url, "create": create_db, "db": db_name, "doc": doc }

def _generate_doc( ret, options ):
	'''
	Create a object that will be saved into the database based on
	options.
	'''
	
	# Just set the document ID to the jid.
	r		= ret
	r["_id"]	= ret["jid"]

	log.debug( "Heh? %s" % options["doc"] )
	# Iterate though the options["doc"]
	for _obj in options["doc"]:
		# If import is defined, iterate through the list and import.
		if hasattr( _obj, "import" ):
			for to_import in getattr( _obj, "import" ):
				eval( "import %s" % to_import )

		# Set the return object[key] to eval(value) in effect.
		r[_obj["key"]] = eval( _obj["value"] )
		
	return r

def returner( ret ):
	'''
	Take in the return and shove it into the couchdb database.
	'''

	# Get the options from configuration.
	options = _get_options( )
	
	# Create a connection to the server.
	server	= couchdb.client.Server( options["url"] )

	# Create the database if the configuration calls for it.
	if not options["db"] in server:
		server.create( options["db"] )

	# Save the document that comes out of _generate_doc.
	server[options["db"]].save( _generate_doc( ret, options ) )
