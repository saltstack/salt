# -*- coding: utf-8 -*-
'''
Test module for syslog_ng state
'''

import yaml
import re
import tempfile
import os

from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

from salt.states import syslog_ng

syslog_ng.__salt__ = {}

SOURCE_1_CONFIG = {
        "id": "s_tail",
        "config":
"""
source:
    - file:
      - "/var/log/apache/access.log"
      - follow_freq : 1
      - flags:
        - no-parse
        - validate-utf8
"""}

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
    - ip: 0.0.0.0
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
};
"""
)

FILTER_1_CONFIG = {
    "id": "f_json",
    "config": (
"""
filter:
  - match:
    - "@json:"
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
    - "$ISODATE $HOST $MSG\n"
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
    - "${.json.message}"
    - value : "$MESSAGE"
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
    "config":
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
          - "/tmp/json-input.log"
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
      - "/tmp/all.log"
      - template: t_gsoc2014
"""
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


def remove_whitespaces(source):
    return re.sub(r"\s+", "", source.strip())


@skipIf(NO_MOCK, NO_MOCK_REASON)
#@skipIf(syslog_ng.__virtual__() is False, 'Syslog-ng must be installed')
class SyslogNGTestCase(TestCase):

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

    def _config_generator_template(self, yaml_input, expected):
        parsed_yaml_config = yaml.load(yaml_input["config"])
        id = yaml_input["id"]
        got = syslog_ng.config(id, config=parsed_yaml_config, write=False)
        config = got["changes"]["new"]
        self.assertEqual(remove_whitespaces(expected), remove_whitespaces(config))
        self.assertEqual(False, got["result"])
        # print("#######################")
        # print(yaml_input["config"])
        # print("-------")
        # print(got)

    def test_write_config(self):
        yaml_inputs = (SOURCE_2_CONFIG, SOURCE_1_CONFIG, FILTER_1_CONFIG, TEMPLATE_1_CONFIG, REWRITE_1_CONFIG, LOG_1_CONFIG)
        expected_outputs = (SOURCE_2_EXPECTED, SOURCE_1_EXPECTED, FILTER_1_EXPECTED, TEMPLATE_1_EXPECTED, REWRITE_1_EXPECTED, LOG_1_EXPECTED)
        config_file_fd, config_file_name = tempfile.mkstemp()
        os.close(config_file_fd)
        syslog_ng.set_config_file(config_file_name)
        syslog_ng.write_version("3.6")
        syslog_ng.write_config("", config='@include "scl.conf"')

        for i in yaml_inputs:
            parsed_yaml_config = yaml.load(i["config"])
            id = i["id"]
            got = syslog_ng.config(id, config=parsed_yaml_config, write=True)

        written_config = ""
        with open(config_file_name, "r") as f:
            written_config = f.read()

        for i in expected_outputs:
            self.assertIn(i, written_config)

        self.assertIn(SOURCE_1_EXPECTED, written_config)

        syslog_ng.set_config_file("")
        os.remove(config_file_name)

    def test_started_state_generate_valid_cli_command(self):
        mock_func = MagicMock(return_value={"retcode": 0, "stdout": "", "pid": 1000})

        with patch.dict(syslog_ng.__salt__, {'cmd.run_all': mock_func}):
            got = syslog_ng.started(user="joe", group="users", enable_core=True)
            command = got["changes"]["new"]
            self.assertTrue(command.endswith("syslog-ng --user=joe --group=users --enable-core --cfgfile=/etc/syslog-ng.conf"))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SyslogNGTestCase, needs_daemon=False)
