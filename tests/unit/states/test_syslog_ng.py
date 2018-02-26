# -*- coding: utf-8 -*-
'''
Test module for syslog_ng state
'''

# Import python libs
from __future__ import absolute_import
import os
import re
import tempfile
import yaml

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

import salt.utils
import salt.states.syslog_ng as syslog_ng
import salt.modules.syslog_ng as syslog_ng_module

SOURCE_1_CONFIG = {
    "id": "s_tail",
    "config": (
        """
        source:
            - file:
              - '"/var/log/apache/access.log"'
              - follow_freq : 1
              - flags:
                - no-parse
                - validate-utf8
        """)
}

SOURCE_1_EXPECTED = (
"""
source s_tail {
   file(
         "/var/log/apache/access.log",
         follow_freq(1),
         flags(no-parse, validate-utf8)
   );
};
"""
)

SOURCE_2_CONFIG = {
    "id": "s_gsoc2014",
    "config": (
        """
        source:
          - tcp:
            - ip: '"0.0.0.0"'
            - port: 1234
            - flags: no-parse
        """
    )
}

SOURCE_2_EXPECTED = (
"""
source s_gsoc2014 {
   tcp(
         ip("0.0.0.0"),
         port(1234),
         flags(no-parse)
   );
};"""
)

FILTER_1_CONFIG = {
    "id": "f_json",
    "config": (
        """
        filter:
          - match:
            - '"@json:"'
        """
    )
}

FILTER_1_EXPECTED = (
    """
    filter f_json {
       match(
             "@json:"
       );
    };
    """
)

TEMPLATE_1_CONFIG = {
    "id": "t_demo_filetemplate",
    "config": (
        """
        template:
          - template:
            - '"$ISODATE $HOST $MSG\n"'
          - template_escape:
            - "no"
        """
    )
}

TEMPLATE_1_EXPECTED = (
    """
    template t_demo_filetemplate {
       template(
             "$ISODATE $HOST $MSG "
       );
       template_escape(
             no
       );
    };
    """
)

REWRITE_1_CONFIG = {
    "id": "r_set_message_to_MESSAGE",
    "config": (
        """
        rewrite:
          - set:
            - '"${.json.message}"'
            - value : '"$MESSAGE"'
        """
    )
}

REWRITE_1_EXPECTED = (
    """
    rewrite r_set_message_to_MESSAGE {
       set(
             "${.json.message}",
             value("$MESSAGE")
       );
    };
    """
)

LOG_1_CONFIG = {
    "id": "l_gsoc2014",
    "config": (
        """
        log:
          - source: s_gsoc2014
          - junction:
            - channel:
              - filter: f_json
              - parser: p_json
              - rewrite: r_set_json_tag
              - rewrite: r_set_message_to_MESSAGE
              - destination:
                - file:
                  - '"/tmp/json-input.log"'
                  - template: t_gsoc2014
              - flags: final
            - channel:
              - filter: f_not_json
              - parser:
                - syslog-parser: []
              - rewrite: r_set_syslog_tag
              - flags: final
          - destination:
            - file:
              - '"/tmp/all.log"'
              - template: t_gsoc2014
        """
    )
}

LOG_1_EXPECTED = (
    """
    log {
       source(s_gsoc2014);
       junction {
          channel {
             filter(f_json);
             parser(p_json);
             rewrite(r_set_json_tag);
             rewrite(r_set_message_to_MESSAGE);
             destination {
                file(
                      "/tmp/json-input.log",
                      template(t_gsoc2014)
                );
             };
             flags(final);
          };
          channel {
             filter(f_not_json);
             parser {
                syslog-parser(

                );
             };
             rewrite(r_set_syslog_tag);
             flags(final);
          };
       };
       destination {
          file(
                "/tmp/all.log",
                template(t_gsoc2014)
          );
       };
    };
    """
)

OPTIONS_1_CONFIG = {
    "id": "global_options",
    "config": (
        """
        options:
          - time_reap: 30
          - mark_freq: 10
          - keep_hostname: "yes"
        """
    )
}

OPTIONS_1_EXPECTED = (
    """
    options {
        time_reap(30);
        mark_freq(10);
        keep_hostname(yes);
    };
    """
)

SHORT_FORM_CONFIG = {
    "id": "source.s_gsoc",
    "config": (
        """
          - tcp:
            - ip: '"0.0.0.0"'
            - port: 1234
            - flags: no-parse
        """
    )
}

SHORT_FORM_EXPECTED = (
    """
    source s_gsoc {
        tcp(
            ip(
                "0.0.0.0"
            ),
            port(
                1234
            ),
            flags(
              no-parse
            )
        );
    };
    """
)

GIVEN_CONFIG = {
    'id': "config.some_name",
    'config': (
        """
               source s_gsoc {
                  tcp(
                      ip(
                          "0.0.0.0"
                      ),
                      port(
                          1234
                      ),
                      flags(
                        no-parse
                      )
                  );
               };
        """
    )
}

_SALT_VAR_WITH_MODULE_METHODS = {
    'syslog_ng.config': syslog_ng_module.config,
    'syslog_ng.start': syslog_ng_module.start,
    'syslog_ng.reload': syslog_ng_module.reload_,
    'syslog_ng.stop': syslog_ng_module.stop,
    'syslog_ng.write_version': syslog_ng_module.write_version,
    'syslog_ng.write_config': syslog_ng_module.write_config
}


def remove_whitespaces(source):
    return re.sub(r"\s+", "", source.strip())


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SyslogNGTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            syslog_ng: {},
            syslog_ng_module: {'__opts__': {'test': False}}
        }

    def test_generate_source_config(self):
        self._config_generator_template(SOURCE_1_CONFIG, SOURCE_1_EXPECTED)

    def test_generate_log_config(self):
        self._config_generator_template(LOG_1_CONFIG, LOG_1_EXPECTED)

    def test_generate_tcp_source_config(self):
        self._config_generator_template(SOURCE_2_CONFIG, SOURCE_2_EXPECTED)

    def test_generate_filter_config(self):
        self._config_generator_template(FILTER_1_CONFIG, FILTER_1_EXPECTED)

    def test_generate_template_config(self):
        self._config_generator_template(TEMPLATE_1_CONFIG, TEMPLATE_1_EXPECTED)

    def test_generate_rewrite_config(self):
        self._config_generator_template(REWRITE_1_CONFIG, REWRITE_1_EXPECTED)

    def test_generate_global_options_config(self):
        self._config_generator_template(OPTIONS_1_CONFIG, OPTIONS_1_EXPECTED)

    def test_generate_short_form_statement(self):
        self._config_generator_template(SHORT_FORM_CONFIG, SHORT_FORM_EXPECTED)

    def test_generate_given_config(self):
        self._config_generator_template(GIVEN_CONFIG, SHORT_FORM_EXPECTED)

    def _config_generator_template(self, yaml_input, expected):
        parsed_yaml_config = yaml.load(yaml_input["config"])
        id = yaml_input["id"]

        with patch.dict(syslog_ng.__salt__, _SALT_VAR_WITH_MODULE_METHODS):
            got = syslog_ng.config(id, config=parsed_yaml_config, write=False)
            config = got["changes"]["new"]
            self.assertEqual(remove_whitespaces(expected), remove_whitespaces(config))
            self.assertEqual(False, got["result"])

    def test_write_config(self):
        yaml_inputs = (
            SOURCE_2_CONFIG, SOURCE_1_CONFIG, FILTER_1_CONFIG, TEMPLATE_1_CONFIG, REWRITE_1_CONFIG, LOG_1_CONFIG
        )
        expected_outputs = (
            SOURCE_2_EXPECTED, SOURCE_1_EXPECTED, FILTER_1_EXPECTED, TEMPLATE_1_EXPECTED, REWRITE_1_EXPECTED,
            LOG_1_EXPECTED
        )
        config_file_fd, config_file_name = tempfile.mkstemp()
        os.close(config_file_fd)

        with patch.dict(syslog_ng.__salt__, _SALT_VAR_WITH_MODULE_METHODS):
            syslog_ng_module.set_config_file(config_file_name)
            syslog_ng_module.write_version("3.6")
            syslog_ng_module.write_config(config='@include "scl.conf"')

            for i in yaml_inputs:
                parsed_yaml_config = yaml.load(i["config"])
                id = i["id"]
                got = syslog_ng.config(id, config=parsed_yaml_config, write=True)

            written_config = ""
            with salt.utils.fopen(config_file_name, "r") as f:
                written_config = f.read()

            config_without_whitespaces = remove_whitespaces(written_config)
            for i in expected_outputs:
                without_whitespaces = remove_whitespaces(i)
                self.assertIn(without_whitespaces, config_without_whitespaces)

            syslog_ng_module.set_config_file("")
            os.remove(config_file_name)

    def test_started_state_generate_valid_cli_command(self):
        mock_func = MagicMock(return_value={"retcode": 0, "stdout": "", "pid": 1000})

        with patch.dict(syslog_ng.__salt__, _SALT_VAR_WITH_MODULE_METHODS):
            with patch.dict(syslog_ng_module.__salt__, {'cmd.run_all': mock_func}):
                got = syslog_ng.started(user="joe", group="users", enable_core=True)
                command = got["changes"]["new"]
                self.assertTrue(
                    command.endswith("syslog-ng --user=joe --group=users --enable-core --cfgfile=/etc/syslog-ng.conf"))
