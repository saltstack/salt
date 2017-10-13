# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.utils.schema import (EventSchema,
                               StringItem)


def schemas():
    return [AuthenticationEventSchema]


class AuthenticationEventSchema(EventSchema):
    tag = 'salt/auth'
    title = 'Authentication Event'
    description = 'Event fired when a minion performs an authentication check with the master'

    id = StringItem(title='id',
                    description='The minion id which sent the event',
                    min_length=1,
                    required=True)

    act = StringItem(title='act',
                    description='The current status of the minion key',
                    required=True,
                    enum=('accept', 'pend', 'reject'))

    pub = StringItem(title='pub',
                    description='The minion public key',
                    min_length=1,
                    required=True)
