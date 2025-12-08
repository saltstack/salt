#!/usr/bin/env python3
"""
Cross-platform replacement for GitHub Actions hashFiles() function.

This script computes a hash of files matching the given glob patterns,
compatible with Linux, macOS, and Windows runners.

Usage:
    python hash-files.py 'pattern1' 'pattern2' ...

Example:
    python hash-files.py 'requirements/**/*.txt' 'noxfile.py'
"""
import hashlib
import sys
from pathlib import Path


def find_files(patterns):
    """
    Find all files matching the given glob patterns.

    Args:
        patterns: List of glob patterns (e.g., 'requirements/**/*.txt')

    Returns:
        Sorted list of Path objects for matching files
    """
    files = set()
    repo_root = Path.cwd()

    for pattern in patterns:
        # Handle both absolute and relative patterns
        pattern = pattern.strip()
        if not pattern:
            continue

        # Check if pattern is absolute
        pattern_path = Path(pattern)
        if pattern_path.is_absolute():
            # For absolute paths, extract the pattern relative to repo root
            # e.g., /home/runner/work/salt/salt/.relenv/**/*.xz -> .relenv/**/*.xz
            try:
                # Try to make it relative to repo root
                relative_pattern = pattern_path.relative_to(repo_root)
                pattern = str(relative_pattern)
            except ValueError:
                # Pattern is outside repo root, use as-is
                # Try to glob from root
                if "**" in pattern or "*" in pattern or "?" in pattern:
                    # It's a glob pattern with absolute base
                    # Extract the base directory and the glob part
                    parts = pattern.split("/")
                    # Find the first part with a glob character
                    for i, part in enumerate(parts):
                        if "*" in part or "?" in part:
                            base = Path("/".join(parts[:i]))
                            glob_pattern = "/".join(parts[i:])
                            matching_paths = base.glob(glob_pattern)
                            for path in matching_paths:
                                if path.is_file():
                                    files.add(path)
                            break
                    continue
                else:
                    # It's an absolute path to a single file
                    if pattern_path.is_file():
                        files.add(pattern_path)
                    continue

        # Use glob for patterns
        matching_paths = repo_root.glob(pattern)

        # Add only files (not directories)
        for path in matching_paths:
            if path.is_file():
                files.add(path)

    # Sort for consistent ordering across platforms
    return sorted(files)


def hash_files(file_paths):
    """
    Compute SHA256 hash of the contents of all files.

    Args:
        file_paths: List of Path objects to hash

    Returns:
        Hexadecimal hash string
    """
    hasher = hashlib.sha256()

    for file_path in file_paths:
        try:
            # Add the relative path to the hash for consistency
            # Try to make it relative to cwd, otherwise use the full path
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                # File is outside cwd, use absolute path
                rel_path = file_path
            hasher.update(str(rel_path).encode("utf-8"))

            # Read and hash file contents in binary mode
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files efficiently
                while chunk := f.read(8192):
                    hasher.update(chunk)
        except (OSError, IOError) as e:
            # Print warning but continue with other files
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            continue

    return hasher.hexdigest()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python hash-files.py 'pattern1' 'pattern2' ...", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Example: python hash-files.py 'requirements/**/*.txt' 'noxfile.py'",
            file=sys.stderr,
        )
        sys.exit(1)

    patterns = sys.argv[1:]

    # Find all matching files
    files = find_files(patterns)

    if not files:
        # Return empty hash if no files found (mimics hashFiles behavior)
        print("")
        return

    # Compute and print hash
    file_hash = hash_files(files)
    print(file_hash)


if __name__ == "__main__":
    main()
