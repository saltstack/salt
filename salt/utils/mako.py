# -*- coding: utf-8 -*-
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
    Look up Mako template files using file:// or salt:// URLs with <%include/>
    or <%namespace/>.

    (1) Look up mako template files on local file system via files://... URL.
        Make sure mako template file is present locally on minion beforehand.

      Examples:
        <%include   file="file:///etc/salt/lib/templates/sls-parts.mako"/>
        <%namespace file="file:///etc/salt/lib/templates/utils.mako" import="helper"/>

    (2) Look up mako template files on Salt master via salt://... URL.
        If URL is a relative  path (without an URL scheme) then assume it's relative
        to the directory of the salt file that's doing the lookup. If URL is an absolute
        path then it's treated as if it has been prefixed with salt://.

       Examples::
         <%include   file="templates/sls-parts.mako"/>
         <%include   file="salt://lib/templates/sls-parts.mako"/>
         <%include   file="/lib/templates/sls-parts.mako"/>                 ##-- treated as salt://

         <%namespace file="templates/utils.mako"/>
         <%namespace file="salt://lib/templates/utils.mako" import="helper"/>
         <%namespace file="/lib/templates/utils.mako" import="helper"/>     ##-- treated as salt://

    """

    def __init__(self, opts, saltenv='base', env=None):
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env
        self.opts = opts
        self.saltenv = saltenv
        self.file_client = salt.fileclient.get_file_client(self.opts)
        self.lookup = TemplateLookup(directories='/')
        self.cache = {}

    def adjust_uri(self, uri, filename):
        scheme = urlparse.urlparse(uri).scheme
        if scheme in ('salt', 'file'):
            return uri
        elif scheme:
            raise ValueError(
                'Unsupported URL scheme({0}) in {1}'.format(
                    scheme, uri
                )
            )
        return self.lookup.adjust_uri(uri, filename)

    def get_template(self, uri, relativeto=None):
        if uri.startswith("file://"):
            prefix = "file://"
            searchpath = "/"
            salt_uri = uri
        else:
            prefix = "salt://"
            if self.opts['file_client'] == 'local':
                searchpath = self.opts['file_roots'][self.saltenv]
            else:
                searchpath = [os.path.join(self.opts['cachedir'],
                                           'files',
                                           self.saltenv)]
            salt_uri = uri if uri.startswith(prefix) else (prefix + uri)
            self.cache_file(salt_uri)

        self.lookup = TemplateLookup(directories=searchpath)
        return self.lookup.get_template(salt_uri[len(prefix):])

    def cache_file(self, fpath):
        if fpath not in self.cache:
            self.cache[fpath] = self.file_client.get_file(fpath,
                                                          '',
                                                          True,
                                                          self.saltenv)
