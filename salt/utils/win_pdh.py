r"""
Salt Util for getting system information with the Performance Data Helper (pdh).
Counter information is gathered from current activity or log files.

Usage:

.. code-block:: python

    import salt.utils.win_pdh

    # Get a list of Counter objects
    salt.utils.win_pdh.list_objects()

    # Get a list of ``Processor`` instances
    salt.utils.win_pdh.list_instances('Processor')

    # Get a list of ``Processor`` counters
    salt.utils.win_pdh.list_counters('Processor')

    # Get the value of a single counter
    # \Processor(*)\% Processor Time
    salt.utils.win_pdh.get_counter('Processor', '*', '% Processor Time')

    # Get the values of multiple counters
    counter_list = [('Processor', '*', '% Processor Time'),
                    ('System', None, 'Context Switches/sec'),
                    ('Memory', None, 'Pages/sec'),
                    ('Server Work Queues', '*', 'Queue Length')]
    salt.utils.win_pdh.get_counters(counter_list)

    # Get all counters for the Processor object
    salt.utils.win_pdh.get_all_counters('Processor')
"""

# https://docs.microsoft.com/en-us/windows/desktop/perfctrs/using-the-pdh-functions-to-consume-counter-data

# https://www.cac.cornell.edu/wiki/index.php?title=Performance_Data_Helper_in_Python_with_win32pdh
import logging
import time

import salt.utils.platform
from salt.exceptions import CommandExecutionError

try:
    import pywintypes
    import win32pdh

    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False


log = logging.getLogger(__file__)

# Define the virtual name
__virtualname__ = "pdh"


def __virtual__():
    """
    Only works on Windows systems with the PyWin32
    """
    if not salt.utils.platform.is_windows():
        return False, "salt.utils.win_pdh: Requires Windows"

    if not HAS_WINDOWS_MODULES:
        return False, "salt.utils.win_pdh: Missing required modules"

    return __virtualname__


class Counter:
    """
    Counter object
    Has enumerations and functions for working with counters
    """

    # The dwType field from GetCounterInfo returns the following, or'ed.
    # These come from WinPerf.h
    PERF_SIZE_DWORD = 0x00000000
    PERF_SIZE_LARGE = 0x00000100
    PERF_SIZE_ZERO = 0x00000200  # for Zero Length fields
    PERF_SIZE_VARIABLE_LEN = 0x00000300
    # length is in the CounterLength field of the Counter Definition structure

    # select one of the following values to indicate the counter field usage
    PERF_TYPE_NUMBER = 0x00000000  # a number (not a counter)
    PERF_TYPE_COUNTER = 0x00000400  # an increasing numeric value
    PERF_TYPE_TEXT = 0x00000800  # a text field
    PERF_TYPE_ZERO = 0x00000C00  # displays a zero

    # If the PERF_TYPE_NUMBER field was selected, then select one of the
    # following to describe the Number
    PERF_NUMBER_HEX = 0x00000000  # display as HEX value
    PERF_NUMBER_DECIMAL = 0x00010000  # display as a decimal integer
    PERF_NUMBER_DEC_1000 = 0x00020000  # display as a decimal/1000

    # If the PERF_TYPE_COUNTER value was selected then select one of the
    # following to indicate the type of counter
    PERF_COUNTER_VALUE = 0x00000000  # display counter value
    PERF_COUNTER_RATE = 0x00010000  # divide ctr / delta time
    PERF_COUNTER_FRACTION = 0x00020000  # divide ctr / base
    PERF_COUNTER_BASE = 0x00030000  # base value used in fractions
    PERF_COUNTER_ELAPSED = 0x00040000  # subtract counter from current time
    PERF_COUNTER_QUEUE_LEN = 0x00050000  # Use Queue len processing func.
    PERF_COUNTER_HISTOGRAM = 0x00060000  # Counter begins or ends a histogram

    # If the PERF_TYPE_TEXT value was selected, then select one of the
    # following to indicate the type of TEXT data.
    PERF_TEXT_UNICODE = 0x00000000  # type of text in text field
    PERF_TEXT_ASCII = 0x00010000  # ASCII using the CodePage field

    #  Timer SubTypes
    PERF_TIMER_TICK = 0x00000000  # use system perf. freq for base
    PERF_TIMER_100NS = 0x00100000  # use 100 NS timer time base units
    PERF_OBJECT_TIMER = 0x00200000  # use the object timer freq

    # Any types that have calculations performed can use one or more of the
    # following calculation modification flags listed here
    PERF_DELTA_COUNTER = 0x00400000  # compute difference first
    PERF_DELTA_BASE = 0x00800000  # compute base diff as well
    PERF_INVERSE_COUNTER = 0x01000000  # show as 1.00-value (assumes:
    PERF_MULTI_COUNTER = 0x02000000  # sum of multiple instances

    # Select one of the following values to indicate the display suffix (if any)
    PERF_DISPLAY_NO_SUFFIX = 0x00000000  # no suffix
    PERF_DISPLAY_PER_SEC = 0x10000000  # "/sec"
    PERF_DISPLAY_PERCENT = 0x20000000  # "%"
    PERF_DISPLAY_SECONDS = 0x30000000  # "secs"
    PERF_DISPLAY_NO_SHOW = 0x40000000  # value is not displayed

    def build_counter(obj, instance, instance_index, counter):
        r"""
        Makes a fully resolved counter path. Counter names are formatted like
        this:

        ``\Processor(*)\% Processor Time``

        The above breaks down like this:

            obj = 'Processor'
            instance = '*'
            counter = '% Processor Time'

        Args:

            obj (str):
                The top level object

            instance (str):
                The instance of the object

            instance_index (int):
                The index of the instance. Can usually be 0

            counter (str):
                The name of the counter

        Returns:
            Counter: A Counter object with the path if valid

        Raises:
            CommandExecutionError: If the path is invalid
        """
        path = win32pdh.MakeCounterPath(
            (None, obj, instance, None, instance_index, counter), 0
        )
        if win32pdh.ValidatePath(path) == 0:
            return Counter(path, obj, instance, instance_index, counter)
        raise CommandExecutionError(f"Invalid counter specified: {path}")

    build_counter = staticmethod(build_counter)

    def __init__(self, path, obj, instance, index, counter):
        self.path = path
        self.obj = obj
        self.instance = instance
        self.index = index
        self.counter = counter
        self.handle = None
        self.info = None
        self.type = None

    def add_to_query(self, query):
        """
        Add the current path to the query

        Args:
            query (obj):
                The handle to the query to add the counter
        """
        self.handle = win32pdh.AddCounter(query, self.path)

    def get_info(self):
        """
        Get information about the counter

        .. note::
            GetCounterInfo sometimes crashes in the wrapper code. Fewer crashes
            if this is called after sampling data.
        """
        if not self.info:
            ci = win32pdh.GetCounterInfo(self.handle, 0)
            self.info = {
                "type": ci[0],
                "version": ci[1],
                "scale": ci[2],
                "default_scale": ci[3],
                "user_data": ci[4],
                "query_user_data": ci[5],
                "full_path": ci[6],
                "machine_name": ci[7][0],
                "object_name": ci[7][1],
                "instance_name": ci[7][2],
                "parent_instance": ci[7][3],
                "instance_index": ci[7][4],
                "counter_name": ci[7][5],
                "explain_text": ci[8],
            }
        return self.info

    def value(self):
        """
        Return the counter value

        Returns:
            long: The counter value
        """
        (counter_type, value) = win32pdh.GetFormattedCounterValue(
            self.handle, win32pdh.PDH_FMT_DOUBLE
        )
        self.type = counter_type
        return value

    def type_string(self):
        """
        Returns the names of the flags that are set in the Type field

        It can be used to format the counter.
        """
        type = self.get_info()["type"]
        type_list = []
        for member in dir(self):
            if member.startswith("PERF_"):
                bit = getattr(self, member)
                if bit and bit & type:
                    type_list.append(member[5:])
        return type_list

    def __str__(self):
        return self.path


def list_objects():
    """
    Get a list of available counter objects on the system

    Returns:
        list: A list of counter objects
    """
    return sorted(win32pdh.EnumObjects(None, None, -1, 0))


def list_counters(obj):
    """
    Get a list of counters available for the object

    Args:
        obj (str):
            The name of the counter object. You can get a list of valid names
            using the ``list_objects`` function

    Returns:
        list: A list of counters available to the passed object
    """
    return win32pdh.EnumObjectItems(None, None, obj, -1, 0)[0]


def list_instances(obj):
    """
    Get a list of instances available for the object

    Args:
        obj (str):
            The name of the counter object. You can get a list of valid names
            using the ``list_objects`` function

    Returns:
        list: A list of instances available to the passed object
    """
    return win32pdh.EnumObjectItems(None, None, obj, -1, 0)[1]


def build_counter_list(counter_list):
    r"""
    Create a list of Counter objects to be used in the pdh query

    Args:
        counter_list (list):
            A list of tuples containing counter information. Each tuple should
            contain the object, instance, and counter name. For example, to
            get the ``% Processor Time`` counter for all Processors on the
            system (``\Processor(*)\% Processor Time``) you would pass a tuple
            like this:

            ```
            counter_list = [('Processor', '*', '% Processor Time')]
            ```

            If there is no ``instance`` for the counter, pass ``None``

            Multiple counters can be passed like so:

            ```
            counter_list = [('Processor', '*', '% Processor Time'),
                            ('System', None, 'Context Switches/sec')]
            ```

            .. note::
                Invalid counters are ignored

    Returns:
        list: A list of Counter objects
    """
    counters = []
    index = 0
    for obj, instance, counter_name in counter_list:
        try:
            counter = Counter.build_counter(obj, instance, index, counter_name)
            index += 1
            counters.append(counter)
        except CommandExecutionError as exc:
            # Not a valid counter
            log.debug(exc.strerror)
            continue
    return counters


def get_all_counters(obj, instance_list=None):
    """
    Get the values for all counters available to a Counter object

    Args:

        obj (str):
            The name of the counter object. You can get a list of valid names
            using the ``list_objects`` function

        instance_list (list):
            A list of instances to return. Use this to narrow down the counters
            that are returned.

            .. note::
                ``_Total`` is returned as ``*``
    """
    counters, instances_avail = win32pdh.EnumObjectItems(None, None, obj, -1, 0)

    if instance_list is None:
        instance_list = instances_avail

    if not isinstance(instance_list, list):
        instance_list = [instance_list]

    counter_list = []
    for counter in counters:
        for instance in instance_list:
            instance = "*" if instance.lower() == "_total" else instance
            counter_list.append((obj, instance, counter))
        else:  # pylint: disable=useless-else-on-loop
            counter_list.append((obj, None, counter))

    return get_counters(counter_list) if counter_list else {}


def get_counters(counter_list):
    """
    Get the values for the passes list of counters

    Args:
        counter_list (list):
            A list of counters to lookup

    Returns:
        dict: A dictionary of counters and their values
    """
    if not isinstance(counter_list, list):
        raise CommandExecutionError("counter_list must be a list of tuples")

    try:
        # Start a Query instances
        query = win32pdh.OpenQuery()

        # Build the counters
        counters = build_counter_list(counter_list)

        # Add counters to the Query
        for counter in counters:
            counter.add_to_query(query)

        # https://docs.microsoft.com/en-us/windows/desktop/perfctrs/collecting-performance-data
        win32pdh.CollectQueryData(query)
        # The sleep here is required for counters that require more than 1
        # reading
        time.sleep(1)
        win32pdh.CollectQueryData(query)
        ret = {}

        for counter in counters:
            try:
                ret.update({counter.path: counter.value()})
            except pywintypes.error as exc:
                if exc.strerror == "No data to return.":
                    # Some counters are not active and will throw an error if
                    # there is no data to return
                    continue
                else:
                    raise

    except pywintypes.error as exc:
        if exc.strerror == "No data to return.":
            # Sometimess, win32pdh.CollectQueryData can err
            # so just ignore it
            return {}
        else:
            raise

    finally:
        win32pdh.CloseQuery(query)

    return ret


def get_counter(obj, instance, counter):
    """
    Get the value of a single counter

    Args:

        obj (str):
            The name of the counter object. You can get a list of valid names
            using the ``list_objects`` function

        instance (str):
            The counter instance you wish to return. Get a list of instances
            using the ``list_instances`` function

            .. note::
                ``_Total`` is returned as ``*``

        counter (str):
            The name of the counter. Get a list of counters using the
            ``list_counters`` function
    """
    return get_counters([(obj, instance, counter)])
