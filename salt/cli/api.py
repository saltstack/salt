# -*- coding: utf-8 -*-
'''
    salt.cli.api
    ~~~~~~~~~~~~~

    Salt's api cli parser.

'''

# Import Python libs
from __future__ import absolute_import, print_function
import os.path
import logging

# Import Salt libs
import salt.utils.parsers as parsers
import salt.version
import salt.syspaths as syspaths
from salt.utils.verify import verify_log

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


class SaltAPI(six.with_metaclass(parsers.OptionParserMeta,  # pylint: disable=W0232
        parsers.OptionParser, parsers.ConfigDirMixIn,
        parsers.LogLevelMixIn, parsers.PidfileMixin, parsers.DaemonMixIn,
        parsers.MergeConfigMixIn)):
    '''
    The cli parser object used to fire up the salt api system.
    '''

    VERSION = salt.version.__version__

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = os.path.join(syspaths.LOGS_DIR, 'api')

    def setup_config(self):
        return salt.config.api_config(self.get_config_file_path())

    def run(self):
        '''
        Run the api
        '''
        import salt.client.netapi
        self.parse_args()
        self.setup_logfile_logger()
        verify_log(self.config)
        self.daemonize_if_required()
        client = salt.client.netapi.NetapiClient(self.config)
        self.set_pidfile()
        client.run()
