import argparse
import os

print("Update winrepo script")

# Where are we
print(f"Current working directory: {os.getcwd()}")

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("-f", "--file", help="the winrepo file to edit")
arg_parser.add_argument("-v", "--version", help="The version to add")

args = arg_parser.parse_args()
file = args.file
version = args.version

print("Args:")
print(f"- file: {file}")
print(f"- version: {version}")

if version.startswith("v"):
    version = version[1:]

with open(file) as f:
    print(f"Opening file: {file}")
    current_contents = f.readlines()

new_contents = []

added = False
for line in current_contents:
    new_contents.append(line)
    if "load_yaml as versions_relenv" in line and not added:
        print(f"Adding version: {version}")
        new_contents.append(f"- {version}\n")
        added = True

with open(file, "w") as f:
    print(f"Writing file: {file}")
    f.writelines(new_contents)

print("Update winrepo script complete")
