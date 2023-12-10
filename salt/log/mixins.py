# pylint: disable=unused-import
from salt._logging.mixins import (
    ExcInfoOnLogLevelFormatMixin as ExcInfoOnLogLevelFormatMixIn,
)
from salt._logging.mixins import LoggingGarbageMixin as LoggingGarbageMixIn
from salt._logging.mixins import LoggingMixinMeta as LoggingMixInMeta
from salt._logging.mixins import LoggingProfileMixin as LoggingProfileMixIn
from salt._logging.mixins import LoggingTraceMixin as LoggingTraceMixIn
from salt.utils.versions import warn_until_date

# pylint: enable=unused-import

warn_until_date(
    "20240101",
    "Please stop using '{name}' and instead use 'salt._logging.mixins'. "
    "'{name}' will go away after {{date}}.".format(name=__name__),
)
