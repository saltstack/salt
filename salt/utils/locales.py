"""
the locale utils used by salt
"""

import sys

from salt.utils.decorators import memoize as real_memoize


@real_memoize
def get_encodings():
    """
    return a list of string encodings to try
    """
    encodings = [__salt_system_encoding__]

    try:
        sys_enc = sys.getdefaultencoding()
    except ValueError:  # system encoding is nonstandard or malformed
        sys_enc = None
    if sys_enc and sys_enc not in encodings:
        encodings.append(sys_enc)

    for enc in ["utf-8", "latin-1"]:
        if enc not in encodings:
            encodings.append(enc)

    return encodings


def split_locale(loc):
    """
    Split a locale specifier.  The general format is

    language[_territory][.codeset][@modifier] [charmap]

    For example:

    ca_ES.UTF-8@valencia UTF-8
    """

    def split(st, char):
        """
        Split a string `st` once by `char`; always return a two-element list
        even if the second element is empty.
        """
        split_st = st.split(char, 1)
        if len(split_st) == 1:
            split_st.append("")
        return split_st

    comps = {}
    work_st, comps["charmap"] = split(loc, " ")
    work_st, comps["modifier"] = split(work_st, "@")
    work_st, comps["codeset"] = split(work_st, ".")
    comps["language"], comps["territory"] = split(work_st, "_")
    return comps


def join_locale(comps):
    """
    Join a locale specifier split in the format returned by split_locale.
    """
    loc = comps["language"]
    if comps.get("territory"):
        loc += "_" + comps["territory"]
    if comps.get("codeset"):
        loc += "." + comps["codeset"]
    if comps.get("modifier"):
        loc += "@" + comps["modifier"]
    if comps.get("charmap"):
        loc += " " + comps["charmap"]
    return loc


def normalize_locale(loc):
    """
    Format a locale specifier according to the format returned by `locale -a`.
    """
    comps = split_locale(loc)
    comps["territory"] = comps["territory"].upper()
    comps["codeset"] = comps["codeset"].lower().replace("-", "")
    comps["charmap"] = ""
    return join_locale(comps)
