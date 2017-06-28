#!/usr/bin/python
from __future__ import print_function

import sys
import os.path
import getopt


def display_help():
    print('####################################################################')
    print('#                                                                  #')
    print('# File: portable.py                                                #')
    print('# Description:                                                     #')
    print('#   - search and replace within a binary file                      #')
    print('#                                                                  #')
    print('# Parameters:                                                      #')
    print('#   -f, --file    :  target file                                   #')
    print('#   -s, --search  :  term to search for                            #')
    print('#                    default is "C:\Python"                        #')
    print('#   -r, --replace :  replace with this                             #')
    print('#                    default is ".."                               #')
    print('#                                                                  #')
    print('# example:                                                         #')
    print('#  portable.py -f <target_file> -s <search_term> -r <replace_term> #')
    print('#                                                                  #')
    print('####################################################################')
    sys.exit(2)


def main(argv):
    target = ''
    python_dir = 'Python{0}{1}'.format(sys.version_info[0], sys.version_info[1])
    if sys.version_info >= (3, 5):
        from win32com.shell import shellcon, shell
        search = shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAM_FILES, 0, 0)
        search = os.path.join(search, python_dir)
    else:
        search = os.path.join('C:\\', python_dir)
    replace = '..'
    try:
        opts, args = getopt.getopt(argv,"hf:s:r:",["file=","search=", "replace="])
    except getopt.GetoptError:
        display_help()
    for opt, arg in opts:
        if opt == '-h':
            display_help()
        elif opt in ("-f", "--file"):
            target = arg
        elif opt in ("-s", "--search"):
            search = arg
        elif opt in ("-r", "--replace"):
            replace = arg
    if target == '':
        display_help()

    if sys.version_info >= (3, 0):
        search = search.encode('utf-8')
        replace = replace.encode('utf-8')
    f = open( target, 'rb' ).read()
    f = f.replace( search, replace )
    f = f.replace( search.lower(), replace )
    open( target, 'wb' ).write(f)


if __name__ == "__main__":
    main(sys.argv[1:])
