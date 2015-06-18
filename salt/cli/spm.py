# -*- coding: utf-8 -*-
'''
    salt.cli.spm
    ~~~~~~~~~~~~~

    Salt's spm cli parser.

'''

# Import Python libs
from __future__ import absolute_import, print_function
import os.path
import logging

# Import Salt libs
import salt.utils.parsers as parsers
import salt.version
import salt.syspaths as syspaths

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


class SPM(six.with_metaclass(parsers.OptionParserMeta,  # pylint: disable=W0232
        parsers.OptionParser, parsers.ConfigDirMixIn,
        parsers.LogLevelMixIn, parsers.MergeConfigMixIn)):
    '''
    The cli parser object used to fire up the salt spm system.
    '''

    VERSION = salt.version.__version__

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'spm'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = os.path.join(syspaths.LOGS_DIR, 'spm')

    def setup_config(self):
        return salt.config.spm_config(self.get_config_file_path())

    def run(self):
        '''
        Run the api
        '''
        import salt.client.spm
        self.parse_args()
        self.setup_logfile_logger()
        client = salt.client.spm.SPMClient(self.config)
        client.run(self.args)
