# Unification of the returning data

import os
from abc import ABCMeta, abstractmethod
from salt.utils.structure import Stub


class Package(object):
    '''
    Refers to the pkg.* module.
    '''
    DIST_SPECIFIC = 'distribution-specific'

    def __init__(self, ident):
        # This loads the corresponding unifier to the caller module
        self.unifier = Package.__dict__.get(os.path.basename(ident).split(".")[0].title(), Stub)()

    class _Methods(object):
        __metaclass__ = ABCMeta

        @abstractmethod
        def mod_repo(self, data):
            '''
            Structure returned for mod_repo method call
            :return:
            '''
            schema = {
                'alias': str,
                'baseurl': str,
                'enabled': bool,
                'refresh': bool,
                'gpgcheck': bool,
                'filename': str,
                'name': str,
                Package.DIST_SPECIFIC: {},  # Data only appears
                                            # in this particular distribution
            }

            return schema

    class Yumpkg(_Methods):
        '''
        Structure unifiers for Yum.
        '''
        def mod_repo(self, data):
            schema = {}
            # Supposed to be only one repo, so not really an iteration.
            for r_filename, r_repodata in data.items():
                for r_alias, r_meta in r_repodata.items():
                    schema = {
                        'alias': r_alias,
                        'baseurl': r_meta.pop('baseurl'),
                        'enabled': bool(r_meta.pop('enabled')),
                        'refresh': 'refresh' in r_meta and bool(r_meta.pop('refresh')) or False,
                        'gpgcheck': bool(r_meta.pop('gpgcheck')),
                        'filename': r_filename,
                        'name': r_meta.pop('name'),
                    }
                    if r_meta:
                        schema[Package.DIST_SPECIFIC] = r_meta

            return schema

    class Zypper(_Methods):
        '''
        Structure unifiers for Zypper.
        '''
        def mod_repo(self, data):
            alias = data.pop('alias')
            schema = {
                'alias': alias,
                'baseurl': data.pop('baseurl'),
                'enabled': data.pop('enabled'),
                'refresh': data.pop('autorefresh'),
                'gpgcheck': data.get('gpgcheck') and data.pop('gpgcheck') or False,
                'filename': data.pop('path'),
                'name': data.pop('name'),
            }
            if data:
                schema[Package.DIST_SPECIFIC] = data

            return schema

    class Aptpkg(_Methods):
        '''
        Structure unifiers for Apt
        '''
        def mod_repo(self, data):
            return data

    def __getattr__(self, item):
        '''
        Load only what is really needed at the very moment.

        :param item:
        :return:
        '''
        # When this class is initialized, an unifier is set according to the module name.
        # Example: for modules/zypper.py class is Zypper. For modules/yumpkg is Yumpkg etc.
        # The usage of this class is simple:
        #
        #    foo = Package(__file__)     <-- this sets what module is calling it
        #    return foo.mod_repo(output) <-- this wraps the output to the certain function
        #
        # TODO: Turn all this thing into a generic decorator?

        return getattr(self.unifier, item)
