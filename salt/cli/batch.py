# -*- coding: utf-8 -*-
"""
Execute batch runs
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy

# pylint: enable=import-error,no-name-in-module,redefined-builtin
import logging
import math
import time
from datetime import datetime, timedelta

import salt.client
import salt.exceptions
import salt.output

# Import salt libs
import salt.utils.stringutils

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range

log = logging.getLogger(__name__)


class Batch(object):
    """
    Manage the execution of batch runs
    """

    def __init__(self, opts, eauth=None, quiet=False, parser=None):
        self.opts = opts
        self.eauth = eauth if eauth else {}
        self.pub_kwargs = eauth if eauth else {}
        self.quiet = quiet
        self.local = salt.client.get_local_client(opts["conf_file"])
        self.minions, self.ping_gen, self.down_minions = self.__gather_minions()
        self.options = parser

    def __gather_minions(self):
        """
        Return a list of minions to use for the batch run
        """
        args = [
            self.opts["tgt"],
            "test.ping",
            [],
            self.opts["timeout"],
        ]

        selected_target_option = self.opts.get("selected_target_option", None)
        if selected_target_option is not None:
            args.append(selected_target_option)
        else:
            args.append(self.opts.get("tgt_type", "glob"))

        self.pub_kwargs["yield_pub_data"] = True
        ping_gen = self.local.cmd_iter(
            *args, gather_job_timeout=self.opts["gather_job_timeout"], **self.pub_kwargs
        )

        # Broadcast to targets
        fret = set()
        nret = set()
        for ret in ping_gen:
            if ("minions" and "jid") in ret:
                for minion in ret["minions"]:
                    nret.add(minion)
                continue
            else:
                try:
                    m = next(six.iterkeys(ret))
                except StopIteration:
                    if not self.quiet:
                        salt.utils.stringutils.print_cli(
                            "No minions matched the target."
                        )
                    break
                if m is not None:
                    fret.add(m)
        return (list(fret), ping_gen, nret.difference(fret))

    def get_bnum(self):
        """
        Return the active number of minions to maintain
        """
        partition = lambda x: float(x) / 100.0 * len(self.minions)
        try:
            if (
                isinstance(self.opts["batch"], six.string_types)
                and "%" in self.opts["batch"]
            ):
                res = partition(float(self.opts["batch"].strip("%")))
                if res < 1:
                    return int(math.ceil(res))
                else:
                    return int(res)
            else:
                return int(self.opts["batch"])
        except ValueError:
            if not self.quiet:
                salt.utils.stringutils.print_cli(
                    "Invalid batch data sent: {0}\nData must be in the "
                    "form of %10, 10% or 3".format(self.opts["batch"])
                )

    def __update_wait(self, wait):
        now = datetime.now()
        i = 0
        while i < len(wait) and wait[i] <= now:
            i += 1
        if i:
            del wait[:i]

    def run(self):
        """
        Execute the batch run
        """
        args = [
            [],
            self.opts["fun"],
            self.opts["arg"],
            self.opts["timeout"],
            "list",
        ]
        bnum = self.get_bnum()
        # No targets to run
        if not self.minions:
            return
        to_run = copy.deepcopy(self.minions)
        active = []
        ret = {}
        iters = []
        # wait the specified time before decide a job is actually done
        bwait = self.opts.get("batch_wait", 0)
        wait = []

        if self.options:
            show_jid = self.options.show_jid
            show_verbose = self.options.verbose
        else:
            show_jid = False
            show_verbose = False

        # the minion tracker keeps track of responses and iterators
        # - it removes finished iterators from iters[]
        # - if a previously detected minion does not respond, its
        #   added with an empty answer to ret{} once the timeout is reached
        # - unresponsive minions are removed from active[] to make
        #   sure that the main while loop finishes even with unresp minions
        minion_tracker = {}

        if not self.quiet:
            # We already know some minions didn't respond to the ping, so inform
            # the user we won't be attempting to run a job on them
            for down_minion in self.down_minions:
                salt.utils.stringutils.print_cli(
                    "Minion {0} did not respond. No job will be sent.".format(
                        down_minion
                    )
                )

        # Iterate while we still have things to execute
        while len(ret) < len(self.minions):
            next_ = []
            if bwait and wait:
                self.__update_wait(wait)
            if len(to_run) <= bnum - len(wait) and not active:
                # last bit of them, add them all to next iterator
                while to_run:
                    next_.append(to_run.pop())
            else:
                for i in range(bnum - len(active) - len(wait)):
                    if to_run:
                        minion_id = to_run.pop()
                        if isinstance(minion_id, dict):
                            next_.append(minion_id.keys()[0])
                        else:
                            next_.append(minion_id)

            active += next_
            args[0] = next_

            if next_:
                if not self.quiet:
                    salt.utils.stringutils.print_cli(
                        "\nExecuting run on {0}\n".format(sorted(next_))
                    )
                # create a new iterator for this batch of minions
                new_iter = self.local.cmd_iter_no_block(
                    *args,
                    raw=self.opts.get("raw", False),
                    ret=self.opts.get("return", ""),
                    show_jid=show_jid,
                    verbose=show_verbose,
                    gather_job_timeout=self.opts["gather_job_timeout"],
                    **self.eauth
                )
                # add it to our iterators and to the minion_tracker
                iters.append(new_iter)
                minion_tracker[new_iter] = {}
                # every iterator added is 'active' and has its set of minions
                minion_tracker[new_iter]["minions"] = next_
                minion_tracker[new_iter]["active"] = True

            else:
                time.sleep(0.02)
            parts = {}

            # see if we found more minions
            for ping_ret in self.ping_gen:
                if ping_ret is None:
                    break
                m = next(six.iterkeys(ping_ret))
                if m not in self.minions:
                    self.minions.append(m)
                    to_run.append(m)

            for queue in iters:
                try:
                    # Gather returns until we get to the bottom
                    ncnt = 0
                    while True:
                        part = next(queue)
                        if part is None:
                            time.sleep(0.01)
                            ncnt += 1
                            if ncnt > 5:
                                break
                            continue
                        if self.opts.get("raw"):
                            parts.update({part["data"]["id"]: part})
                            if part["data"]["id"] in minion_tracker[queue]["minions"]:
                                minion_tracker[queue]["minions"].remove(
                                    part["data"]["id"]
                                )
                            else:
                                salt.utils.stringutils.print_cli(
                                    "minion {0} was already deleted from tracker, probably a duplicate key".format(
                                        part["id"]
                                    )
                                )
                        else:
                            parts.update(part)
                            for id in part:
                                if id in minion_tracker[queue]["minions"]:
                                    minion_tracker[queue]["minions"].remove(id)
                                else:
                                    salt.utils.stringutils.print_cli(
                                        "minion {0} was already deleted from tracker, probably a duplicate key".format(
                                            id
                                        )
                                    )
                except StopIteration:
                    # if a iterator is done:
                    # - set it to inactive
                    # - add minions that have not responded to parts{}

                    # check if the tracker contains the iterator
                    if queue in minion_tracker:
                        minion_tracker[queue]["active"] = False

                        # add all minions that belong to this iterator and
                        # that have not responded to parts{} with an empty response
                        for minion in minion_tracker[queue]["minions"]:
                            if minion not in parts:
                                parts[minion] = {}
                                parts[minion]["ret"] = {}

            for minion, data in six.iteritems(parts):
                if minion in active:
                    active.remove(minion)
                    if bwait:
                        wait.append(datetime.now() + timedelta(seconds=bwait))
                # Munge retcode into return data
                failhard = False
                if (
                    "retcode" in data
                    and isinstance(data["ret"], dict)
                    and "retcode" not in data["ret"]
                ):
                    data["ret"]["retcode"] = data["retcode"]
                    if self.opts.get("failhard") and data["ret"]["retcode"] > 0:
                        failhard = True
                else:
                    if self.opts.get("failhard") and data["retcode"] > 0:
                        failhard = True

                if self.opts.get("raw"):
                    ret[minion] = data
                    yield data
                else:
                    ret[minion] = data["ret"]
                    yield {minion: data["ret"]}
                if not self.quiet:
                    ret[minion] = data["ret"]
                    data[minion] = data.pop("ret")
                    if "out" in data:
                        out = data.pop("out")
                    else:
                        out = None
                    salt.output.display_output(data, out, self.opts)
                if failhard:
                    log.error(
                        "Minion %s returned with non-zero exit code. "
                        "Batch run stopped due to failhard",
                        minion,
                    )
                    raise StopIteration

            # remove inactive iterators from the iters list
            for queue in minion_tracker:
                # only remove inactive queues
                if not minion_tracker[queue]["active"] and queue in iters:
                    iters.remove(queue)
                    # also remove the iterator's minions from the active list
                    for minion in minion_tracker[queue]["minions"]:
                        if minion in active:
                            active.remove(minion)
                            if bwait:
                                wait.append(datetime.now() + timedelta(seconds=bwait))
