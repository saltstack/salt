'''
The State Library: SaltStack state documentor module.
'''
import re
import glob
import logging
import salt
import os
from uuid import getnode as get_mac

__virtualname__ = 'tsl'

'''
State files must include a header like this
#START-DOC
# Author: John Doe
# Description: Mongodb enable start on boot and restart
# Grains (if applicable):
# Pillars (if applicable):
# Syntax: N/A
#END-DOC
'''

'''
_infotype_ contains the possible doc values, with a boolean 'required' flag
'''
_infotype_ = {
    'Author': True, 'Description': True, 'Syntax': True
}

'''
ENVIRONMENT contains the states environment
'''
#TODO: get this from salt config
ENVIRONMENT = 'base'

log = logging.getLogger(__name__)

def filedoc(filename, state):
    '''
    Show the document section of a state file.
    CLI Example:
    salt '*' tls.filedoc statefile.sls
    '''

    if __salt__['file.file_exists'](filename):
        content = __salt__['file.read'](filename)
        docs_section = re.findall('#START-DOC(.*?)#END-DOC', content, re.S)
        if docs_section:
            docs = docs_section[0].splitlines()
            tsl, exists, error = (), (), ()
            # Creating the File_name
            tsl += ('State_name: ' + state, )
            # Creating the File_path
            tsl += ('File_name: ' + filename, )
            # Pillars
            plist = pillars(state)
            if len(plist) > 0:
                tsl += ('Pillars: ' + os.linesep + '\t' + (os.linesep + '\t').join(plist), )
            # Grains
            glist = grains(state)
            if len(glist) > 0:
                tsl += ('Grains: ' + os.linesep + '\t' + (os.linesep + '\t').join(glist), )
            # Includes
            ilist = includes(state)
            if len(ilist) > 0:
                tsl += ('Includes: ' + os.linesep + '\t' + (os.linesep + '\t').join(ilist), )
            # Processing DOC string
            for line in docs:
                docval = re.match('# (.*): (.*)', line)
                if docval:
                    name = docval.expand(r'\1')
                    # Check if this info is known to us
                    if name in _infotype_:
                        # Check duplicate info
                        if name in exists:
                            error += ('Duplicated info: ' + name + docval.expand(r' (\2)'),)
                            continue
                        str = docval.expand(r'\1: \2')
                        tsl += (str,)
                        exists += (name,)
                    else:
                        str = docval.expand(r'Unknown info: \1 ')
                        error += (str,)
            # Look for missing info
            for type in _infotype_:
                if _infotype_[type] == True and type not in exists:
                    error += ('Missing info: ' + type,)
            # retval = 'Doc Info:\n' +'\n'.join(tsl) + '\n\nErrors:\n' + '\n'.join(error)
            retval = {}
            retval['Doc Info'] = tsl
            if (len(error)):
                retval['Errors'] = error
            return retval
        else:
            return {'Error': 'Missing DOC section'}
    else:
        return {'Error': 'Missing .sls file'}


def path(state):
    '''
    Show the path of the state file (.sls).
    CLI Example:
    salt '*' tls.path state
    '''

    opts = salt.utils.state.get_sls_opts(__opts__)
    st_ = salt.state.HighState(opts)
    info = st_.client.get_state(state, ENVIRONMENT)

    if ('dest' in info):
        path = info['dest']
        return path
    else:
        return False


def doc(state):
    '''
    Show the document section of a state.
    CLI Example:
    salt '*' tls.doc state
    '''

    if (path(state)):
        return filedoc(path(state), state)
    else:
        return 'State does not exist on this minion.'

def list_full():
    '''
    Show the document section of states for a minion.
    CLI Example:
    salt 'minion' tls.list
    '''

    tsl = {'Doc section': {}, 'Used states': {}, 'Unused states': {}}
    opts = salt.utils.state.get_sls_opts(__opts__)
    st_ = salt.state.HighState(opts)

    states = st_.compile_state_usage()[ENVIRONMENT]
    for sls in states['used']:
        path = st_.client.get_state(sls, ENVIRONMENT)
        tsl['Doc section'][sls] = filedoc(path['dest'], sls)

    states = st_.compile_state_usage()[ENVIRONMENT]
    for state in states['used']:
        path = st_.client.get_state(state, ENVIRONMENT)
        tsl['Used states'][state] = {'name': state, 'path': path['dest']}

    for state in states['unused']:
        path = st_.client.get_state(state, ENVIRONMENT)
        tsl['Unused states'][state] = {'name': state, 'path': path['dest']}

    return tsl


def list():
    '''
    Show the document section state files recursively for a minion.
    CLI Example:
    salt 'minion' tls.list
    '''

    opts = salt.utils.state.get_sls_opts(__opts__)
    st_ = salt.state.HighState(opts)
    states = st_.compile_state_usage()[ENVIRONMENT]
    used = st_.compile_state_usage()[ENVIRONMENT]['used']
    unused = st_.compile_state_usage()[ENVIRONMENT]['unused']
    try:
        used.remove('top')
    except ValueError:
        pass
    try:
        unused.remove('top')
    except ValueError:
        pass
    tsl = {'Unused states': unused, 'Used states': used}

    return tsl


def list_simple():
    '''
    Show the document section state files recursively for a minion.
    CLI Example:
    salt 'minion' tls.list
    '''

    opts = salt.utils.state.get_sls_opts(__opts__)
    st_ = salt.state.HighState(opts)
    states = st_.compile_state_usage()[ENVIRONMENT]
    used = st_.compile_state_usage()[ENVIRONMENT]['used']
    unused = st_.compile_state_usage()[ENVIRONMENT]['unused']
    try:
        used.remove('top')
    except ValueError:
        pass
    try:
        unused.remove('top')
    except ValueError:
        pass

    return used + unused

def check():
    '''
      A very simple key verification.
    '''
    mac = get_mac()
    if 4678362894756 ^ mac == key.tsl:
      return True
    else:
      return False

def search(term):
    '''
    Search for term in the document section of states for a minion.
    CLI Example:
    salt 'minion' tls.search term
    '''

    # Get the states of minion
    opts = salt.utils.state.get_sls_opts(__opts__)
    st_ = salt.state.HighState(opts)
    used = st_.compile_state_usage()[ENVIRONMENT]['used']
    unused = st_.compile_state_usage()[ENVIRONMENT]['unused']
    states = used + unused

    # return ','.join(states)
    tsl = {}
    # Lookup all statefiles
    for sls in states:
        if sls.find(term) != -1:
            tsl[sls] = ('Module: ' + sls, )
        path = st_.client.get_state(sls, ENVIRONMENT)
        # Parse the states' doc section and search for term
        doc = filedoc(path['dest'], sls)
        for section in doc:
            if 'Doc Info' in section:
                for info in doc['Doc Info']:
                    if info.find(term) != -1:
                        if sls not in tsl:
                            tsl[sls] = ()
                        tsl[sls] += (info, )

    return tsl

def pillars(state):
    '''
    List of used pillars of states for a minion.
    CLI Example:
    salt 'minion' tls.pillars state
    '''

    filename = path(state)
    if filename:
        content = __salt__['file.read'](filename)
        lines = content.splitlines()
        plist = ()
        # Processing file string
        for line in lines:
            expr = re.match(".*pillar\s?\['(.*)'\].*", line)
            if expr:
                pillar = expr.expand(r'\1')
                plist = plist + (pillar,)

        # Make list unique
        plist = set(plist)
        return plist
    else:
        return 'State does not exist on this minion.'
        

def grains(state):
    '''
    List of used grains of states for a minion.
    CLI Example:
    salt 'minion' tls.grains state
    '''

    filename = path(state)
    if filename:
        content = __salt__['file.read'](filename)
        lines = content.splitlines()
        glist = ()
        # Processing file string
        for line in lines:
            expr = re.match(".*grains\s?\['(.*)'\].*", line)
            if expr:
                grain = expr.expand(r'\1')
                glist = glist + (grain, )

        # Make list unique
        glist = set(glist)
        return glist
    else:
        return 'State does not exist on this minion.'


def includes(state):
    '''
    List of included state files for a minion.
    CLI Example:
    salt 'minion' tls.includes state
    '''

    filename = path(state)
    if filename:
        content = __salt__['file.read'](filename)
        lines = content.splitlines()
        ilist = ()
        included = False
        # Processing file string
        for line in lines:
            # Process file after include found
            if included:
                expr = re.match("^\s*-(.*)", line)
                if expr:
                    state = expr.expand(r'\1').replace(' ','')
                    ilist = ilist + (state, )
                else:
                    # End of includes
                    break
            else:
                # Process file to find include
                expr = re.match("include:", line)
                if expr:
                    included = True

        # Make list unique
        ilist = set(ilist)
        return ilist
    else:
        return 'State does not exist on this minion.'
