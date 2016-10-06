# Unification of the returning data

from abc import ABCMeta, abstractmethod


class Package(object):
    '''
    Refers to the pkg.* module.
    '''
    DIST_SPECIFIC = 'distribution-specific'

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

    class Yum(_Methods):
        '''
        Structure unifiers for Yum.
        '''
        def mod_repo(self, data):
            schema = {}
            for r_filename, r_repodata in data.items():
                for r_alias, r_meta in r_repodata.items():
                    schema[r_alias] = {
                        'baseurl': r_meta['baseurl'],
                        'enabled': bool(r_meta['enabled']),
                        'gpgcheck': bool(r_meta['gpgcheck']),
                        'filename': r_filename,
                        'name': r_alias,
                    }

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

    class Apt(_Methods):
        '''
        Structure unifiers for Apt
        '''
        def mod_repo(self, data):
            return data

    def __init__(self):
        self.yum = Package.Yum()
        self.zypper = Package.Zypper()
        self.apt = Package.Apt()
