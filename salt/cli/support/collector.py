# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import copy
import yaml
import json
import logging
import tarfile
import time
import salt.ext.six as six

if six.PY2:
    import exceptions
else:
    import builtins as exceptions
    from io import IOBase as file

from io import BytesIO

import salt.utils.stringutils
import salt.utils.parsers
import salt.utils.verify
import salt.utils.platform
import salt.utils.process
import salt.exceptions
import salt.defaults.exitcodes
import salt.cli.caller
import salt.cli.support
import salt.cli.support.console
import salt.cli.support.intfunc
import salt.cli.support.localrunner
import salt.output.table_out
import salt.runner
import salt.utils.files


salt.output.table_out.__opts__ = {}
log = logging.getLogger(__name__)


class SupportDataCollector(object):
    '''
    Data collector. It behaves just like another outputter,
    except it grabs the data to the archive files.
    '''
    def __init__(self, name, output):
        '''
        constructor of the data collector
        :param name:
        :param path:
        :param format:
        '''
        self.archive_path = name
        self.__default_outputter = output
        self.__format = format
        self.__arch = None
        self.__current_section = None
        self.__current_section_name = None
        self.__default_root = time.strftime('%Y.%m.%d-%H.%M.%S-snapshot')
        self.out = salt.cli.support.console.MessagesOutput()

    def open(self):
        '''
        Opens archive.
        :return:
        '''
        if self.__arch is not None:
            raise salt.exceptions.SaltException('Archive already opened.')
        self.__arch = tarfile.TarFile.bz2open(self.archive_path, 'w')

    def close(self):
        '''
        Closes the archive.
        :return:
        '''
        if self.__arch is None:
            raise salt.exceptions.SaltException('Archive already closed')
        self._flush_content()
        self.__arch.close()
        self.__arch = None

    def _flush_content(self):
        '''
        Flush content to the archive
        :return:
        '''
        if self.__current_section is not None:
            buff = BytesIO()
            buff._dirty = False
            for action_return in self.__current_section:
                for title, ret_data in action_return.items():
                    if isinstance(ret_data, file):
                        self.out.put(ret_data.name, indent=4)
                        self.__arch.add(ret_data.name, arcname=ret_data.name)
                    else:
                        buff.write(salt.utils.stringutils.to_bytes(title + '\n'))
                        buff.write(salt.utils.stringutils.to_bytes(('-' * len(title)) + '\n\n'))
                        buff.write(salt.utils.stringutils.to_bytes(ret_data))
                        buff.write(salt.utils.stringutils.to_bytes('\n\n\n'))
                        buff._dirty = True
            if buff._dirty:
                buff.seek(0)
                tar_info = tarfile.TarInfo(name="{}/{}".format(self.__default_root, self.__current_section_name))
                if not hasattr(buff, 'getbuffer'):  # Py2's BytesIO is older
                    buff.getbuffer = buff.getvalue
                tar_info.size = len(buff.getbuffer())
                self.__arch.addfile(tarinfo=tar_info, fileobj=buff)

    def add(self, name):
        '''
        Start a new section.
        :param name:
        :return:
        '''
        if self.__current_section:
            self._flush_content()
        self.discard_current(name)

    def discard_current(self, name=None):
        '''
        Discard current section
        :return:
        '''
        self.__current_section = []
        self.__current_section_name = name

    def _printout(self, data, output):
        '''
        Use salt outputter to printout content.

        :return:
        '''
        opts = {'extension_modules': '', 'color': False}
        try:
            printout = salt.output.get_printout(output, opts)(data)
            if printout is not None:
                return printout.rstrip()
        except (KeyError, AttributeError, TypeError) as err:
            log.debug(err, exc_info=True)
            try:
                printout = salt.output.get_printout('nested', opts)(data)
                if printout is not None:
                    return printout.rstrip()
            except (KeyError, AttributeError, TypeError) as err:
                log.debug(err, exc_info=True)
                printout = salt.output.get_printout('raw', opts)(data)
                if printout is not None:
                    return printout.rstrip()

        return salt.output.try_printout(data, output, opts)

    def write(self, title, data, output=None):
        '''
        Add a data to the current opened section.
        :return:
        '''
        if not isinstance(data, (dict, list, tuple)):
            data = {'raw-content': str(data)}
        output = output or self.__default_outputter

        if output != 'null':
            try:
                if isinstance(data, dict) and 'return' in data:
                    data = data['return']
                content = self._printout(data, output)
            except Exception:  # Fall-back to just raw YAML
                content = None
        else:
            content = None

        if content is None:
            data = json.loads(json.dumps(data))
            if isinstance(data, dict) and data.get('return'):
                data = data.get('return')
            content = yaml.safe_dump(data, default_flow_style=False, indent=4)

        self.__current_section.append({title: content})

    def link(self, title, path):
        '''
        Add a static file on the file system.

        :param title:
        :param path:
        :return:
        '''
        # The filehandler needs to be explicitly passed here, so PyLint needs to accept that.
        # pylint: disable=W8470
        if not isinstance(path, file):
            path = salt.utils.files.fopen(path)
        self.__current_section.append({title: path})
        # pylint: enable=W8470


class SaltSupport(salt.utils.parsers.SaltSupportOptionParser):
    '''
    Class to run Salt Support subsystem.
    '''
    RUNNER_TYPE = 'run'
    CALL_TYPE = 'call'

    def _setup_fun_config(self, fun_conf):
        '''
        Setup function configuration.

        :param conf:
        :return:
        '''
        conf = copy.deepcopy(self.config)
        conf['file_client'] = 'local'
        conf['fun'] = ''
        conf['arg'] = []
        conf['kwarg'] = {}
        conf['cache_jobs'] = False
        conf['print_metadata'] = False
        conf.update(fun_conf)
        conf['fun'] = conf['fun'].split(':')[-1]  # Discard typing prefix

        return conf

    def _get_runner(self, conf):
        '''
        Get & setup runner.

        :param conf:
        :return:
        '''
        conf = self._setup_fun_config(copy.deepcopy(conf))
        if not getattr(self, '_runner', None):
            self._runner = salt.cli.support.localrunner.LocalRunner(conf)
        else:
            self._runner.opts = conf
        return self._runner

    def _get_caller(self, conf):
        '''
        Get & setup caller from the factory.

        :param conf:
        :return:
        '''
        conf = self._setup_fun_config(copy.deepcopy(conf))
        if not getattr(self, '_caller', None):
            self._caller = salt.cli.caller.Caller.factory(conf)
        else:
            self._caller.opts = conf
        return self._caller

    def _local_call(self, call_conf):
        '''
        Execute local call
        '''
        try:
            ret = self._get_caller(call_conf).call()
        except SystemExit:
            ret = 'Data is not available at this moment'
            self.out.error(ret)
        except Exception as ex:
            ret = 'Unhandled exception occurred: {}'.format(ex)
            log.debug(ex, exc_info=True)
            self.out.error(ret)

        return ret

    def _local_run(self, run_conf):
        '''
        Execute local runner

        :param run_conf:
        :return:
        '''
        try:
            ret = self._get_runner(run_conf).run()
        except SystemExit:
            ret = 'Runner is not available at this moment'
            self.out.error(ret)
        except Exception as ex:
            ret = 'Unhandled exception occurred: {}'.format(ex)
            log.debug(ex, exc_info=True)

        return ret

    def _internal_function_call(self, call_conf):
        '''
        Call internal function.

        :param call_conf:
        :return:
        '''
        def stub(*args, **kwargs):
            message = 'Function {} is not available'.format(call_conf['fun'])
            self.out.error(message)
            log.debug(
                'Attempt to run "%s" with %s arguments and %s parameters.',
                call_conf['fun'], call_conf['arg'], call_conf['kwargs']
            )
            return message

        return getattr(salt.cli.support.intfunc,
                       call_conf['fun'], stub)(self.collector,
                                               *call_conf['arg'],
                                               **call_conf['kwargs'])

    def _get_action(self, action_meta):
        '''
        Parse action and turn into a calling point.
        :param action_meta:
        :return:
        '''
        conf = {
            'fun': list(action_meta.keys())[0],
            'arg': [],
            'kwargs': {},
        }
        if not len(conf['fun'].split('.')) - 1:
            conf['salt.int.intfunc'] = True

        action_meta = action_meta[conf['fun']]
        info = action_meta.get('info', 'Action for {}'.format(conf['fun']))
        for arg in action_meta.get('args') or []:
            if not isinstance(arg, dict):
                conf['arg'].append(arg)
            else:
                conf['kwargs'].update(arg)

        return info, action_meta.get('output'), conf

    def collect_internal_data(self):
        '''
        Dumps current running pillars, configuration etc.
        :return:
        '''
        section = 'configuration'
        self.out.put(section)
        self.collector.add(section)
        self.out.put('Saving config', indent=2)
        self.collector.write('General Configuration', self.config)
        self.out.put('Saving pillars', indent=2)
        self.collector.write('Active Pillars', self._local_call({'fun': 'pillar.items'}))

        section = 'highstate'
        self.out.put(section)
        self.collector.add(section)
        self.out.put('Saving highstate', indent=2)
        self.collector.write('Rendered highstate', self._local_call({'fun': 'state.show_highstate'}))

    def _extract_return(self, data):
        '''
        Extracts return data from the results.

        :param data:
        :return:
        '''
        if isinstance(data, dict):
            data = data.get('return', data)

        return data

    def collect_local_data(self, profile=None, profile_source=None):
        '''
        Collects master system data.
        :return:
        '''
        def call(func, *args, **kwargs):
            '''
            Call wrapper for templates
            :param func:
            :return:
            '''
            return self._extract_return(self._local_call({'fun': func, 'arg': args, 'kwarg': kwargs}))

        def run(func, *args, **kwargs):
            '''
            Runner wrapper for templates
            :param func:
            :return:
            '''
            return self._extract_return(self._local_run({'fun': func, 'arg': args, 'kwarg': kwargs}))

        scenario = profile_source or salt.cli.support.get_profile(profile or self.config['support_profile'], call, run)
        for category_name in scenario:
            self.out.put(category_name)
            self.collector.add(category_name)
            for action in scenario[category_name]:
                if not action:
                    continue
                action_name = next(iter(action))
                if not isinstance(action[action_name], six.string_types):
                    info, output, conf = self._get_action(action)
                    action_type = self._get_action_type(action)  # run:<something> for runners
                    if action_type == self.RUNNER_TYPE:
                        self.out.put('Running {}'.format(info.lower()), indent=2)
                        self.collector.write(info, self._local_run(conf), output=output)
                    elif action_type == self.CALL_TYPE:
                        if not conf.get('salt.int.intfunc'):
                            self.out.put('Collecting {}'.format(info.lower()), indent=2)
                            self.collector.write(info, self._local_call(conf), output=output)
                        else:
                            self.collector.discard_current()
                            self._internal_function_call(conf)
                    else:
                        self.out.error('Unknown action type "{}" for action: {}'.format(action_type, action))
                else:
                    # TODO: This needs to be moved then to the utils.
                    #       But the code is not yet there (other PRs)
                    self.out.msg('\n'.join(salt.cli.support.console.wrap(action[action_name])), ident=2)

    def _get_action_type(self, action):
        '''
        Get action type.
        :param action:
        :return:
        '''
        action_name = next(iter(action or {'': None}))
        if ':' not in action_name:
            action_name = '{}:{}'.format(self.CALL_TYPE, action_name)

        return action_name.split(':')[0] or None

    def _cleanup(self):
        '''
        Cleanup if crash/exception
        :return:
        '''
        if (hasattr(self, 'config')
           and self.config.get('support_archive')
           and os.path.exists(self.config['support_archive'])):
            self.out.warning('Terminated earlier, cleaning up')
            try:
                os.unlink(self.config['support_archive'])
            except Exception as err:
                log.debug(err)
                self.out.error('{} while cleaning up.'.format(err))

    def _check_existing_archive(self):
        '''
        Check if archive exists or not. If exists and --force was not specified,
        bail out. Otherwise remove it and move on.

        :return:
        '''
        if os.path.exists(self.config['support_archive']):
            if self.config['support_archive_force_overwrite']:
                self.out.warning('Overwriting existing archive: {}'.format(self.config['support_archive']))
                try:
                    os.unlink(self.config['support_archive'])
                except Exception as err:
                    log.debug(err)
                    self.out.error('{} while trying to overwrite existing archive.'.format(err))
                ret = True
            else:
                self.out.warning('File {} already exists.'.format(self.config['support_archive']))
                ret = False
        else:
            ret = True

        return ret

    def run(self):
        exit_code = salt.defaults.exitcodes.EX_OK
        self.out = salt.cli.support.console.MessagesOutput()
        try:
            self.parse_args()
        except (Exception, SystemExit) as ex:
            if not isinstance(ex, exceptions.SystemExit):
                exit_code = salt.defaults.exitcodes.EX_GENERIC
                self.out.error(ex)
            elif isinstance(ex, exceptions.SystemExit):
                exit_code = ex.code
            else:
                exit_code = salt.defaults.exitcodes.EX_GENERIC
                self.out.error(ex)
        else:
            if self.config['log_level'] not in ('quiet', ):
                self.setup_logfile_logger()
                salt.utils.verify.verify_log(self.config)
                salt.cli.support.log = log  # Pass update logger so trace is available

            if self.config['support_profile_list']:
                self.out.put('List of available profiles:')
                for idx, profile in enumerate(salt.cli.support.get_profiles(self.config)):
                    msg_template = '  {}. '.format(idx + 1) + '{}'
                    self.out.highlight(msg_template, profile)
                    exit_code = salt.defaults.exitcodes.EX_OK
            elif self.config['support_show_units']:
                self.out.put('List of available units:')
                for idx, unit in enumerate(self.find_existing_configs(None)):
                    msg_template = '  {}. '.format(idx + 1) + '{}'
                    self.out.highlight(msg_template, unit)
                exit_code = salt.defaults.exitcodes.EX_OK
            else:
                if not self.config['support_profile']:
                    self.print_help()
                    raise SystemExit()

                if self._check_existing_archive():
                    try:
                        self.collector = SupportDataCollector(self.config['support_archive'],
                                                              output=self.config['support_output_format'])
                    except Exception as ex:
                        self.out.error(ex)
                        exit_code = salt.defaults.exitcodes.EX_GENERIC
                        log.debug(ex, exc_info=True)
                    else:
                        try:
                            self.collector.open()
                            self.collect_local_data()
                            self.collect_internal_data()
                            self.collector.close()

                            archive_path = self.collector.archive_path
                            self.out.highlight('\nSupport data has been written to "{}" file.\n',
                                               archive_path, _main='YELLOW')
                        except Exception as ex:
                            self.out.error(ex)
                            log.debug(ex, exc_info=True)
                            exit_code = salt.defaults.exitcodes.EX_SOFTWARE

        if exit_code:
            self._cleanup()

        sys.exit(exit_code)
