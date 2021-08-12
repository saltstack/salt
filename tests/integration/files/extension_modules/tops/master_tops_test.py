import logging

log = logging.getLogger(__name__)


def __virtual__():
    log.info("master tops test loaded")
    return "master_tops_test"


def top(**kwargs):
    log.info("master_tops_test")
    return {"base": ["master_tops_test"]}
