# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.config.schemas.common
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Common salt configuration schemas
'''

# Import Pythosn libs
from __future__ import absolute_import

# Import salt libs
from salt.utils.schema import (Schema,
                               StringItem,
                               ArrayItem,
                               OneOfItem)


class DefaultIncludeConfig(StringItem):
    '''
    Per default, the {0}, will automatically include all config files
    from '{1}/*.conf' ('{1}' is a sub-directory in the same directory
    as the main {0} config file).
    '''
    __target__ = None
    __confd_directory__ = None

    title = 'Include Config'
    description = __doc__

    def __init__(self, default=None, pattern=None, **kwargs):
        default = '{0}/*.conf'.format(self.__confd_directory__)
        pattern = r'(?:.*)/\*\.conf'
        super(DefaultIncludeConfig, self).__init__(default=default, pattern=pattern, **kwargs)

    def __validate_attributes__(self):
        self.__doc__ = DefaultIncludeConfig.__doc__.format(self.__target__,
                                                           self.__confd_directory__)
        super(DefaultIncludeConfig, self).__validate_attributes__()

    def __get_description__(self):
        return self.__doc__.format(self.__target__, self.__confd_directory__)


class MinionDefaultInclude(DefaultIncludeConfig):
    __target__ = 'minion'
    __confd_directory__ = 'minion.d'


class MasterDefaultInclude(DefaultIncludeConfig):
    __target__ = 'master'
    __confd_directory = 'master.d'


class IncludeConfig(Schema):
    title = 'Include Configuration File(s)'
    description = 'Include one or more specific configuration files'

    string_or_array = OneOfItem(items=(StringItem(),
                                       ArrayItem(items=StringItem())))(flatten=True)
