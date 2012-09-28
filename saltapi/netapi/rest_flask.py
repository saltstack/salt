'''A REST API for Salt

'''
from flask import Flask
from flask import jsonify
from flask import request
from flask.views import MethodView
from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException

import salt.client

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
    def __init__(self, *args, **kwargs):
        super(SaltAPI, self).__init__(*args, **kwargs)
        self.client = salt.client.LocalClient(__opts__['conf_file'])

    def get(self):
        ret = self.client.cmd('*', ['grains.items', 'sys.list_functions'], [[], []])
        return jsonify(ret)

    def post(self):
        '''
        Return grains and available functions for each minion
        '''
        ret = self.client.cmd(
                request.form['tgt'],
                request.form['cmd'])
        return jsonify(ret)

def build_app():
    '''
    Build the Flask app

    '''
    app = Flask(__name__)

    for code in default_exceptions.iterkeys():
        app.error_handler_spec[None][code] = make_json_error

    app.add_url_rule('/', view_func=SaltAPI.as_view('index'))

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
