"""
Watch files and translate the changes into salt events.

.. versionadded:: 2019.2.0

:depends:   - watchdog Python module >= 0.8.3

"""

import collections
import logging

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

    class FileSystemEventHandler:
        """A dummy class to make the import work"""

        def __init__(self):
            pass


__virtualname__ = "watchdog"

log = logging.getLogger(__name__)

DEFAULT_MASK = [
    "create",
    "delete",
    "modify",
    "move",
]


class Handler(FileSystemEventHandler):
    def __init__(self, queue, masks=None):
        super().__init__()
        self.masks = masks or DEFAULT_MASK
        self.queue = queue

    def on_created(self, event):
        self._append_if_mask(event, "create")

    def on_modified(self, event):
        self._append_if_mask(event, "modify")

    def on_deleted(self, event):
        self._append_if_mask(event, "delete")

    def on_moved(self, event):
        self._append_if_mask(event, "move")

    def _append_if_mask(self, event, mask):
        logging.debug(event)

        self._append_path_if_mask(event, mask)

    def _append_path_if_mask(self, event, mask):
        if mask in self.masks:
            self.queue.append(event)


def __virtual__():
    if HAS_WATCHDOG:
        return __virtualname__
    return False


def _get_queue(config):
    """
    Check the context for the notifier and construct it if not present
    """

    if "watchdog.observer" not in __context__:
        queue = collections.deque()
        observer = Observer()
        for path in config.get("directories", {}):
            path_params = config.get("directories").get(path)
            masks = path_params.get("mask", DEFAULT_MASK)
            event_handler = Handler(queue, masks)
            observer.schedule(event_handler, path)

        observer.start()

        __context__["watchdog.observer"] = observer
        __context__["watchdog.queue"] = queue

    return __context__["watchdog.queue"]


class ValidationError(Exception):
    pass


def validate(config):
    """
    Validate the beacon configuration
    """

    try:
        _validate(config)
        return True, "Valid beacon configuration"
    except ValidationError as error:
        return False, str(error)


def _validate(config):
    if not isinstance(config, list):
        raise ValidationError("Configuration for watchdog beacon must be a list.")

    _config = {}
    for part in config:
        _config.update(part)

    if "directories" not in _config:
        raise ValidationError(
            "Configuration for watchdog beacon must include directories."
        )

    if not isinstance(_config["directories"], dict):
        raise ValidationError(
            "Configuration for watchdog beacon directories must be a dictionary."
        )

    for path in _config["directories"]:
        _validate_path(_config["directories"][path])


def _validate_path(path_config):
    if not isinstance(path_config, dict):
        raise ValidationError(
            "Configuration for watchdog beacon directory path must be a dictionary."
        )

    if "mask" in path_config:
        _validate_mask(path_config["mask"])


def _validate_mask(mask_config):
    valid_mask = [
        "create",
        "modify",
        "delete",
        "move",
    ]

    if not isinstance(mask_config, list):
        raise ValidationError("Configuration for watchdog beacon mask must be list.")

    if any(mask not in valid_mask for mask in mask_config):
        raise ValidationError("Configuration for watchdog beacon contains invalid mask")


def to_salt_event(event):
    return {
        "tag": __virtualname__,
        "path": event.src_path,
        "change": event.event_type,
    }


def beacon(config):
    """
    Watch the configured directories

    Example Config

    .. code-block:: yaml

        beacons:
          watchdog:
            - directories:
                /path/to/dir:
                  mask:
                    - create
                    - modify
                    - delete
                    - move

    The mask list can contain the following events (the default mask is create,
    modify delete, and move):
    * create  - File or directory is created in watched directory
    * modify  - The watched directory is modified
    * delete  - File or directory is deleted from watched directory
    * move    - File or directory is moved or renamed in the watched directory
    """

    _config = {}
    list(map(_config.update, config))

    queue = _get_queue(_config)

    ret = []
    while queue:
        ret.append(to_salt_event(queue.popleft()))

    return ret


def close(config):
    observer = __context__.pop("watchdog.observer", None)

    if observer:
        observer.stop()
