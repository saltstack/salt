'''
A module for shelling out

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions
'''

import subprocess
import tempfile

def run(cmd):
    '''
    Execute the passed command and return the output as a string

    CLI Example:
    salt '*' cmd.run "ls -l | grep foo | awk '{print $2}'"
    '''
    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]

def run_stdout(cmd):
    '''
    Execute a command, and only return the standard out 

    CLI Example:
    salt '*' cmd.run "ls -l | grep foo | awk '{print $2}'"
    '''
    return subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]

def run_stderr(cmd):
    '''
    Execute a command and only return the standard error

    CLI Example:
    salt '*' cmd.run "ls -l | grep foo | awk '{print $2}'"
    '''
    return subprocess.Popen(cmd,
            shell=True,
            stderr=subprocess.PIPE).communicate()[0]

def exec_code(lang, code):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout and stderr will be returned

    CLI Example:
    salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    cfn = tempfile.mkstemp()
    open(cfn, 'w+').write(code)
    return subprocess.Popen(lang + ' ' + cfn,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
