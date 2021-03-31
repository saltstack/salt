def normalize_ret(ret):
    """
    Normalize the return to the format that we'll use for result checking
    """
    result = {}
    for item, descr in ret.items():
        result[item] = {
            "__run_num__": descr["__run_num__"],
            "comment": descr["comment"],
            "result": descr["result"],
            "changes": descr["changes"] != {},  # whether there where any changes
        }
    return result
