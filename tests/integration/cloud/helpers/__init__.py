import random
import string


def random_name(size=6):
    """
    Generates a random cloud instance name
    """
    return "CLOUD-TEST-" + "".join(
        random.choice(string.ascii_uppercase + string.digits) for x in range(size)
    )
