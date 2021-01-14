#!/usr/bin/python
from __future__ import print_function

import getopt
import os
import sys


def display_help():
    print("####################################################################")
    print("#                                                                  #")
    print("# File: portable.py                                                #")
    print("# Description:                                                     #")
    print("#   - search and replace within a binary file                      #")
    print("#                                                                  #")
    print("# Parameters:                                                      #")
    print("#   -f, --file    :  target file                                   #")
    print("#   -s, --search  :  term to search for                            #")
    print("#                    Default is the base path for the python       #")
    print("#                    executable that is running this script.       #")
    print("#                    In Py2 that would be C:\\Python27             #")
    print("#   -r, --replace :  replace with this                             #")
    print('#                    default is ".."                               #')
    print("#                                                                  #")
    print("# example:                                                         #")
    print("#  portable.py -f <target_file> -s <search_term> -r <replace_term> #")
    print("#                                                                  #")
    print("####################################################################")
    sys.exit(2)


def main(argv):
    target = ""
    search = os.path.dirname(sys.executable)
    replace = ".."
    try:
        opts, args = getopt.getopt(argv, "hf:s:r:", ["file=", "search=", "replace="])
    except getopt.GetoptError:
        display_help()
    for opt, arg in opts:
        if opt == "-h":
            display_help()
        elif opt in ("-f", "--file"):
            target = arg
        elif opt in ("-s", "--search"):
            search = arg
        elif opt in ("-r", "--replace"):
            replace = arg
    if target == "":
        display_help()

    if sys.version_info >= (3, 0):
        search = search.encode("utf-8")
        replace = replace.encode("utf-8")
    f = open(target, "rb").read()
    f = f.replace(search, replace)
    f = f.replace(search.lower(), replace)
    open(target, "wb").write(f)


if __name__ == "__main__":
    main(sys.argv[1:])
