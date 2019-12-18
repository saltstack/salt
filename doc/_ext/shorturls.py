'''
Short-URL redirects
'''
import json
import os

import sphinx.ext.intersphinx

DOCS_URL = 'http://docs.saltstack.com/en/latest/'

def write_urls_index(app, exc):
    '''
    Generate a JSON file to serve as an index for short-URL lookups
    '''
    inventory = os.path.join(app.builder.outdir, 'objects.inv')
    objects = sphinx.ext.intersphinx.fetch_inventory(app, DOCS_URL, inventory)

    with open(os.path.join(app.builder.outdir, 'shorturls.json'), 'w') as f:
        json.dump(objects, f)

def setup(app):
    app.connect('build-finished', write_urls_index)
