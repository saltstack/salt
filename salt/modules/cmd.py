'''
A module for shelling out

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions
'''

import subprocess
import tempfile

def run(cmd, cwd='/root'):
    '''
    Execute the passed command and return the output as a string

    CLI Example:
    salt '*' cmd.run "ls -l | grep foo | awk '{print $2}'"
    '''
    return subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]

def run_stdout(cmd, cwd='/root'):
    '''
    Execute a command, and only return the standard out 

    CLI Example:
    salt '*' cmd.run "ls -l | grep foo | awk '{print $2}'"
    '''
    return subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE).communicate()[0]

def run_stderr(cmd, cwd='/root'):
    '''
    Execute a command and only return the standard error

    CLI Example:
    salt '*' cmd.run "ls -l | grep foo | awk '{print $2}'"
    '''
    return subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stderr=subprocess.PIPE).communicate()[0]

def run_all(cmd, cwd='/root'):
    '''
    Execute the passed command and return a dict of return data

    CLI Example:
    salt '*' cmd.run_all "ls -l | grep foo | awk '{print $2}'"
    '''
    ret = {}
    proc =  subprocess.Popen(cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out = proc.communicate()
    ret['stdout'] = out[0]
    ret['stderr'] = out[1]
    ret['retcode'] = out.returncode
    return ret

def retcode(cmd, cwd='/root'):
    '''
    Execute a shell command and return the command's return code.

    CLI Example:
    salt '*' cmd.retcode "file /bin/bash"
    '''
    return subprocess.call(cmd, shell=True, cwd=cwd)

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
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
