'''
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

# Actual returner.
def returner( ret ):
	'''
	Take in the return and shove it into the couchdb database.
	'''
	
	# Get a connection to the couchdb server.
	couchdb_server	= couchdb.client.Server( server_url )
	
	# Create the server if the create_db flag is set and the db
	# doesn't already exist.
	if create_db and not db_name in couchdb_server:
		couchdb_server.create( db_name )

	# Get the database object specifically.
	db = couchdb_server[db_name]

	# Create a temporary obj that we can add to.
	obj			= ret
	obj["_id"]		= ret["jid"]
	obj["timestamp"]	= time.time( )
	db.save( obj )
