import argparse
import os

# Where are we
print(os.getcwd())

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("-f", "--file", help="the winrepo file to edit")
arg_parser.add_argument("-v", "--version", help="The version to add")

args = arg_parser.parse_args()
file = args.file
version = args.version

if version.startswith("v"):
    version = version[1:]

with open(file) as f:
    current_contents = f.readlines()

new_contents = []

added = False
for line in current_contents:
    new_contents.append(line)
    if "for version in [" in line and not added:
        new_contents.append(f"          '{version}',\n")
        added = True

with open(file, "w") as f:
    f.writelines(new_contents)
