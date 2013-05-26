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
