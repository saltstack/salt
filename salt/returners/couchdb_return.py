'''
Simple returner for CouchDB. Optional configuration
settings are listed below, along with sane defaults.

couchdb.db:		'salt'
couchdb.url:		'http://salt:5984/'
couchdb.create_db:	True

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
	create_db	= __salt__['config.option']('couchdb.create_db')
	if create_db == None:
		create_db = True
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
	_s	= couchdb.client.Server( options["server_url"] )

	# Create the database if the configuration calls for it.
	if options["create_db"] and not options["db"] in _s:
		server.create( options["db"] )
	
	# Save the document that comes out of _generate_doc.
	_s[options["db"]].save( _generate_doc( ret, options ) )
