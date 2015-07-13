# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    salt.config.schemas.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Minion configuration schema
'''

# Import python libs
from __future__ import absolute_import

# Import salt libs
from salt.utils.config import (Configuration,
                               IPv4Config,
                               )
from salt.config.schemas.common import (MinionDefaultInclude,
                                        IncludeConfig
                                        )

# XXX: THIS IS WAY TOO MINIMAL, BUT EXISTS TO IMPLEMENT salt-ssh


class MinionConfiguration(Configuration):

    # Because salt's configuration is very permissive with additioal
    # configuration settings, let's allow them in the schema or validation
    # would fail
    __allow_additional_items__ = True

    interface = IPv4Config(title='Interface')

    default_include = MinionDefaultInclude()
    include = IncludeConfig()
