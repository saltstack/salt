import logging
import subprocess

import pytest

import salt.utils.platform
from tests.pytests.integration.cluster.conftest import (
    cluster_cache_path,
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_minion_1,
    cluster_pki_path,
    cluster_shared_path,
)

log = logging.getLogger(__name__)
