#!/usr/bin/python
#
# committer_parser.py
#
# Simple script to parse the output of 'git log' and generate some statistics.
# May leverage GitHub API in the future
#
"""
To use this commit parser script pipe git log into the stdin:

    git log | committer_parser.py -c -
"""
# pylint: disable=resource-leakage


import datetime
import email.utils
import getopt
import re
import sys


class Usage(Exception):
    def __init__(self, msg):  # pylint: disable=W0231
        self.msg = "committer_parser.py [-c | --contributor-detail] - | <logfilename>\n"
        self.msg += (
            "   : Parse commit log from git and print number of "
            "commits and unique committers\n"
        )
        self.msg += "   : by month.  Accepts a filename or reads from stdin.\n"
        self.msg += (
            "   : -c | --contributor-detail generates output by "
            "contributor, by month, in a tab-separated table\n"
        )
        if msg:
            self.msg += "\n"
            self.msg += msg


def parse_date(datestr):
    d = email.utils.parsedate(datestr)
    return datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5], d[6])


def parse_gitlog(filename=None):
    """
    Parse out the gitlog cli data
    """
    results = {}
    commits = {}
    commits_by_contributor = {}

    if not filename or filename == "-":
        fh = sys.stdin
    else:
        fh = open(filename, "r+", encoding="utf-8")

    try:
        commitcount = 0
        for line in fh.readlines():
            line = line.rstrip()
            if line.startswith("commit "):
                new_commit = True
                commitcount += 1
                continue

            if line.startswith("Author:"):
                author = re.match(r"Author:\s+(.*)\s+<(.*)>", line)
                if author:
                    email = author.group(2)
                continue

            if line.startswith("Date:"):

                isodate = re.match(r"Date:\s+(.*)", line)
                d = parse_date(isodate.group(1))
                continue

            if len(line) < 2 and new_commit:
                new_commit = False
                key = f"{d.year}-{str(d.month).zfill(2)}"

                if key not in results:
                    results[key] = []

                if key not in commits:
                    commits[key] = 0

                if email not in commits_by_contributor:
                    commits_by_contributor[email] = {}

                if key not in commits_by_contributor[email]:
                    commits_by_contributor[email][key] = 1
                else:
                    commits_by_contributor[email][key] += 1

                    if email not in results[key]:
                        results[key].append(email)

                    commits[key] += commitcount
                    commitcount = 0
    finally:
        fh.close()
    return (results, commits, commits_by_contributor)


def counts_by_contributor(commits_by_contributor, results):
    output = ""
    dates = sorted(results.keys())
    for d in dates:
        output += f"\t{d}"

    output += "\n"

    for email in sorted(commits_by_contributor.keys()):
        output += f"'{email}"
        for d in dates:
            if d in commits_by_contributor[email]:
                output += f"\t{commits_by_contributor[email][d]}"
            else:
                output += "\t"
        output += "\n"
    return output


def count_results(results, commits):
    result_str = ""
    print("Date\tContributors\tCommits")
    for k in sorted(results.keys()):
        result_str += f"{k}\t{len(results[k])}\t{commits[k]}"
        result_str += "\n"
    return result_str


def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hc", ["help", "contributor-detail"])
            if len(args) < 1:
                raise Usage(
                    "committer_parser.py needs a filename or '-' to read from stdin"
                )
        except getopt.error as msg:
            raise Usage(msg)
    except Usage as err:
        print(err.msg, file=sys.stderr)
        return 2

    if len(opts) > 0:
        if "-h" in opts[0] or "--help" in opts[0]:
            return 0

    data, counts, commits_by_contributor = parse_gitlog(filename=args[0])

    if len(opts) > 0:
        if "-c" or "--contributor-detail":
            print(counts_by_contributor(commits_by_contributor, data))
    else:
        print(count_results(data, counts))


if __name__ == "__main__":
    sys.exit(main())
