'''A REST API for Salt

'''
from flask import Flask
from flask import jsonify
from flask import request
from flask.views import MethodView
from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException

import salt.client
import salt.loader
import salt.runner

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

class SaltAPI(MethodView):
    '''
    A collection of convenience functions for use when creating API endpoints
    '''
    def get_client(self):
        '''
        Return, or instantiate and return, a Salt LocalClient
        '''
        if not hasattr(self, '_client'):
            self._client = salt.client.LocalClient(__opts__['conf_file'])

        return self._client

    def get_runner(self):
        '''
        Return, or instantiate and return, a Salt runner dict
        '''
        if not hasattr(self, '_runner'):
            self._runner = salt.loader.runner(__opts__)

        return self._runner

class JobsView(SaltAPI):
    '''
    View Salt jobs or create new jobs (run commands)
    '''
    def get_job_by_jid(self, jid):
        '''
        Return information on a previously run job
        '''
        runner = self.get_runner()
        runner['jobs.lookup_jid'](jid)

        # TODO: add cache headers based on the keep_jobs settings
        client = self.get_client()
        ret = client.cmd('*', ['grains.items', 'sys.list_functions'], [[], []])
        return jsonify(ret)

    def get_jobs_list(self):
        '''
        Return a previously run jobs
        '''
        runner = self.get_runner()
        return runner['jobs.list_jobs']()

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
        client = self.get_client()
        runner = self.get_runner()
        ret = client.cmd(
                request.form['tgt'],
                request.form['cmd'])
        return jsonify(ret)

def build_app():
    '''
    Build the Flask app
    '''
    app = Flask(__name__)
    jobs = JobsView.as_view('jobs')

    for code in default_exceptions.iterkeys():
        app.error_handler_spec[None][code] = make_json_error

    app.add_url_rule('/jobs', view_func=jobs, methods=['GET', 'POST'])
    app.add_url_rule('/jobs/<int:jid>', view_func=jobs, methods=['GET'])

    return app

def __virtual__():
    '''
    Verify enough infos to actually start server.
    '''
    # if not 'port' in __opts__ or not __opts__['port']:
    #     return False

    return 'rest'

def bind():
    '''
    Server loop here. Started in a multiprocess.
    '''
    app = build_app()
    # port = __opts__['port']
    app.run(host='0.0.0.0', port=8000, debug=True)
