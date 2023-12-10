"""
The 'sysbench' module is used to analyze the
performance of the minions, right from the master!
It measures various system parameters such as
CPU, Memory, File I/O, Threads and Mutex.
"""

import re

import salt.utils.path


def __virtual__():
    """
    loads the module, if only sysbench is installed
    """
    # finding the path of the binary
    if salt.utils.path.which("sysbench"):
        return "sysbench"
    return (
        False,
        "The sysbench execution module failed to load: the sysbench binary is not in"
        " the path.",
    )


def _parser(result):
    """
    parses the output into a dictionary
    """

    # regexes to match
    _total_time = re.compile(r"total time:\s*(\d*.\d*s)")
    _total_execution = re.compile(r"event execution:\s*(\d*.\d*s?)")
    _min_response_time = re.compile(r"min:\s*(\d*.\d*ms)")
    _max_response_time = re.compile(r"max:\s*(\d*.\d*ms)")
    _avg_response_time = re.compile(r"avg:\s*(\d*.\d*ms)")
    _per_response_time = re.compile(r"95 percentile:\s*(\d*.\d*ms)")

    # extracting data
    total_time = re.search(_total_time, result).group(1)
    total_execution = re.search(_total_execution, result).group(1)
    min_response_time = re.search(_min_response_time, result).group(1)
    max_response_time = re.search(_max_response_time, result).group(1)
    avg_response_time = re.search(_avg_response_time, result).group(1)
    per_response_time = re.search(_per_response_time, result)
    if per_response_time is not None:
        per_response_time = per_response_time.group(1)

    # returning the data as dictionary
    return {
        "total time": total_time,
        "total execution time": total_execution,
        "minimum response time": min_response_time,
        "maximum response time": max_response_time,
        "average response time": avg_response_time,
        "95 percentile": per_response_time,
    }


def cpu():
    """
    Tests for the CPU performance of minions.

    CLI Examples:

    .. code-block:: bash

        salt '*' sysbench.cpu
    """

    # Test data
    max_primes = [500, 1000, 2500, 5000]

    # Initializing the test variables
    test_command = "sysbench --test=cpu --cpu-max-prime={0} run"
    result = None
    ret_val = {}

    # Test beings!
    for primes in max_primes:
        key = "Prime numbers limit: {}".format(primes)
        run_command = test_command.format(primes)
        result = __salt__["cmd.run"](run_command)
        ret_val[key] = _parser(result)

    return ret_val


def threads():
    """
    This tests the performance of the processor's scheduler

    CLI Example:

    .. code-block:: bash

        salt '*' sysbench.threads
    """

    # Test data
    thread_yields = [100, 200, 500, 1000]
    thread_locks = [2, 4, 8, 16]

    # Initializing the test variables
    test_command = "sysbench --num-threads=64 --test=threads "
    test_command += "--thread-yields={0} --thread-locks={1} run "
    result = None
    ret_val = {}

    # Test begins!
    for yields, locks in zip(thread_yields, thread_locks):
        key = "Yields: {} Locks: {}".format(yields, locks)
        run_command = test_command.format(yields, locks)
        result = __salt__["cmd.run"](run_command)
        ret_val[key] = _parser(result)

    return ret_val


def mutex():
    """
    Tests the implementation of mutex

    CLI Examples:

    .. code-block:: bash

        salt '*' sysbench.mutex
    """

    # Test options and the values they take
    # --mutex-num = [50,500,1000]
    # --mutex-locks = [10000,25000,50000]
    # --mutex-loops = [2500,5000,10000]

    # Test data (Orthogonal test cases)
    mutex_num = [50, 50, 50, 500, 500, 500, 1000, 1000, 1000]
    locks = [10000, 25000, 50000, 10000, 25000, 50000, 10000, 25000, 50000]
    mutex_locks = []
    mutex_locks.extend(locks)
    mutex_loops = [2500, 5000, 10000, 10000, 2500, 5000, 5000, 10000, 2500]

    # Initializing the test variables
    test_command = "sysbench --num-threads=250 --test=mutex "
    test_command += "--mutex-num={0} --mutex-locks={1} --mutex-loops={2} run "
    result = None
    ret_val = {}

    # Test begins!
    for num, locks, loops in zip(mutex_num, mutex_locks, mutex_loops):
        key = "Mutex: {} Locks: {} Loops: {}".format(num, locks, loops)
        run_command = test_command.format(num, locks, loops)
        result = __salt__["cmd.run"](run_command)
        ret_val[key] = _parser(result)

    return ret_val


def memory():
    """
    This tests the memory for read and write operations.

    CLI Examples:

    .. code-block:: bash

        salt '*' sysbench.memory
    """

    # test defaults
    # --memory-block-size = 10M
    # --memory-total-size = 1G

    # We test memory read / write against global / local scope of memory
    # Test data
    memory_oper = ["read", "write"]
    memory_scope = ["local", "global"]

    # Initializing the test variables
    test_command = "sysbench --num-threads=64 --test=memory "
    test_command += "--memory-oper={0} --memory-scope={1} "
    test_command += "--memory-block-size=1K --memory-total-size=32G run "
    result = None
    ret_val = {}

    # Test begins!
    for oper in memory_oper:
        for scope in memory_scope:
            key = "Operation: {} Scope: {}".format(oper, scope)
            run_command = test_command.format(oper, scope)
            result = __salt__["cmd.run"](run_command)
            ret_val[key] = _parser(result)

    return ret_val


def fileio():
    """
    This tests for the file read and write operations
    Various modes of operations are

    * sequential write
    * sequential rewrite
    * sequential read
    * random read
    * random write
    * random read and write

    The test works with 32 files with each file being 1Gb in size
    The test consumes a lot of time. Be patient!

    CLI Examples:

    .. code-block:: bash

        salt '*' sysbench.fileio
    """

    # Test data
    test_modes = ["seqwr", "seqrewr", "seqrd", "rndrd", "rndwr", "rndrw"]

    # Initializing the required variables
    test_command = "sysbench --num-threads=16 --test=fileio "
    test_command += "--file-num=32 --file-total-size=1G --file-test-mode={0} "
    result = None
    ret_val = {}

    # Test begins!
    for mode in test_modes:
        key = "Mode: {}".format(mode)

        # Prepare phase
        run_command = (test_command + "prepare").format(mode)
        __salt__["cmd.run"](run_command)

        # Test phase
        run_command = (test_command + "run").format(mode)
        result = __salt__["cmd.run"](run_command)
        ret_val[key] = _parser(result)

        # Clean up phase
        run_command = (test_command + "cleanup").format(mode)
        __salt__["cmd.run"](run_command)

    return ret_val


def ping():

    return True
