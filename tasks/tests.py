# -*- coding: utf-8 -*-
"""
    tasks.tests
    ~~~~~~~~~~~

    Mark slow tests based on Jenkins test reports
"""

import os
import pathlib
import sys

from invoke import task  # pylint: disable=3rd-party-module-not-gated
from tasks import utils

try:
    import jenkins
except ImportError:
    utils.error("pip install python-jenkins")
    utils.exit_invoke(1)

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
SALT_CODE_DIR = CODE_DIR / "salt"
TESTS_CODE_DIR = CODE_DIR / "tests"


@task
def mark_slow(ctx, pr_number=None, branch="master", username=None, password=None):
    slowest_test_times = {}

    if username is None:
        username = os.environ.get("JENKINS_USERNAME")

    if password is None:
        password = os.environ.get("JENKINS_PASSWORD")

    client = jenkins.Jenkins(
        "https://jenkinsci.saltstack.com/", username=username, password=password
    )

    if pr_number:
        job_name_search = "PR-{}".format(pr_number)
    else:
        job_name_search = branch

    stop_processing = False
    jobs = []
    for job in client.get_jobs():
        if "jobs" not in job:
            continue
        if job["name"] in ("pr-docs", "pr-lint", "pr-pre-commit"):
            continue
        for njob in job["jobs"]:
            if njob["name"] != job_name_search:
                continue
            job_name = "{}/{}".format(job["name"], njob["name"])
            jobs.append(job_name)

    if not jobs:
        utils.error("No jobs were found")
        utils.exit_invoke(1)

    for job_name in jobs:
        if stop_processing:
            break
        try:
            job_info = client.get_job_info(job_name)
        except jenkins.JenkinsException as exc:
            utils.error("Failed to get job information for {}: {}", job_name, exc)
            continue
        for build in job_info["builds"]:
            test_count = 0
            build_number = build["number"]
            utils.info("Processing {} build {}", job_name, build_number)
            report = client.get_build_test_report(job_name, build_number)
            if report is None:
                continue
            for suite in report["suites"]:
                for case in suite["cases"]:
                    test_count += 1
                    if case["status"] not in (
                        "SKIPPED",
                        "FAILED",
                        "FIXED",
                        "PASSED",
                        "REGRESSION",
                    ):
                        utils.warn(
                            "Found status {} for {} build {}",
                            case["status"],
                            job_name,
                            build_number,
                        )
                    if case["status"] in ("SKIPPED",):
                        continue
                    testname = case["className"].replace("tests.", "")
                    # Remove pytest parametrize stuff from the test name
                    testname += "." + case["name"].rsplit("[", 1)[0]
                    if testname == "pytest.internal":
                        # A pytest internal error, carry on
                        continue
                    # utils.info(
                    #    "Found {} with {} seconds duration", testname, case["duration"]
                    # )
                    slowest_test_times[testname] = max(
                        slowest_test_times.get(testname, 0), case["duration"]
                    )
            utils.info(
                "Processed {} build {}. Found {} tests.",
                job_name,
                build_number,
                test_count,
            )
        # if job_name.startswith("pr-centos"):
        #    stop_processing = True

    utils.info("Found {} tests", len(slowest_test_times))

    # Clean up previous slow markers
    for path in TESTS_CODE_DIR.rglob("test_*.py"):
        lines = path.read_text().splitlines()
        found_pytest_import = False
        for idx, line in enumerate(lines[:]):
            if line.strip().startswith("@pytest.mark.slow_test"):
                lines[idx] = "[DELETE]"
            elif line.strip().startswith("# @pytest.mark.slow_test"):
                lines[idx] = "[DELETE]"
            elif line.strip().startswith("import pytest"):
                found_pytest_import = True
        contents = "\n".join(l for l in lines if l != "[DELETE]") + "\n"
        if "pytest." not in contents and found_pytest_import:
            contents = contents.replace("import pytest", "")
        path.write_text(contents)

    # Mark slow tests
    skip_whole_classes = {}
    skip_whole_classes_inheritance = {}
    for name, time in slowest_test_times.items():
        time = slowest_test_times[name]

        if time < 0.1:  # or time > 240:
            continue

        times = (
            # (0, 0.01),
            (0.01, 0.1),
            (0.1, 0.5),
            (0.5, 1),
            (1, 5),
            (5, 10),
            (10, 30),
            (30, 60),
            (60, 120),
            (120, 240),
            (240, 480),
            (480, sys.maxsize),
        )
        for lower, higher in times:
            if higher == sys.maxsize:
                marker = "{{}}@pytest.mark.slow_test(seconds={0})  # Test takes >= {0} seconds".format(
                    lower
                )
                break
            if time > lower and time <= higher:
                marker = "{{}}@pytest.mark.slow_test(seconds={0})  # Test takes >{1} and <={0} seconds".format(
                    higher, lower
                )
                time = higher
                break

        found_pytest_import = found_class = False
        futures_import_idx = None

        name_parts = name.split(".")
        fpath = TESTS_CODE_DIR / name_parts.pop(0)
        while True:
            fpath = fpath / name_parts.pop(0)
            if fpath.with_suffix(".py").is_file():
                fpath = fpath.with_suffix(".py")
                break
            if not name_parts:
                break
        if not fpath.exists():
            utils.error(
                "File {} does not exist while processing {}",
                fpath.relative_to(CODE_DIR),
                name,
            )
            continue

        if len(name_parts) == 2:
            klass = name_parts.pop(0)
            test_name = name_parts.pop(0)
        else:
            found_class = True
            klass = None
            test_name = name_parts.pop(0)

        try:
            assert not name_parts
        except AssertionError:
            utils.error(
                "could not process {}. File {} // class: {} // test name {} // name parts: {}",
                name,
                fpath,
                klass,
                test_name,
                name_parts,
            )
            continue

        # Exclude some paths from being marked slow
        exclude_paths = (TESTS_CODE_DIR / "unit" / "test_module_names.py",)
        exclude_paths = tuple(str(p) for p in exclude_paths)
        skip_whole_class_paths = (
            TESTS_CODE_DIR / "integration" / "pillar" / "test_git_pillar.py",
            TESTS_CODE_DIR / "integration" / "states" / "test_docker_network.py",
            TESTS_CODE_DIR / "unit" / "utils" / "test_pyobjects.py",
        )
        skip_whole_class_paths = tuple(str(p) for p in skip_whole_class_paths)

        excluded_path = str(fpath).startswith(exclude_paths)
        skip_whole_class = str(fpath).startswith(skip_whole_class_paths)

        test_func_def = "def {}(".format(test_name)
        test_class_def = "class {}(".format(klass)
        test_class_def_no_inheritance = "class {}:".format(klass)
        try:
            lines = fpath.read_text().splitlines()
            for idx, line in enumerate(lines[:]):
                if line.strip().startswith("from __future__"):
                    futures_import_idx = idx
                if line.strip().startswith("import pytest"):
                    found_pytest_import = True
                if found_class is False and line.strip().startswith(
                    (test_class_def, test_class_def_no_inheritance)
                ):
                    found_class = True
                    if skip_whole_class:
                        search_class_def = None
                        for class_def in (
                            test_class_def,
                            test_class_def_no_inheritance,
                        ):
                            if line.strip().startswith(class_def):
                                search_class_def = class_def
                        if not search_class_def:
                            utils.error("Failed to find a suited class def")
                        key = (fpath, search_class_def)
                        skip_whole_classes[key] = max(
                            skip_whole_classes.get(key, 0), time
                        )
                        break
                if not found_class:
                    continue
                if line.strip().startswith(test_func_def):
                    indent, _ = line.split(test_func_def)
                    if excluded_path:
                        formatted_marker = (
                            "{}@pytest.mark.slow_test(seconds=0.0001)  "
                            "# Force test to be part of the slow tests".format(indent)
                        )
                    else:
                        formatted_marker = marker.format(indent)
                    lines.insert(idx, formatted_marker)
                    if not found_pytest_import and futures_import_idx:
                        lines.insert(futures_import_idx + 1, "import pytest")
                    break
            else:
                lines = fpath.read_text().splitlines()
                for line in lines:
                    if line.strip().startswith(
                        (test_class_def, test_class_def_no_inheritance)
                    ):
                        search_class_def = None
                        for class_def in (
                            test_class_def,
                            test_class_def_no_inheritance,
                        ):
                            if line.strip().startswith(class_def):
                                search_class_def = class_def
                        if not search_class_def:
                            utils.error("Failed to find a suited class def")
                        key = (fpath, search_class_def)
                        skip_whole_classes_inheritance[key] = max(
                            skip_whole_classes_inheritance.get(key, 0), time
                        )
                        break
                # utils.warn("Did not find {} in {}", name, fpath)
                continue
            contents = "\n".join(l for l in lines) + "\n"
            fpath.write_text(contents)
        except FileNotFoundError:
            utils.error("{} not found at {}", name, fpath)

    for (fpath, test_class_def), time in skip_whole_classes.items():
        skip_whole_class_marker = (
            "{}@pytest.mark.slow_test(seconds={})  # The whole test class needs to run."
        )
        found_pytest_import = False
        futures_import_idx = None
        try:
            lines = fpath.read_text().splitlines()
            for idx, line in enumerate(lines[:]):
                if line.strip().startswith("from __future__"):
                    futures_import_idx = idx
                if line.strip().startswith("import pytest"):
                    found_pytest_import = True
                if line.strip().startswith(test_class_def):
                    indent, _ = line.split(test_class_def)
                    formatted_marker = skip_whole_class_marker.format(indent, time)
                    lines.insert(idx, formatted_marker)
                    if not found_pytest_import and futures_import_idx:
                        lines.insert(futures_import_idx + 1, "import pytest")
                    break
            else:
                utils.warn("Did not find {} in {}", test_class_def, fpath)
                continue
            contents = "\n".join(l for l in lines) + "\n"
            fpath.write_text(contents)
        except FileNotFoundError:
            utils.error("{} not found at {}", name, fpath)

    for (fpath, test_class_def), time in skip_whole_classes_inheritance.items():
        skip_whole_class_marker = "{}@pytest.mark.slow_test(seconds={})  # Inheritance used. Skip the whole class"
        found_pytest_import = False
        futures_import_idx = None
        try:
            lines = fpath.read_text().splitlines()
            for idx, line in enumerate(lines[:]):
                if line.strip().startswith("from __future__"):
                    futures_import_idx = idx
                if line.strip().startswith("import pytest"):
                    found_pytest_import = True
                if line.strip().startswith(test_class_def):
                    indent, _ = line.split(test_class_def)
                    formatted_marker = skip_whole_class_marker.format(indent, time)
                    lines.insert(idx, formatted_marker)
                    if not found_pytest_import and futures_import_idx:
                        lines.insert(futures_import_idx + 1, "import pytest")
                    break
            else:
                utils.warn("Did not find {} in {}", test_class_def, fpath)
                continue
            contents = "\n".join(l for l in lines) + "\n"
            fpath.write_text(contents)
        except FileNotFoundError:
            utils.error("{} not found at {}", name, fpath)
