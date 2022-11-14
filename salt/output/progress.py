"""
Display return data as a progress bar
"""


try:
    import progressbar

    HAS_PROGRESSBAR = True
except ImportError:
    HAS_PROGRESSBAR = False


def __virtual__():
    return True if HAS_PROGRESSBAR else False


def output(ret, bar, **kwargs):  # pylint: disable=unused-argument
    """
    Update the progress bar
    """
    if "return_count" in ret:
        val = ret["return_count"]
        # Avoid to fail if targets are behind a syndic. In this case actual return count will be
        # higher than targeted by MoM itself.
        # TODO: implement a way to get the proper target minions count and remove this workaround.
        # Details are in #44239.
        if val > bar.maxval:
            bar.maxval = val
        bar.update(val)
    return ""


def progress_iter(progress):
    """
    Initialize and return a progress bar iter
    """
    widgets = [
        progressbar.Percentage(),
        " ",
        progressbar.Bar(),
        " ",
        progressbar.Timer(),
        " Returns: [",
        progressbar.Counter(),
        "/{}]".format(progress["minion_count"]),
    ]
    bar = progressbar.ProgressBar(widgets=widgets, maxval=progress["minion_count"])
    bar.start()
    return bar
