"""
This is the default list matcher.
"""

import logging

log = logging.getLogger(__name__)


def match(tgt, opts=None, minion_id=None):
    """
    Determines if this host is on the list
    """

    if not opts:
        opts = __opts__
    if not minion_id:
        minion_id = opts.get("id")

    try:
        if (
            ",{},".format(minion_id) in tgt
            or tgt.startswith(minion_id + ",")
            or tgt.endswith("," + minion_id)
        ):
            return True
        # tgt is a string, which we know because the if statement above did not
        # cause one of the exceptions being caught. Therefore, look for an
        # exact match. (e.g. salt -L foo test.ping)
        return minion_id == tgt
    except (AttributeError, TypeError):
        # tgt is not a string, maybe it's a sequence type?
        try:
            return minion_id in tgt
        except Exception:  # pylint: disable=broad-except
            # tgt was likely some invalid type
            return False

    # We should never get here based on the return statements in the logic
    # above. If we do, it is because something above changed, and should be
    # considered as a bug. Log a warning to help us catch this.
    log.warning(
        "List matcher unexpectedly did not return, for target %s, "
        "this is probably a bug.",
        tgt,
    )
    return False
