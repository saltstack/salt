'''
Primary interfaces for the salt-cloud system
'''

# Import python libs
import optparse

# Import salt libs
import saltcloud.config

class SaltCloud(object):
    '''
    Create a cli SaltCloud object
    '''
    def __init__(self):
        self.opts = self.parse()

    def parse(self):
        '''
        Parse the command line and merge the config
        '''
        parser = optparse.OptionParser()
