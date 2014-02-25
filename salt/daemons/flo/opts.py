# -*- coding: utf-8 -*-
'''
Populate ioflo with the info from opts
'''

# Import ioflo libs
import ioflo.base.deeding
import ioflo.base.storing


@ioflo.base.deeding.deedify('populate_opts', ioinits={'opts': '.salt.opts'})
def populate_opts(self):
    '''
    Return the master keys
    '''
    for key, value in self.opts.value.items():
        try:
            share = self.store.create('.salt.etc.{0}'.format(key))
        except ValueError:
            continue
        share.value = value
