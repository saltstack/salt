"""
Some utils functions to be used throughout the integration test files.
"""


def decode_byte_list(byte_list):
    """
    Helper function that takes a list of byte strings and decodes each item
    according to the __salt_system_encoding__ value. Returns a list of strings.
    """
    decoded_items = []
    for item in byte_list:
        decoded_items.append(item.decode(__salt_system_encoding__))

    return decoded_items
