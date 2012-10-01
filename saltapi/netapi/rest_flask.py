'''
A REST API for Salt
'''
from flask import Flask
from flask import jsonify
from flask import request
from flask.views import MethodView
from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException

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


def make_json_error(ex):
    '''
    Creates a JSON-oriented Flask app.

    All error responses that you don't specifically
    manage yourself will have application/json content
    type, and will contain JSON like this (just an example)::

        { "message": "405: Method Not Allowed" }

    http://flask.pocoo.org/snippets/83/

    '''
    response = jsonify(message=str(ex))
    response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
    return response


class JobsView(MethodView):
    '''
    View Salt jobs or create new jobs (run commands)
    '''
    def __init__(self):
        self.runners = saltapi.loader.runner(__opts__)
        self.local = salt.client.LocalClient(__opts__['conf_file'])

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


def build_app():
    '''
    Build the Flask app
    '''
    app = Flask('rest_flask')
    jobs = JobsView.as_view('jobs')

    for code in default_exceptions.iterkeys():
        app.error_handler_spec[None][code] = make_json_error

    app.add_url_rule('/jobs', view_func=jobs, methods=['GET', 'POST'])
    app.add_url_rule('/jobs/<int:jid>', view_func=jobs, methods=['GET'])

    return app


def bind():
    '''
    Server loop here. Started in a multiprocess.
    '''
    app = build_app()
    # port = __opts__['port']
    app.run(host='0.0.0.0', port=8000, debug=True)
