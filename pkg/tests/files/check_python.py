import sys

import salt.utils.data

user_arg = sys.argv

if user_arg[1] == "raise":
    raise Exception("test")

if salt.utils.data.is_true(user_arg[1]):
    sys.exit(0)
else:
    sys.exit(1)
