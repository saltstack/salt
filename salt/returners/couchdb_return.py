'''
Return data to a CouchDB server.

:maintainer:	Some Person <user@host.tld>
:maturity:	new
:depends:	python-couchdb
:platform:	all

This returner requires that the following configuration values be
defined in either the master or the minion. Defaults are shown below:

	couchdb.url:		'http://salt:5984/'
	couchdb.create_db:	True
	couchdb.db:		'salt'

'''
# Setup logging..
import logging
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

# Actual returner.
def returner( ret ):
	'''
	Take in the return from a minion and shove it into the couchdb database.
	'''

	# Make a connection to the couchdb server.
	couchdb_server = couchdb.client.Server( __salt__['config.option']('couchdb.url') )

	# Grab the database name rather than using this long reference everywhere.
	database_name	= __salt__['config.option']('couchdb.db')

	# If the create_db option was specified, and the database doesn't exist at that url, create it.
	if __salt__['config.option']('couchdb.create_db') and database_name not in couchdb_server:
		couchdb_server.create( database_name )
	
	# Get the database object we're interested in.
	db = couchdb_server[database_name]
	
	print ret.__dict__
