# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.utils.schema import (EventSchema,
                               StringItem,
                               DateTimeItem)


def schemas():
    return [TestEventSchema]


class TestEventSchema(EventSchema):
    tag = 'evt1'
    __allow_additional_items__ = False
    data = StringItem(title='data',
                    description='The current status of the minion key',
                    required=True,)

    _stamp = DateTimeItem(title='data',
                    description='The current status of the minion key',
                    required=True,)
