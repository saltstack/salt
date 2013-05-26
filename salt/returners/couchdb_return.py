'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults.

couchdb.db:		'salt'
couchdb.url:		'http://salt:5984/'

'''
import time

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
	# Get the configuration options, and set some defaults
	server_url	= __salt__['config.option']('couchdb.url')
	if not server_url:
		server_url = "http://salt:5984/"
	db_name		= __salt__['config.option']('couchdb.db')
	if not db_name:
		db_name = "salt"

	return { "url": server_url, "create": create_db, "db": db_name }

def _generate_doc( ret, options ):
	'''
	Create a object that will be saved into the database based on
	options.
	'''
	r		= ret
	r["_id"]	= ret["jid"]
	r["timestamp"]	= time.time( )
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
