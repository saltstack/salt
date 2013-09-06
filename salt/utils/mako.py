from __future__ import absolute_import

# Import python libs
import os
import urlparse

# Import third party libs
from mako.lookup import TemplateCollection, TemplateLookup

# Import salt libs
import salt.fileclient

class SaltMakoTemplateLookup(TemplateCollection):
    """
    Look up Mako template files on Salt master via salt://... URLs.

    If URL is a relative path(without an URL scheme) then assume it's relative
    to the directory of the salt file that's doing the lookup(with <%include/>
    or <%namespace/>).

    If URL is an absolute path then it's treated as if it has been prefixed
    with salt://.

    Examples::

       <%include file="templates/sls-parts.mako"/>
       <%namespace file="salt://lib/templates/utils.mako" import="helper"/>

    """

    def __init__(self, opts, env='base'):
        self.opts = opts
        self.env = env
        if opts['file_client'] == 'local':
            searchpath = opts['file_roots'][env]
        else:
            searchpath = [os.path.join(opts['cachedir'], 'files', env)]
        self.lookup = TemplateLookup(directories=searchpath)

        self.file_client = salt.fileclient.get_file_client(self.opts)
        self.cache = {}

    def adjust_uri(self, uri, filename):
        scheme = urlparse.urlparse(uri).scheme
        if scheme == 'salt':
            return uri
        elif scheme:
            raise ValueError("Unsupported URL scheme(%s) in %s" %
                             (scheme, uri))
        else:
            return self.lookup.adjust_uri(uri, filename)

    def get_template(self, uri):
        prefix = "salt://"
        salt_uri = uri if uri.startswith(prefix) else (prefix + uri)
        self.cache_file(salt_uri)
        return self.lookup.get_template(salt_uri[len(prefix):])

    def cache_file(self, fpath):
        if fpath not in self.cache:
            self.cache[fpath] = \
                    self.file_client.get_file(fpath, '', True, self.env)
