# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.log.mixins
    ~~~~~~~~~~~~~~~

    .. versionadded:: 0.17.0

    Some mix-in classes to be used in salt's logging
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
# pylint: disable=unused-import
from salt._logging.mixins import (
    ExcInfoOnLogLevelFormatMixin as ExcInfoOnLogLevelFormatMixIn,
)
from salt._logging.mixins import LoggingGarbageMixin as LoggingGarbageMixIn
from salt._logging.mixins import LoggingMixinMeta as LoggingMixInMeta
from salt._logging.mixins import LoggingProfileMixin as LoggingProfileMixIn
from salt._logging.mixins import LoggingTraceMixin as LoggingTraceMixIn
from salt._logging.mixins import NewStyleClassMixin as NewStyleClassMixIn

# pylint: enable=unused-import
# from salt.utils.versions import warn_until_date
# warn_until_date(
#    '20220101',
#    'Please stop using \'{name}\' and instead use \'salt._logging.mixins\'. '
#    '\'{name}\' will go away after {{date}}.'.format(
#        name=__name__
#    )
# )
