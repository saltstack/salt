'''
Salt's pluggable authentication system

This sysetm allows for authentication to be managed in a module pluggable way
so that any external authentication system can be used inside of Salt
'''

# 1. Create auth loader instance
# 2. Accept arguments as a dict
# 3. Verify with function introspection
# 4. Execute auth function
# 5. Cache auth token with relative data opts['token_dir']
# 6. Interface to verify tokens

# Import Python libs
import time
import logging
import random
#
# Import Salt libs
import salt.loader
import salt.utils
import salt.payload

log = logging.getLogger(__name__)


class LoadAuth(object):
    '''
    Wrap the authentication system to handle periphrial components
    '''
    def __init__(self, opts):
        self.opts = opts
        self.max_fail = 1.0
        self.serial = salt.payload.Serial(opts)
        self.auth = salt.loader.auth(opts)

    def load_name(self, load):
        '''
        Return the primary name associate with the load, if an empty string
        is returned then the load does not match the function
        '''
        if not 'eauth' in load:
            return ''
        fstr = '{0}.auth'.format(load['eauth'])
        if not fstr in self.auth:
            return ''
        fcall = salt.utils.format_call(self.auth[fstr], load)
        try:
            return fcall['args'][0]
        except IndexError:
            return ''

    def auth_call(self, load):
        '''
        Return the token and set the cache data for use 
        '''
        if not 'fun' in load:
            return False
        fstr = '{0}.auth'.format(load['fun'])
        if not fstr in self.auth:
            return False
        fcall = salt.utils.format_call(self.auth[fstr], load)
        try:
            if 'kwargs' in fcall:
                return self.auth[fstr](*fcall['args'], **fcall['kwargs'])
            else:
                return self.auth[fstr](*fcall['args'])
        except Exception as exc:
            err = 'Authentication module threw an exception: {0}'.format(exc)
            log.critical(err)
            return False
        return False

    def time_auth(self, load):
        '''
        Make sure that all failures happen in the same amount of time
        '''
        start = time.time()
        ret = self.auth_call(load)
        if ret:
            return ret
        f_time = time.time() - start
        if f_time > self.max_fail:
            self.max_fail = f_time
        deviation = self.max_time / 4
        r_time = random.uniform(
                self.max_time - deviation,
                self.max_time + deviation
                )
        while start + r_time > time.time():
            time.sleep(0.001)
        return False

    def mk_token(self, load):
        '''
        Run time_auth and create a token. Return False or the token
        '''
        ret = time_auth(load)
        if ret is False:
            return ret
        tok = hashlib.md5(os.urandom(512)).hexdigest()
        t_path = os.path.join(opts['token_dir'], tok)
        while os.path.isfile(t_path):
            tok = hashlib.md5(os.urandom(512)).hexdigest()
            t_path = os.path.join(opts['token_dir'], tok)
        fcall = salt.utils.format_call(self.auth[fstr], load)
        tdata = {'start': time.time(),
                 'expire': time.time() + self.opts['token_expire'],
                 'name': fcall['args'][0],}
        with open(t_path, 'w+') as fp_:
            fp_.write(self.serial.dumps(tdata))
        return tok

    def get_tok(self, tok):
        '''
        Return the name associate with the token, or False ifthe token is not valid
        '''
        t_path = os.path.join(opts['token_dir'], tok)
        if not os.path.isfile:
            return False
        with open(t_path, 'r') as fp_:
            return self.serial.loads(fp_.read())
        return False
