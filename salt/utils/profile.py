"""
Decorator and functions to profile Salt using cProfile
"""

import datetime
import logging
import os
import pstats
import subprocess

import salt.utils.files
import salt.utils.hashutils
import salt.utils.path
import salt.utils.stringutils

log = logging.getLogger(__name__)

try:
    import cProfile

    HAS_CPROFILE = True
except ImportError:
    HAS_CPROFILE = False


def profile_func(filename=None):
    """
    Decorator for adding profiling to a nested function in Salt
    """

    def proffunc(fun):
        def profiled_func(*args, **kwargs):
            logging.info("Profiling function %s", fun.__name__)
            try:
                profiler = cProfile.Profile()
                retval = profiler.runcall(fun, *args, **kwargs)
                profiler.dump_stats(filename or f"{fun.__name__}_func.profile")
            except OSError:
                logging.exception("Could not open profile file %s", filename)

            return retval

        return profiled_func

    return proffunc


def activate_profile(test=True):
    pr = None
    if test:
        if HAS_CPROFILE:
            pr = cProfile.Profile()
            pr.enable()
        else:
            log.error("cProfile is not available on your platform")
    return pr


def output_profile(pr, stats_path="/tmp/stats", stop=False, id_=None):
    if pr is not None and HAS_CPROFILE:
        try:
            pr.disable()
            if not os.path.isdir(stats_path):
                os.makedirs(stats_path)
            date = datetime.datetime.now().isoformat()
            if id_ is None:
                id_ = salt.utils.hashutils.random_hash(size=32)
            ficp = os.path.join(stats_path, f"{id_}.{date}.pstats")
            fico = os.path.join(stats_path, f"{id_}.{date}.dot")
            ficn = os.path.join(stats_path, f"{id_}.{date}.stats")
            if not os.path.exists(ficp):
                pr.dump_stats(ficp)
                with salt.utils.files.fopen(ficn, "w") as fic:
                    pstats.Stats(pr, stream=fic).sort_stats("cumulative")
            log.info("PROFILING: %s generated", ficp)
            log.info("PROFILING (cumulative): %s generated", ficn)
            pyprof = salt.utils.path.which("pyprof2calltree")
            cmd = [pyprof, "-i", ficp, "-o", fico]
            if pyprof:
                failed = False
                try:
                    pro = subprocess.Popen(
                        cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                except OSError:
                    failed = True
                if pro.returncode:
                    failed = True
                if failed:
                    log.error("PROFILING (dot problem")
                else:
                    log.info("PROFILING (dot): %s generated", fico)
                log.trace("pyprof2calltree output:")
                log.trace(
                    salt.utils.stringutils.to_str(pro.stdout.read()).strip()
                    + salt.utils.stringutils.to_str(pro.stderr.read()).strip()
                )
            else:
                log.info("You can run %s for additional stats.", cmd)
        finally:
            if not stop:
                pr.enable()
    return pr
