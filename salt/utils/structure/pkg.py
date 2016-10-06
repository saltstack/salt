# Unification of the returning data

from abc import ABCMeta, abstractmethod


class Package(object):
    '''
    Refers to the pkg.* module.
    '''
    class _Methods(object):
        __metaclass__ = ABCMeta

        @abstractmethod
        def mod_repo(self, data):
            '''
            Structure returned for mod_repo method call
            :return:
            '''
            schema = {
                'alias' : {
                    'baseurl': str,
                    'enabled': bool,
                    'refresh': bool,
                    'gpgcheck': bool,
                    'type': str,
                    'filename': str,
                }
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
                        'type': 'package',
                        'filename': r_filename,
                    }

            return schema

    class Zypper(_Methods):
        '''
        Structure unifiers for Zypper.
        '''
        def mod_repo(self, data):
            return data

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
