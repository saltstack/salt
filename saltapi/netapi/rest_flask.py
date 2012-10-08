'''
A REST API for Salt
'''
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import request
from flask import url_for
from flask.views import MethodView
from werkzeug import exceptions

import salt.client
import salt.runner
import salt.utils

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
        self.local = salt.client.LocalClient(__opts__['conf_file'])
        self.runner = salt.runner.RunnerClient(__opts__)

class JobsView(SaltAPI):
    '''
    View Salt jobs or create new jobs (run commands)
    '''
    def get_job_by_jid(self, jid):
        '''
        Return information on a previously run job
        '''
        ret = self.runner.cmd('jobs.lookup_jid', [jid])
        return jsonify(ret)

    def get_jobs_list(self):
        '''
        Return a previously run jobs
        '''
        ret = self.runner.cmd('jobs.list_jobs', [])
        return jsonify(ret)

    def get(self, jid=None):
        '''
        View a list of previously run jobs, or fetch a single job
        '''
        if jid:
            return self.get_job_by_jid(jid)

        return self.get_jobs_list()

class MinionsView(SaltAPI):
    def get(self, mid=None):
        '''
        List all minions (and grains and functions for each minion)
        '''
        return jsonify(self.local.cmd(mid or '*',
            ['sys.list_functions', 'grains.items'], [[], []]))

    def post(self):
        '''
        Begin command execution on minion(s) and redirect to the JID URI
        '''
        tgt = request.form.get('tgt')
        expr = request.form.get('expr', 'glob')
        funs = request.form.getlist('fun')
        args = []

        # Make a list & strip out empty strings: ['']
        for i in request.form.getlist('arg'):
            args.append([i] if i else [])

        if not tgt:
            raise exceptions.BadRequest("Missing target.")

        if not funs:
            raise exceptions.BadRequest("Missing command(s).")

        if len(funs) != len(args):
            raise exceptions.BadRequest(
                    "Mismatched number of commands and args.")

        jid = self.local.run_job(tgt, funs, args, expr_form=expr).get('jid')
        return redirect(url_for('jobs', jid=jid, _method='GET'))

class RunnersView(SaltAPI):
    def get(self):
        '''
        Return all available runners
        '''
        return jsonify({'runners': self.runner.functions.keys()})

    def post(self):
        '''
        Execute runner commands
        '''
        fun = request.form.get('fun')
        arg = request.form.get('arg')

        # pylint: disable-msg=W0142
        ret = self.runner.cmd(fun, arg)
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
    app.config['TRAP_HTTP_EXCEPTIONS'] = True
    app.error_handler_spec[None][500] = make_json_error

    jobs = JobsView.as_view('jobs', app=app)
    app.add_url_rule('/jobs', view_func=jobs, methods=['GET', 'POST'])
    app.add_url_rule('/jobs/<jid>', view_func=jobs, methods=['GET'])

    minions = MinionsView.as_view('minions', app=app)
    app.add_url_rule('/minions', view_func=minions, methods=['GET', 'POST'])
    app.add_url_rule('/minions/<mid>', view_func=minions,
            methods=['GET', 'POST'])

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
