"""
This is the default compound matcher function.
"""

import logging

import salt.loader
import salt.utils.minions

HAS_RANGE = False
try:
    import seco.range  # pylint: disable=unused-import

    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def _load_matchers(opts):
    """
    Store matchers in __context__ so they're only loaded once
    """
    __context__["matchers"] = {}
    __context__["matchers"] = salt.loader.matchers(opts)


def match(tgt, opts=None, minion_id=None):
    """
    Runs the compound target check
    """
    if not opts:
        opts = __opts__
    nodegroups = opts.get("nodegroups", {})
    if "matchers" not in __context__:
        _load_matchers(opts)
    if not minion_id:
        minion_id = opts.get("id")

    if not isinstance(tgt, str) and not isinstance(tgt, (list, tuple)):
        log.error("Compound target received that is neither string, list nor tuple")
        return False
    log.debug("compound_match: %s ? %s", minion_id, tgt)
    ref = {
        "G": "grain",
        "P": "grain_pcre",
        "I": "pillar",
        "J": "pillar_pcre",
        "L": "list",
        "N": None,  # Nodegroups should already be expanded
        "S": "ipcidr",
        "E": "pcre",
    }
    if HAS_RANGE:
        ref["R"] = "range"

    results = []
    opers = ["and", "or", "not", "(", ")"]

    if isinstance(tgt, str):
        words = tgt.split()
    else:
        # we make a shallow copy in order to not affect the passed in arg
        words = tgt[:]

    while words:
        word = words.pop(0)
        target_info = salt.utils.minions.parse_target(word)

        # Easy check first
        if word in opers:
            if results:
                if results[-1] == "(" and word in ("and", "or"):
                    log.error('Invalid beginning operator after "(": %s', word)
                    return False
                if word == "not":
                    if not results[-1] in ("and", "or", "("):
                        results.append("and")
                results.append(word)
            else:
                # seq start with binary oper, fail
                if word not in ["(", "not"]:
                    log.error("Invalid beginning operator: %s", word)
                    return False
                results.append(word)

        elif target_info and target_info["engine"]:
            if "N" == target_info["engine"]:
                # if we encounter a node group, just evaluate it in-place
                decomposed = salt.utils.minions.nodegroup_comp(
                    target_info["pattern"], nodegroups
                )
                if decomposed:
                    words = decomposed + words
                continue

            engine = ref.get(target_info["engine"])
            if not engine:
                # If an unknown engine is called at any time, fail out
                log.error(
                    'Unrecognized target engine "%s" for target expression "%s"',
                    target_info["engine"],
                    word,
                )
                return False

            engine_args = [target_info["pattern"]]
            engine_kwargs = {"opts": opts, "minion_id": minion_id}
            if target_info["delimiter"]:
                engine_kwargs["delimiter"] = target_info["delimiter"]

            results.append(
                str(
                    __context__["matchers"]["{}_match.match".format(engine)](
                        *engine_args, **engine_kwargs
                    )
                )
            )

        else:
            # The match is not explicitly defined, evaluate it as a glob
            results.append(
                str(__context__["matchers"]["glob_match.match"](word, opts, minion_id))
            )

    results = " ".join(results)
    log.debug('compound_match %s ? "%s" => "%s"', minion_id, tgt, results)
    try:
        return eval(results)  # pylint: disable=W0123
    except Exception:  # pylint: disable=broad-except
        log.error("Invalid compound target: %s for results: %s", tgt, results)
    return False
