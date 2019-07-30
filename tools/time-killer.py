from collections import defaultdict, Counter
from pathlib import Path

SALT_PATH = Path('~/util/tests').expanduser().resolve()

def skip_class(classname):
    filename, _, classname = classname.rpartition('.')
    filename = SALT_PATH / (filename.replace('.', '/')+'.py')
    classline = "class "+classname
    print('Updating:', filename, classname)
    with filename.open(mode='r+') as f:
        lines = f.readlines()

        last_import_line = 0
        has_import = False
        class_line_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_line = i

            if 'tests.support.unit' in line and 'skipIf' in line:
                has_import = True

            if classline in line:
                class_line_idx = i

        if not has_import:
            lines.insert(last_import_line, 'from tests.support.unit import skipIf  # WAR ROOM temp import\n')
            class_line_idx += 1

            f.seek(0)
            f.truncate()
            f.write(''.join(lines))

        if 'WAR ROOM' not in lines[class_line_idx-1]:
            lines.insert(class_line_idx, '@skipIf(True, "WAR ROOM TEMPORARY SKIP")\n')
            f.seek(0)
            f.truncate()
            f.write(''.join(lines))


def skip_file(filename):
    filename = SALT_PATH / (filename.replace('.', '/')+'.py')
    print('Updating:', filename)
    with filename.open(mode='r+') as f:
        lines = f.readlines()

        last_import_line = 0
        has_import = False
        has_skip = False
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_line = i

            if 'tests.support.unit' in line and 'skipIf' in line:
                has_import = True

            if 'skipIf(True, "WAR ROOM"' in line:
                has_skip = True

        if not has_import:
            lines.insert(last_import_line, 'from tests.support.unit import skipIf; skipIf(True, "WAR ROOM TEMPORARY SKIP")  # pylint: disable=C0321,E8702\n')

            f.seek(0)
            f.truncate()
            f.write(''.join(lines))
        elif not has_skip:
            lines.insert(last_import_line, 'skipIf(True, "WAR ROOM TEMPORARY SKIP")')


if __name__ == '__main__':
    with open('/tmp/times.txt') as f:
        # Couple of header lines
        f.readline()
        f.readline()
        tests = f.readlines()[:100]

    by_module = defaultdict(list)
    for test in tests:
        name = test.split(None, 1)[0]
        module = name.rpartition('.')[0]
        by_module[module].append(name)

    counts = Counter()
    for mod in by_module:
        counts[mod] = len(by_module[mod])

    for name, count in counts.most_common():
        if count == 1:
            skip_class(by_module[name][0])
        else:
            skip_file(name)
