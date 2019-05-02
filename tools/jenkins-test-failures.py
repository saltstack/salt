'''
Dump test failures from jenkins

This script can be used to dump all the current test failures from jenkins. The
failures are aggrigated by branch and build.

Set JENKINS_USER and JENKINS_PASS environment variables. Connect to the VPN to
enable the script to access cloud test failures.
'''
import collections
import logging
import os
import pprint

import requests
import requests.auth


log = logging.getLogger()

TestFailure = collections.namedtuple('TestFailure', 'full_name, branch, suite, case, uri')

uri = os.environ.get('JENKINS_URI', 'https://jenkinsci.saltstack.com/api/json')
user = os.environ['JENKINS_USER']
password = os.environ['JENKINS_PASS']

# TODO: Is 2019.2 a good default branch? Maybe develop? -W. Werner, 2019-05-02
current_versions = [
    branch.strip()
    for branch in os.environ.get('JENKINS_BRANCHES', '2019.2').split(',')
]


template = '''
{title} test failures
=======

{branches}
---

{details}

```
{stacktrace}
```
'''


def all_jobs(branches=current_versions):
    for branch in branches:
        uri = (
            'https://jenkinsci.saltstack.com/job/{branch}/view/All/api/json'
        ).format(branch=branch)
        log.debug("Fetching builds for branch:%s url: %s", branch, uri)
        resp = requests.get(
            uri,
            headers={'accept': 'application/json'},
            auth=requests.auth.HTTPBasicAuth(user, password),
        )
        data = resp.json()
        for job in data['jobs']:
            if job['color'] == 'red':
                yield job['url']


def builds(branch, suite, number_of_builds=1):
    uri = (
        'https://jenkinsci.saltstack.com/job/{branch}/job'
        '/{suite}/api/json'
    ).format(
        branch=branch,
        suite=suite,
    )
    resp = requests.get(
        uri,
        headers={'accept': 'application/json'},
        auth=requests.auth.HTTPBasicAuth(user, password),
    )
    log.debug('Fetching builds for branch: %s suite: %s uri: %s', branch, suite, uri)
    if resp.status_code != 200:
        log.error('Unable to fetch builds: %s %s %s %s', branch, suite, uri, resp.status_code)
        return
    done = 0
    for build in resp.json()['builds']:
        yield build['url']
        done += 1
        if done >= number_of_builds:
            break


def test_report(branch, suite, build_number):
    uri = (
        'https://jenkinsci.saltstack.com/job/{branch}/job'
        '/{suite}/{build_number}/testReport/api/json'
    ).format(
        branch=branch,
        suite=suite,
        build_number=build_number,
    )
    resp = requests.get(
        uri,
        headers={'accept': 'application/json'},
        auth=requests.auth.HTTPBasicAuth(user, password))
    if resp.status_code != 200:
        return
    testsuite = suite
    data = resp.json()
    for suite in data['suites']:
        for case in suite['cases']:
            test, _, klass = case['className'].rpartition('.')
            if case['status'] not in ('PASSED', 'SKIPPED',):
                # TODO: There is probably a better way -W. Werner, 2019-05-02
                # This was just the least intrusive, and quickest thing
                # I could do.
                uri = (
                    'https://jenkinsci.saltstack.com/job/{branch}/job'
                    '/{suite}/{build_number}/testReport/junit/{test}/'
                    '{testclass}/{testcase}'
                ).format(
                    branch=branch,
                    suite=testsuite,
                    build_number=build_number,
                    test=test,
                    testclass=klass,
                    testcase=case['name'],
                )
                yield case, uri


def main():
    test_failures = {}
    suite_failures = {}
    for job_url in all_jobs():
        parts = job_url.split('/')
        branch = parts[4]
        suite = parts[6]
        for url in builds(branch, suite, 1):
            parts = url.split('/')
            branch = parts[4]
            suite = parts[6]
            build_number = parts[7]
            has_failures = False
            for case, uri in test_report(branch, suite, build_number):
                has_failures = True
                full_name = '{}.{}'.format(case['className'], case['name'])
                failure = TestFailure(
                    full_name,
                    branch,
                    suite,
                    case,
                    uri=uri,
                )
                if full_name not in test_failures:
                    test_failures[full_name] = {}
                if branch not in test_failures[full_name]:
                    test_failures[full_name][branch] = [failure]
                else:
                    test_failures[full_name][branch].append(failure)
            if not has_failures:
                if suite not in suite_failures:
                    suite_failures[suite] = [branch]
                else:
                    suite_failures[suite].append(branch)
    for name in suite_failures:
        print("Suite {} failed on {}".format(name, ', '.join(suite_failures[name])))
    for name in test_failures:
        print('*' * 80)
        branches = []
        for branch in test_failures[name]:
            branches.append(
                '{} failed {}'.format(
                    branch, ', '.join(
                        [
                            f'[{str(x.suite)}]({x.uri})'
                            for x in test_failures[name][branch]
                        ]
                    )
                )
            )
        case = test_failures[name][branch][-1].case
        print(template.format(
            title=name,
            branches='\n'.join(branches),
            details=case['errorDetails'],
            stacktrace=case['errorStackTrace'],
        ))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    main()
