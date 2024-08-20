"""
    salt.utils.master
    -----------------

    Utilities that can only be used on a salt master.

"""

import logging
import os
import signal
from threading import Event, Thread

import salt.cache
import salt.client
import salt.config
import salt.payload
import salt.pillar
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.minions
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.verify
from salt.exceptions import SaltException
from salt.utils.cache import CacheCli as cache_cli
from salt.utils.process import Process
from salt.utils.zeromq import zmq

log = logging.getLogger(__name__)


def get_running_jobs(opts):
    """
    Return the running jobs on this master
    """

    ret = []
    proc_dir = os.path.join(opts["cachedir"], "proc")
    if not os.path.isdir(proc_dir):
        return ret
    for fn_ in os.listdir(proc_dir):
        path = os.path.join(proc_dir, fn_)
        try:
            data = _read_proc_file(path, opts)
            if data is not None:
                ret.append(data)
        except OSError:
            # proc files may be removed at any time during this process by
            # the master process that is executing the JID in question, so
            # we must ignore ENOENT during this process
            log.trace("%s removed during processing by master process", path)
    return ret


def clean_proc_dir(opts):
    """
    Clean out old tracked jobs running on the master
    Generally, anything tracking a job should remove the job
    once the job has finished. However, this will remove any
    jobs that for some reason were not properly removed
    when finished or errored.
    """
    proc_dir = os.path.join(opts["cachedir"], "proc")
    for fn_ in os.listdir(proc_dir):
        proc_file = os.path.join(proc_dir, fn_)
        try:
            data = _read_proc_file(proc_file, opts)
        except OSError:
            # proc files may be removed at any time during this process by
            # the master process that is executing the JID in question, so
            # we must ignore ENOENT during this process
            log.trace("%s removed during processing by master process", proc_file)
            continue
        if not data:
            try:
                log.warning(
                    "Found proc file %s without proper data. Removing from tracked proc files.",
                    proc_file,
                )
                os.remove(proc_file)
            except OSError as err:
                log.error("Unable to remove proc file: %s.", err)
            continue
        if not _check_cmdline(data):
            try:
                log.warning(
                    "PID %s not owned by salt or no longer running. Removing tracked proc file %s",
                    data["pid"],
                    proc_file,
                )
                os.remove(proc_file)
            except OSError as err:
                log.error("Unable to remove proc file: %s.", err)


def _read_proc_file(path, opts):
    """
    Return a dict of JID metadata, or None
    """
    with salt.utils.files.fopen(path, "rb") as fp_:
        buf = fp_.read()
        fp_.close()
        if buf:
            data = salt.payload.loads(buf)
        else:
            # Proc file is empty, remove
            try:
                os.remove(path)
            except OSError:
                log.debug("Unable to remove proc file %s.", path)
            return None
    if not isinstance(data, dict):
        # Invalid payload object
        return None
    if not salt.utils.process.os_is_running(data["pid"]):
        # The process is no longer running, clear out the file and
        # continue
        try:
            os.remove(path)
        except OSError:
            log.debug("Unable to remove proc file %s.", path)
        return None

    if not _check_cmdline(data):
        pid = data.get("pid")
        if pid:
            log.warning("PID %s exists but does not appear to be a salt process.", pid)
        try:
            os.remove(path)
        except OSError:
            log.debug("Unable to remove proc file %s.", path)
        return None
    return data


def _check_cmdline(data):
    """
    In some cases where there are an insane number of processes being created
    on a system a PID can get recycled or assigned to a non-Salt process.
    On Linux this fn checks to make sure the PID we are checking on is actually
    a Salt process.

    For non-Linux systems we punt and just return True
    """
    if not salt.utils.platform.is_linux():
        return True
    pid = data.get("pid")
    if not pid:
        return False
    if not os.path.isdir("/proc"):
        return True
    path = os.path.join(f"/proc/{pid}/cmdline")
    if not os.path.isfile(path):
        return False
    try:
        with salt.utils.files.fopen(path, "rb") as fp_:
            return b"salt" in fp_.read()
    except OSError:
        return False


class MasterPillarUtil:
    """
    Helper utility for easy access to targeted minion grain and
    pillar data, either from cached data on the master or retrieved
    on demand, or (by default) both.

    The minion pillar data returned in get_minion_pillar() is
    compiled directly from salt.pillar.Pillar on the master to
    avoid any possible 'pillar poisoning' from a compromised or
    untrusted minion.

    ** However, the minion grains are still possibly entirely
    supplied by the minion. **

    Example use case:
        For runner modules that need access minion pillar data,
        MasterPillarUtil.get_minion_pillar should be used instead
        of getting the pillar data by executing the "pillar" module
        on the minions:

        # my_runner.py
        tgt = 'web*'
        pillar_util = salt.utils.master.MasterPillarUtil(tgt, tgt_type='glob', opts=__opts__)
        pillar_data = pillar_util.get_minion_pillar()
    """

    def __init__(
        self,
        tgt="",
        tgt_type="glob",
        saltenv=None,
        use_cached_grains=True,
        use_cached_pillar=True,
        grains_fallback=True,
        pillar_fallback=True,
        opts=None,
    ):

        log.debug("New instance of %s created.", self.__class__.__name__)
        if opts is None:
            log.error("%s: Missing master opts init arg.", self.__class__.__name__)
            raise SaltException(
                f"{self.__class__.__name__}: Missing master opts init arg."
            )
        else:
            self.opts = opts
        self.tgt = tgt
        self.tgt_type = tgt_type
        self.saltenv = saltenv
        self.use_cached_grains = use_cached_grains
        self.use_cached_pillar = use_cached_pillar
        self.grains_fallback = grains_fallback
        self.pillar_fallback = pillar_fallback
        self.cache = salt.cache.factory(opts)
        log.debug(
            "Init settings: tgt: '%s', tgt_type: '%s', saltenv: '%s', "
            "use_cached_grains: %s, use_cached_pillar: %s, "
            "grains_fallback: %s, pillar_fallback: %s",
            tgt,
            tgt_type,
            saltenv,
            use_cached_grains,
            use_cached_pillar,
            grains_fallback,
            pillar_fallback,
        )

    def _get_cached_mine_data(self, *minion_ids):
        # Return one dict with the cached mine data of the targeted minions
        mine_data = {minion_id: {} for minion_id in minion_ids}
        if not self.opts.get("minion_data_cache", False) and not self.opts.get(
            "enforce_mine_cache", False
        ):
            log.debug(
                "Skipping cached mine data minion_data_cache"
                "and enfore_mine_cache are both disabled."
            )
            return mine_data
        if not minion_ids:
            minion_ids = self.cache.list("minions")
        for minion_id in minion_ids:
            if not salt.utils.verify.valid_id(self.opts, minion_id):
                continue
            mdata = self.cache.fetch(f"minions/{minion_id}", "mine")
            if isinstance(mdata, dict):
                mine_data[minion_id] = mdata
        return mine_data

    def _get_cached_minion_data(self, *minion_ids):
        # Return two separate dicts of cached grains and pillar data of the
        # minions
        grains = {minion_id: {} for minion_id in minion_ids}
        pillars = grains.copy()
        if not self.opts.get("minion_data_cache", False):
            log.debug("Skipping cached data because minion_data_cache is not enabled.")
            return grains, pillars
        if not minion_ids:
            minion_ids = self.cache.list("minions")
        for minion_id in minion_ids:
            if not salt.utils.verify.valid_id(self.opts, minion_id):
                continue
            mdata = self.cache.fetch(f"minions/{minion_id}", "data")
            if not isinstance(mdata, dict):
                log.warning(
                    "cache.fetch should always return a dict. ReturnedType: %s,"
                    " MinionId: %s",
                    type(mdata).__name__,
                    minion_id,
                )
                continue
            if "grains" in mdata:
                grains[minion_id] = mdata["grains"]
            if "pillar" in mdata:
                pillars[minion_id] = mdata["pillar"]
        return grains, pillars

    def _get_live_minion_grains(self, minion_ids):
        # Returns a dict of grains fetched directly from the minions
        log.debug('Getting live grains for minions: "%s"', minion_ids)
        with salt.client.get_local_client(self.opts["conf_file"]) as client:
            return client.cmd(
                ",".join(minion_ids),
                "grains.items",
                timeout=self.opts["timeout"],
                tgt_type="list",
            )

    def _get_live_minion_pillar(self, minion_id=None, minion_grains=None):
        # Returns a dict of pillar data for one minion
        if minion_id is None:
            return {}
        if not minion_grains:
            log.warning("Cannot get pillar data for %s: no grains supplied.", minion_id)
            return {}
        log.debug("Getting live pillar for %s", minion_id)
        pillar = salt.pillar.Pillar(
            self.opts, minion_grains, minion_id, self.saltenv, self.opts["ext_pillar"]
        )
        log.debug("Compiling pillar for %s", minion_id)
        ret = pillar.compile_pillar()
        return ret

    def _get_minion_grains(self, *minion_ids, **kwargs):
        # Get the minion grains either from cache or from a direct query
        # on the minion. By default try to use cached grains first, then
        # fall back to querying the minion directly.
        ret = {}
        cached_grains = kwargs.get("cached_grains", {})
        cret = {}
        lret = {}
        if self.use_cached_grains:
            cret = {
                minion_id: mcache
                for (minion_id, mcache) in cached_grains.items()
                if mcache
            }
            missed_minions = [
                minion_id for minion_id in minion_ids if minion_id not in cret
            ]
            log.debug("Missed cached minion grains for: %s", missed_minions)
            if self.grains_fallback:
                lret = self._get_live_minion_grains(missed_minions)
            ret = dict(
                list({minion_id: {} for minion_id in minion_ids}.items())
                + list(lret.items())
                + list(cret.items())
            )
        else:
            lret = self._get_live_minion_grains(minion_ids)
            missed_minions = [
                minion_id for minion_id in minion_ids if minion_id not in lret
            ]
            log.debug("Missed live minion grains for: %s", missed_minions)
            if self.grains_fallback:
                cret = {
                    minion_id: mcache
                    for (minion_id, mcache) in cached_grains.items()
                    if mcache
                }
            ret = dict(
                list({minion_id: {} for minion_id in minion_ids}.items())
                + list(lret.items())
                + list(cret.items())
            )
        return ret

    def _get_minion_pillar(self, *minion_ids, **kwargs):
        # Get the minion pillar either from cache or from a direct query
        # on the minion. By default try use the cached pillar first, then
        # fall back to rendering pillar on demand with the supplied grains.
        ret = {}
        grains = kwargs.get("grains", {})
        cached_pillar = kwargs.get("cached_pillar", {})
        cret = {}
        lret = {}
        if self.use_cached_pillar:
            cret = {
                minion_id: mcache
                for (minion_id, mcache) in cached_pillar.items()
                if mcache
            }
            missed_minions = [
                minion_id for minion_id in minion_ids if minion_id not in cret
            ]
            log.debug("Missed cached minion pillars for: %s", missed_minions)
            if self.pillar_fallback:
                lret = {
                    minion_id: self._get_live_minion_pillar(
                        minion_id, grains.get(minion_id, {})
                    )
                    for minion_id in missed_minions
                }
            ret = dict(
                list({minion_id: {} for minion_id in minion_ids}.items())
                + list(lret.items())
                + list(cret.items())
            )
        else:
            lret = {
                minion_id: self._get_live_minion_pillar(
                    minion_id, grains.get(minion_id, {})
                )
                for minion_id in minion_ids
            }
            missed_minions = [
                minion_id for minion_id in minion_ids if minion_id not in lret
            ]
            log.debug("Missed live minion pillars for: %s", missed_minions)
            if self.pillar_fallback:
                cret = {
                    minion_id: mcache
                    for (minion_id, mcache) in cached_pillar.items()
                    if mcache
                }
            ret = dict(
                list({minion_id: {} for minion_id in minion_ids}.items())
                + list(lret.items())
                + list(cret.items())
            )
        return ret

    def _tgt_to_list(self):
        # Return a list of minion ids that match the target and tgt_type
        minion_ids = []
        ckminions = salt.utils.minions.CkMinions(self.opts)
        _res = ckminions.check_minions(self.tgt, self.tgt_type)
        minion_ids = _res["minions"]
        if not minion_ids:
            log.debug(
                'No minions matched for tgt="%s" and tgt_type="%s"',
                self.tgt,
                self.tgt_type,
            )
            return {}
        log.debug(
            'Matching minions for tgt="%s" and tgt_type="%s": %s',
            self.tgt,
            self.tgt_type,
            minion_ids,
        )
        return minion_ids

    def get_minion_pillar(self):
        """
        Get pillar data for the targeted minions, either by fetching the
        cached minion data on the master, or by compiling the minion's
        pillar data on the master.

        For runner modules that need access minion pillar data, this
        function should be used instead of getting the pillar data by
        executing the pillar module on the minions.

        By default, this function tries hard to get the pillar data:
            - Try to get the cached minion grains and pillar if the
                master has minion_data_cache: True
            - If the pillar data for the minion is cached, use it.
            - If there is no cached grains/pillar data for a minion,
                then try to get the minion grains directly from the minion.
            - Use the minion grains to compile the pillar directly from the
                master using salt.pillar.Pillar
        """
        minion_pillars = {}
        minion_grains = {}
        minion_ids = self._tgt_to_list()
        if self.tgt and not minion_ids:
            return {}
        if any(
            arg
            for arg in [
                self.use_cached_grains,
                self.use_cached_pillar,
                self.grains_fallback,
                self.pillar_fallback,
            ]
        ):
            log.debug("Getting cached minion data")
            cached_minion_grains, cached_minion_pillars = self._get_cached_minion_data(
                *minion_ids
            )
        else:
            cached_minion_grains = {}
            cached_minion_pillars = {}
        log.debug("Getting minion grain data for: %s", minion_ids)
        minion_grains = self._get_minion_grains(
            *minion_ids, cached_grains=cached_minion_grains
        )
        log.debug("Getting minion pillar data for: %s", minion_ids)
        minion_pillars = self._get_minion_pillar(
            *minion_ids, grains=minion_grains, cached_pillar=cached_minion_pillars
        )
        return minion_pillars

    def get_minion_grains(self):
        """
        Get grains data for the targeted minions, either by fetching the
        cached minion data on the master, or by fetching the grains
        directly on the minion.

        By default, this function tries hard to get the grains data:
            - Try to get the cached minion grains if the master
                has minion_data_cache: True
            - If the grains data for the minion is cached, use it.
            - If there is no cached grains data for a minion,
                then try to get the minion grains directly from the minion.
        """
        minion_grains = {}
        minion_ids = self._tgt_to_list()
        if not minion_ids:
            return {}
        if any(arg for arg in [self.use_cached_grains, self.grains_fallback]):
            log.debug("Getting cached minion data.")
            cached_minion_grains, cached_minion_pillars = self._get_cached_minion_data(
                *minion_ids
            )
        else:
            cached_minion_grains = {}
        log.debug("Getting minion grain data for: %s", minion_ids)
        minion_grains = self._get_minion_grains(
            *minion_ids, cached_grains=cached_minion_grains
        )
        return minion_grains

    def get_cached_mine_data(self):
        """
        Get cached mine data for the targeted minions.
        """
        mine_data = {}
        minion_ids = self._tgt_to_list()
        log.debug("Getting cached mine data for: %s", minion_ids)
        mine_data = self._get_cached_mine_data(*minion_ids)
        return mine_data

    def clear_cached_minion_data(
        self,
        clear_pillar=False,
        clear_grains=False,
        clear_mine=False,
        clear_mine_func=None,
    ):
        """
        Clear the cached data/files for the targeted minions.
        """
        clear_what = []
        if clear_pillar:
            clear_what.append("pillar")
        if clear_grains:
            clear_what.append("grains")
        if clear_mine:
            clear_what.append("mine")
        if clear_mine_func is not None:
            clear_what.append(f"mine_func: '{clear_mine_func}'")
        if not clear_what:
            log.debug("No cached data types specified for clearing.")
            return False

        minion_ids = self._tgt_to_list()
        log.debug("Clearing cached %s data for: %s", ", ".join(clear_what), minion_ids)
        if clear_pillar == clear_grains:
            # clear_pillar and clear_grains are both True or both False.
            # This means we don't deal with pillar/grains caches at all.
            grains = {}
            pillars = {}
        else:
            # Unless both clear_pillar and clear_grains are True, we need
            # to read in the pillar/grains data since they are both stored
            # in the same file, 'data.p'
            grains, pillars = self._get_cached_minion_data(*minion_ids)
        try:
            c_minions = self.cache.list("minions")
            for minion_id in minion_ids:
                if not salt.utils.verify.valid_id(self.opts, minion_id):
                    continue

                if minion_id not in c_minions:
                    # Cache bank for this minion does not exist. Nothing to do.
                    continue
                bank = f"minions/{minion_id}"
                minion_pillar = pillars.pop(minion_id, False)
                minion_grains = grains.pop(minion_id, False)
                if (
                    (clear_pillar and clear_grains)
                    or (clear_pillar and not minion_grains)
                    or (clear_grains and not minion_pillar)
                ):
                    # Not saving pillar or grains, so just delete the cache file
                    self.cache.flush(bank, "data")
                elif clear_pillar and minion_grains:
                    self.cache.store(bank, "data", {"grains": minion_grains})
                elif clear_grains and minion_pillar:
                    self.cache.store(bank, "data", {"pillar": minion_pillar})
                if clear_mine:
                    # Delete the whole mine file
                    self.cache.flush(bank, "mine")
                elif clear_mine_func is not None:
                    # Delete a specific function from the mine file
                    mine_data = self.cache.fetch(bank, "mine")
                    if isinstance(mine_data, dict):
                        if mine_data.pop(clear_mine_func, False):
                            self.cache.store(bank, "mine", mine_data)
        except OSError:
            return True
        return True


class CacheTimer(Thread):
    """
    A basic timer class the fires timer-events every second.
    This is used for cleanup by the ConnectedCache()
    """

    def __init__(self, opts, event):
        Thread.__init__(self)
        self.opts = opts
        self.stopped = event
        self.daemon = True
        self.timer_sock = os.path.join(self.opts["sock_dir"], "con_timer.ipc")

    def run(self):
        """
        main loop that fires the event every second
        """
        context = zmq.Context()
        # the socket for outgoing timer events
        socket = context.socket(zmq.PUB)
        socket.setsockopt(zmq.LINGER, 100)
        socket.bind("ipc://" + self.timer_sock)

        count = 0
        log.debug("ConCache-Timer started")
        while not self.stopped.wait(1):
            socket.send(salt.payload.dumps(count))  # pylint: disable=missing-kwoa

            count += 1
            if count >= 60:
                count = 0


class CacheWorker(Process):
    """
    Worker for ConnectedCache which runs in its
    own process to prevent blocking of ConnectedCache
    main-loop when refreshing minion-list
    """

    def __init__(self, opts, **kwargs):
        """
        Sets up the zmq-connection to the ConCache
        """
        super().__init__(**kwargs)
        self.opts = opts

    def run(self):
        """
        Gather currently connected minions and update the cache
        """
        new_mins = list(salt.utils.minions.CkMinions(self.opts).connected_ids())
        cc = cache_cli(self.opts)
        cc.get_cached()
        cc.put_cache([new_mins])
        log.debug("ConCache CacheWorker update finished")


class ConnectedCache(Process):
    """
    Provides access to all minions ids that the master has
    successfully authenticated. The cache is cleaned up regularly by
    comparing it to the IPs that have open connections to
    the master publisher port.
    """

    def __init__(self, opts, **kwargs):
        """
        starts the timer and inits the cache itself
        """
        super().__init__(**kwargs)
        log.debug("ConCache initializing...")

        # the possible settings for the cache
        self.opts = opts

        # the actual cached minion ids
        self.minions = []

        self.cache_sock = os.path.join(self.opts["sock_dir"], "con_cache.ipc")
        self.update_sock = os.path.join(self.opts["sock_dir"], "con_upd.ipc")
        self.upd_t_sock = os.path.join(self.opts["sock_dir"], "con_timer.ipc")
        self.cleanup()

        # the timer provides 1-second intervals to the loop in run()
        # to make the cache system most responsive, we do not use a loop-
        # delay which makes it hard to get 1-second intervals without a timer
        self.timer_stop = Event()
        self.timer = CacheTimer(self.opts, self.timer_stop)
        self.timer.start()
        self.running = True

    def signal_handler(self, sig, frame):
        """
        handle signals and shutdown
        """
        self.stop()

    def cleanup(self):
        """
        remove sockets on shutdown
        """
        log.debug("ConCache cleaning up")
        if os.path.exists(self.cache_sock):
            os.remove(self.cache_sock)
        if os.path.exists(self.update_sock):
            os.remove(self.update_sock)
        if os.path.exists(self.upd_t_sock):
            os.remove(self.upd_t_sock)

    def secure(self):
        """
        secure the sockets for root-only access
        """
        log.debug("ConCache securing sockets")
        if os.path.exists(self.cache_sock):
            os.chmod(self.cache_sock, 0o600)
        if os.path.exists(self.update_sock):
            os.chmod(self.update_sock, 0o600)
        if os.path.exists(self.upd_t_sock):
            os.chmod(self.upd_t_sock, 0o600)

    def stop(self):
        """
        shutdown cache process
        """
        # avoid getting called twice
        self.cleanup()
        if self.running:
            self.running = False
            self.timer_stop.set()
            self.timer.join()

    def run(self):
        """
        Main loop of the ConCache, starts updates in intervals and
        answers requests from the MWorkers
        """
        context = zmq.Context()
        # the socket for incoming cache requests
        creq_in = context.socket(zmq.REP)
        creq_in.setsockopt(zmq.LINGER, 100)
        creq_in.bind("ipc://" + self.cache_sock)

        # the socket for incoming cache-updates from workers
        cupd_in = context.socket(zmq.SUB)
        cupd_in.setsockopt(zmq.SUBSCRIBE, b"")
        cupd_in.setsockopt(zmq.LINGER, 100)
        cupd_in.bind("ipc://" + self.update_sock)

        # the socket for the timer-event
        timer_in = context.socket(zmq.SUB)
        timer_in.setsockopt(zmq.SUBSCRIBE, b"")
        timer_in.setsockopt(zmq.LINGER, 100)
        timer_in.connect("ipc://" + self.upd_t_sock)

        poller = zmq.Poller()
        poller.register(creq_in, zmq.POLLIN)
        poller.register(cupd_in, zmq.POLLIN)
        poller.register(timer_in, zmq.POLLIN)

        # register a signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        # secure the sockets from the world
        self.secure()

        log.info("ConCache started")

        while self.running:

            # we check for new events with the poller
            try:
                socks = dict(poller.poll(1))
            except KeyboardInterrupt:
                self.stop()
            except zmq.ZMQError as zmq_err:
                log.error("ConCache ZeroMQ-Error occurred")
                log.exception(zmq_err)
                self.stop()

            # check for next cache-request
            if socks.get(creq_in) == zmq.POLLIN:
                msg = salt.payload.loads(creq_in.recv())
                log.debug("ConCache Received request: %s", msg)

                # requests to the minion list are send as str's
                if isinstance(msg, str):
                    if msg == "minions":
                        # Send reply back to client
                        reply = salt.payload.dumps(self.minions)
                        creq_in.send(reply)  # pylint: disable=missing-kwoa

            # check for next cache-update from workers
            if socks.get(cupd_in) == zmq.POLLIN:
                new_c_data = salt.payload.loads(cupd_in.recv())
                # tell the worker to exit
                # cupd_in.send(serial.dumps('ACK'))

                # check if the returned data is usable
                if not isinstance(new_c_data, list):
                    log.error("ConCache Worker returned unusable result")
                    del new_c_data
                    continue

                # the cache will receive lists of minions
                # 1. if the list only has 1 item, its from an MWorker, we append it
                # 2. if the list contains another list, its from a CacheWorker and
                #    the currently cached minions are replaced with that list
                # 3. anything else is considered malformed

                try:

                    if not new_c_data:
                        log.debug("ConCache Got empty update from worker")
                        continue

                    data = new_c_data[0]

                    if isinstance(data, str):
                        if data not in self.minions:
                            log.debug(
                                "ConCache Adding minion %s to cache", new_c_data[0]
                            )
                            self.minions.append(data)

                    elif isinstance(data, list):
                        log.debug("ConCache Replacing minion list from worker")
                        self.minions = data

                except IndexError:
                    log.debug("ConCache Got malformed result dict from worker")
                    del new_c_data

                log.info("ConCache %s entries in cache", len(self.minions))

            # check for next timer-event to start new jobs
            if socks.get(timer_in) == zmq.POLLIN:
                sec_event = salt.payload.loads(timer_in.recv())

                # update the list every 30 seconds
                if int(sec_event % 30) == 0:
                    cw = CacheWorker(self.opts)
                    cw.start()

        self.stop()
        creq_in.close()
        cupd_in.close()
        timer_in.close()
        context.term()
        log.debug("ConCache Shutting down")


def ping_all_connected_minions(opts):
    """
    Ping all connected minions.
    """
    if opts["minion_data_cache"]:
        tgt = list(salt.utils.minions.CkMinions(opts).connected_ids())
        form = "list"
    else:
        tgt = "*"
        form = "glob"
    with salt.client.LocalClient() as client:
        client.cmd_async(tgt, "test.ping", tgt_type=form)


def get_master_key(key_user, opts, skip_perm_errors=False):
    """
    Return the master key.
    """
    if key_user == "root":
        if opts.get("user", "root") != "root":
            key_user = opts.get("user", "root")
    if key_user.startswith("sudo_"):
        key_user = opts.get("user", "root")
    if salt.utils.platform.is_windows():
        # The username may contain '\' if it is in Windows
        # 'DOMAIN\username' format. Fix this for the keyfile path.
        key_user = key_user.replace("\\", "_")
    keyfile = os.path.join(opts["cachedir"], f".{key_user}_key")
    # Make sure all key parent directories are accessible
    salt.utils.verify.check_path_traversal(opts["cachedir"], key_user, skip_perm_errors)

    try:
        with salt.utils.files.fopen(keyfile, "r") as key:
            return key.read()
    except OSError:
        # Fall back to eauth
        return ""


def get_values_of_matching_keys(pattern_dict, user_name):
    """
    Check a whitelist and/or blacklist to see if the value matches it.
    """
    ret = []
    for expr in pattern_dict:
        if salt.utils.stringutils.expr_match(user_name, expr):
            ret.extend(pattern_dict[expr])
    return ret


# test code for the ConCache class
if __name__ == "__main__":

    opts = salt.config.master_config("/etc/salt/master")

    conc = ConnectedCache(opts)
    conc.start()
