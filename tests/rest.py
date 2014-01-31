from bottle import route, run, template, static_file

PACKAGES = {'coreutils': '1.05'}
SERVICES = {'apache': 'stopped', 'postgresql': 'stopped', 'redbull': 'running'}
INFO = { 'os':'RestExampleOS', 'kernel':'0.0000001', 'housecat':'Are you kidding?'}

@route('/package/list')
def index():
    return PACKAGES

@route('/package/install/<name>/<version>')
def index(name, version):
    PACKAGES[name] = version
    return { 'comment': 'installed', 'ret': True }

@route('/package/remove/<name>')
def index(name):
    PACKAGES.pop(name, None)
    return { 'comment': 'removed', 'ret': True }

@route('/package/status/<name>')
def index(name):
    try:
        return PACKAGES[name]
    except KeyError:
        return { 'comment': 'not present', 'ret': False }

@route('/service/list')
def index():
    return SERVICES

@route('/service/start/<name>')
def index(name):
    if name in SERVICES:
        SERVICES[name] = 'running'
        return {'comment': 'running', 'ret': True}
    else:
        return { 'comment': 'not present', 'ret': False }

@route('/service/stop/<name>')
def index(name):
    if name in SERVICES:
        SERVICES[name] = 'stopped'
        return {'comment': 'stopped', 'ret': True}
    else:
        return { 'comment': 'not present', 'ret': False }

@route('/service/status/<name>')
def index(name):
    try:
        return {'comment': SERVICES[name], 'ret': True}
    except KeyError:
        return { 'comment': 'not present', 'ret': False }

@route('/service/restart/<name>')
def index(name):
    if name in SERVICES:
        return {'comment': 'restarted', 'ret': True}
    else:
        return { 'comment': 'restart failed: not present', 'ret': False }

@route('/ping')
def index():
    return { 'comment': 'pong', 'ret': True }

@route('/info')
def index():
    return INFO

@route('/id')
def index():
    return 'rest_sample-localhost'

@route('/monitor')
def index():
    services_html = '<table>'
    for s in SERVICES:
        services_html += '<tr><td>{}</td><td>{}</td></tr>'.format(s, SERVICES[s])
    services_html += '</table>'
    packages_html = '<table>'
    for s in PACKAGES:
        packages_html += '<tr><td>{}</td><td>{}</td></tr>'.format(s, PACKAGES[s])
    packages_html = '</table>'

    return template('monitor', services_html=services_html, packages_html=packages_html)

@route('/dist/<filename:path>')
def send_static(filename):
    print filename
    return static_file(filename, root='./dist/')

run(host='localhost', port=8080)
