'''
Return data to a CouchDB server.

:maintainer:	Some Person <user@host.tld>
:maturity:	new
:depends:	python-couchdb
:platform:	all

This returner requires that the following configuration values be
defined in either the master or the minion. Defaults are shown below:

	couchdb.host: 'salt'
	couchdb.port: 5984
	couchdb.db: 'salt'
	couchdb.user: None
	couchdb.pass: None

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
	pass
