'''
CLI entry-point for salt-api
'''
# Import salt libs
from salt.utils.parsers import (
        ConfigDirMixIn,
        LogLevelMixIn,
        OptionParser,
        OptionParserMeta)

# Import salt-api libs
import saltapi.client
import saltapi.config
import saltapi.version

class SaltAPI(OptionParser, ConfigDirMixIn, LogLevelMixIn):
    '''
    The cli parser object used to fire up the salt api system.
    '''
    __metaclass__ = OptionParserMeta

    VERSION = saltapi.version.__version__

    def setup_config(self):
        return saltapi.config.api_config(self.get_config_file_path('master'))

    def run(self):
        '''
        Run the api
        '''
        self.parse_args()
        self.process_config_dir()
        client = saltapi.client.SaltAPIClient(self.config)
        client.run()
