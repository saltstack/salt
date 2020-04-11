# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import random
import string

from salt.ext.six.moves import range


def random_name(size=6):
    """
    Generates a random cloud instance name
    """
    return "CLOUD-TEST-" + "".join(
        random.choice(string.ascii_uppercase + string.digits) for x in range(size)
    )
