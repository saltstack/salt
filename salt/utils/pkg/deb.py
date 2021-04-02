"""
Common functions for working with deb packages
"""


def combine_comments(comments):
    """
    Given a list of comments, or a comment submitted as a string, return a
    single line of text containing all of the comments.
    """
    if isinstance(comments, list):
        for idx in range(len(comments)):  # pylint: disable=C0200
            if not isinstance(comments[idx], str):
                comments[idx] = str(comments[idx])
    else:
        if not isinstance(comments, str):
            comments = [str(comments)]
        else:
            comments = [comments]
    return " ".join(comments).strip()


def strip_uri(repo):
    """
    Remove the trailing slash from the URI in a repo definition
    """
    splits = repo.split()
    for idx in range(len(splits)):  # pylint: disable=C0200
        if any(splits[idx].startswith(x) for x in ("http://", "https://", "ftp://")):
            splits[idx] = splits[idx].rstrip("/")
    return " ".join(splits)
