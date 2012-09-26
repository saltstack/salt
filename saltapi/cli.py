'''
Cli controls for salt-api
'''
# Import python libs
import optparse
import multiprocessing

# Import salt libs
import saltapi.config
import saltapi.loader
from saltapi.version import __version__ as VERSION

class SaltAPI(object):
    '''
    The cli parser object used to fire up the salt api system.
    '''
    def __init__(self):
        self.opts = self.parse()

    def parse(self):
        '''
        Parse the command line and bring in the config
        '''
        cli = self._parse_cli()
        opts = saltapi.config.api_config(cli['config'])
        opts.update()
        return opts

    def _parse_cli(self):
        '''
        Parse the command line
        '''
        parser = optparse.OptionParser()

        parser.add_option('-C',
                '--master-config',
                '--config',
                dest='config',
                default='/etc/salt/master',
                help='The location of the master config file')

        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Pass to make the system run as a daemon')

        options, args = parser.parse_args()

        cli = {}

        for k, v in options.__dict__.items():
            if v is not None:
                cli[k] = v

        return cli

    def run(self):
        '''
        Run the api
        '''
        netapi = saltapi.loader.netapi(self.opts)
        for fun in netapi:
            if fun.endswith('.bind'):
                multiprocessing.Process(target=netapi[fun]).start()
