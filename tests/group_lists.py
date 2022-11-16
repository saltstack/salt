from os import walk
from os.path import join
from pprint import pprint

import salt


def find_groups(keys=None):
    if keys is None:
        keys = ["slow_test", "core_test"]
    out = {k: set() for k in keys}
    for root, _, files in walk("."):
        for file in files:
            if not file.endswith(".py") or (root == "." and file == __file__):
                continue

            key_copy = keys.copy()
            full_name = join(root, file)
            with salt.utils.files.fopen(full_name) as f:
                for line in f:
                    if not key_copy:
                        break
                    for at in range(len(key_copy) - 1, -1, -1):
                        key = key_copy[at]
                        if key in line:
                            out[key].add(full_name)
                            del key_copy[-1]
    return out


def main(keys=None):
    pprint(find_groups(keys))


if __name__ == "__main__":
    main()
