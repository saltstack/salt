'''
A REST API for Salt
'''
from flask import Flask
from flask import jsonify
from flask import request
from flask.views import MethodView
from werkzeug import exceptions

import salt.client
import salt.runner
import saltapi.loader

def __virtual__():
    '''
    Verify enough infos to actually start server.
    '''
    # if not 'port' in __opts__ or not __opts__['port']:
    #     return False

    return 'rest'

class SaltAPI(MethodView):
    '''
    Base class for salt objects
    '''
    def __init__(self, app, *args, **kwargs):
        self.app = app
        self.runners = saltapi.loader.runner(__opts__)
        self.local = salt.client.LocalClient(__opts__['conf_file'])

class JobsView(SaltAPI):
    '''
    View Salt jobs or create new jobs (run commands)
    '''
    def get_job_by_jid(self, jid):
        '''
        Return information on a previously run job
        '''
        ret = self.runners['jobs.lookup_jid'](jid)
        return jsonify(ret)

    def get_jobs_list(self):
        '''
        Return a previously run jobs
        '''
        ret = self.runners['jobs.list_jobs']()
        return jsonify(ret)

    def get(self, jid=None):
        '''
        View a list of previously run jobs, or fetch a single job
        '''
        if jid:
            return self.get_job_by_jid(jid)

        return self.get_jobs_list()

    def post(self):
        '''
        Run minion commands
        '''
        ret = self.local.cmd(
                request.form['tgt'],
                request.form['cmd'])
        return jsonify(ret)

class RunnersView(SaltAPI):
    def get(self):
        '''
        Return all available runners
        '''
        return jsonify({'runners': self.runners.keys()})

    def post(self):
        '''
        Execute runner commands
        '''
        cmd = request.form['cmd']

        if not cmd in self.runners:
            raise exceptions.BadRequest("Runner '{0}' not found".format(cmd))

        ret = self.runners[cmd]()
        return jsonify({'return': ret})

def build_app():
    '''
    Build the Flask app
    '''
    app = Flask(__name__)

    def make_json_error(ex):
        '''
        Return errors as JSON objects
        '''
        status = getattr(ex, 'code', 500)

        response = jsonify(message='Error {0}: {1}'.format(
            status,
            ex if app.debug else 'Internal server error',
        ))
        response.status_code = status

        return response

    # Allow using custom error handler when debug=True
    app.config['PROPAGATE_EXCEPTIONS'] = False
    app.error_handler_spec[None][500] = make_json_error

    jobs = JobsView.as_view('jobs', app=app)
    app.add_url_rule('/jobs', view_func=jobs, methods=['GET', 'POST'])
    app.add_url_rule('/jobs/<jid>', view_func=jobs, methods=['GET'])

    runners = RunnersView.as_view('runners', app=app)
    app.add_url_rule('/runners', view_func=runners, methods=['GET', 'POST'])

    return app


def start():
    '''
    Server loop here. Started in a multiprocess.
    '''
    app = build_app()
    # port = __opts__['port']
    app.run(host='0.0.0.0', port=8000, debug=True)
