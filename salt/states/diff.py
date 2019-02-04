# -*- coding: utf-8 -*
'''
Smart diff files state
Simple usage to diff a file from the master and the minion :
.. code-block:: sls
    check_redhat-release:
      diff.diff_file:
        - file1: salt://configurations/RHEL7/redhat-release
        - file2: /etc/redhat-release
Only check the permissions of the file /etc/hosts :
.. code-block:: sls
    check_hosts:
      diff.diff_file:
        - file1: salt://configurations/RHEL7/hosts
        - file2: /etc/hosts
        - content: False
Check the /etc/krb5.conf and change it if it's different :
.. code-block:: sls
    check_krb5.conf
      diff.diff_file:
        - file1: salt://configurations/RHEL7/krb5.conf
        - file2: /etc/krb5.conf
        - change: True
Note :
It doesn't check the owner of the file.
If the file is not readable by salt on the master, you should make salt the owner.
'''
import re
import os
import random
from stat import *

def __virtual__():
    return True

def clean_file(filename):
    content = ""
    with open(filename) as f:
        for line in f:
            if re.search('^\s*#.*?$', line):  # Commentary
                pass
            elif re.match(r'^\s*$', line):  # empty line
                pass
            else:
                line = re.sub('\t+', ' ', line)  # Tab replaced
                line = re.sub(' +', ' ', line)  # multispaces replaced
                content += line
    return content.strip('\n\n')

def diff_file(name, file1, file2, content=True, change=False):
    '''
    1) Checking if the file exists.
    2) Checking if the permissions are the same.
    3) Checking if both file's content is the same.
    file1
        The name of the file on the salt-master.
    file2
        The name of the file on the minion.
    '''

    return_dict = {
        'name': 'diff_files',
        'changes': {},
        'result': False,
        'comment': ''
    }
    comments = ""
    same_content = False
    same_permissions = False

    # CHECKING IF THE FILE EXISTS
    # ----------------------------

    if os.path.isfile(file2):
        file_ok = True
    else:
        file_ok = False
        comments += "File doesn't exist (" + file2 + ")."
        return_dict['comment'] = comments
        if change:
            randFile = random.randint(0, 999999)
            ret = __states__['file.managed'](name='/tmp/salt_' + str(randFile), source=file1, mode='keep')
            if ret['result']:
                ret = os.system('cp -p /tmp/salt_' + str(randFile) + ' ' + file2)
                if ret == 0:
                    comments += "\nFile copied."
                    return_dict['comment'] = comments
                    return return_dict 
                else:
                    comments += "\nCouldn't copy the file."
                    return_dict['comment'] = comments
                    return return_dict 
            else:
                comments  += "\nCouldn't copy the file. Maybe it doesn't exist on the master or the permissions don't allow salt to copy it."
                return_dict['comment'] = comments
                return return_dict 
        else:
            return return_dict

    # CHECKING THE PERMISSION OF THE FILE
    # ------------------------------------

    randFile = random.randint(0,999999)
    ret = __states__['file.managed'](name='/tmp/salt_' + str(randFile), source=file1, mode='keep')
    if ret['result']:
        permissions1 = oct(os.stat('/tmp/salt_' + str(randFile))[ST_MODE])[-4:]
        permissions2 = oct(os.stat(file2)[ST_MODE])[-4:]
        
        if permissions1 == permissions2:
            same_permissions = True
            comments += "File's permissions are the same."
        else:
            same_permissions = False
            comments += "File's permissions are NOT the same (" + str(permissions2) + " VS " + str(permissions1) + ")."
# Modify here to directly change the permissions without the change parameter
            #ret = os.system('chmod ' + permissions1 + ' ' + file2)
            #if ret:
            #    comments += "\nCouldn't modify the permissions."
            #else:
            #    comments += '\nPermissions modified.'
    else:
        comments += "\nCouldn't copy the file. Maybe it doesn't exist on the master or the permissions don't allow salt to copy it."
        return_dict['comment'] = comments
        return return_dict


    # CHECKING THE CONTENT OF THE FILE
    # ---------------------------------

    if content is True:
        file1_content = clean_file('/tmp/salt_' + str(randFile))
        file2_content = clean_file(file2)
        if file1_content == file2_content:
            same_content = True

        if same_content:
            comments += "\nFile's content is the same."
        else:
            comments += "\nFile's content is NOT the same."

    # CONCLUSION
    # ----------

    if same_content and same_permissions and content is True:
        return_dict['result'] = True
    elif same_permissions and content is False:
        return_dict['result'] = True
    else: 
        if change: 
            if same_content is False and content is True:
                ret = os.system('cp -p /tmp/salt_' + str(randFile) + ' ' + file2)
                if ret == 0:
                    comments += "\nFile changed as requested."
                else:
                    comments += "\nCouldn't modifiy file's content."
            elif same_permissions is False:
                ret = os.system('chmod ' + permissions1 + ' ' + file2)
                if ret:
                    comments += "\nCouldn't modify the permissions."
                else:
                    comments += '\nPermissions modified.'

    os.remove('/tmp/salt_' + str(randFile))
    return_dict['comment'] = comments
    
    return return_dict
