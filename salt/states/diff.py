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

# Import Python Libs
from __future__ import absolute_import
import re
import os
import random
from stat import ST_MODE

# Import Salt libs
import salt.utils.files


def __virtual__():
    return True


def clean_file(filename):
    content = ""
    with salt.utils.files.fopen(filename) as file:
        for line in file:
            if re.search(r'^\s*#.*?$', line):  # Commentary
                pass
            elif re.match(r'^\s*$', line):  # Empty line
                pass
            else:
                line = re.sub('\t+', ' ', line)  # Tab replaced
                line = re.sub(' +', ' ', line)  # Multispaces replaced
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

    # CHECKING IF THE FILE EXISTS
    # ----------------------------

    if not os.path.isfile(file2):
        comments += "File doesn't exist (" + file2 + ")."
        return_dict['comment'] = comments
        if change:
            ret = __states__['file.managed'](name=file2, source=file1, mode='keep')
            if ret['result']:
                comments += "\nFile copied."
                return_dict['comment'] = comments
            else:
                comments += "\nCouldn't copy the file on the minion. Maybe it doesn't exist on the master or the permissions don't allow salt to copy it."
                return_dict['comment'] = comments
        return return_dict

    # CHECKING THE PERMISSIONS OF THE FILE
    # ------------------------------------

    rand_file = '/tmp/salt_' + str(random.randint(0, 999999))
    ret = __states__['file.managed'](name=rand_file, source=file1, mode='keep')
    if ret['result']:
        permissions1 = oct(os.stat(rand_file)[ST_MODE])[-4:]
        permissions2 = oct(os.stat(file2)[ST_MODE])[-4:]

        if permissions1 == permissions2:
            same_permissions = True
            comments += "File's permissions are the same."
        else:
            same_permissions = False
            comments += "File's permissions are NOT the same (" + str(permissions2) + " VS " + str(permissions1) + ")."
    else:
        comments += "\nCouldn't copy the file on the minion. Maybe it doesn't exist on the master or the permissions don't allow salt to copy it."
        return_dict['comment'] = comments
        return return_dict

    # CHECKING THE CONTENT OF THE FILE
    # ---------------------------------

    if content is True:
        file1_content = clean_file(rand_file)
        file2_content = clean_file(file2)
        if file1_content == file2_content:
            same_content = True
            comments += "\nFile's content is the same."
        else:
            same_content = False
            comments += "\nFile's content is NOT the same."

    # CONCLUSION
    # ----------

    if same_content and same_permissions and content:
        return_dict['result'] = True
    elif same_permissions and content is False:
        return_dict['result'] = True
    else:
        if change:
            if same_content is False and content is True:
                ret = os.system('cp -p ' + rand_file + ' ' + file2)
                if ret == 0:
                    comments += "\nFile changed as requested."
                else:
                    comments += "\nCouldn't modify file's content."
            elif same_permissions is False:
                ret = os.system('chmod ' + permissions1 + ' ' + file2)
                if ret:
                    comments += "\nCouldn't modify the permissions."
                else:
                    comments += '\nPermissions modified.'

    os.remove(rand_file)
    return_dict['comment'] = comments

    return return_dict
