import os
from testtools import TestCase

from cloudify_cli import inputs
from cloudify_cli.exceptions import CloudifyCliError


class InputsToDictTest(TestCase):
    def test_valid_inline(self):
        resources = ['key1=value1;key2=value2']
        result = inputs.inputs_to_dict(resources)
        self.assertDictEqual(result, {'key1': 'value1',
                                      'key2': 'value2'})

    def test_inline_not_dict(self):
        resources = ['key1failure']
        self._verify_not_dict(resources)

    def test_invalid_yaml(self):
        resources = [os.path.join(os.path.dirname(__file__),
                                  'resources',
                                  'inputs',
                                  'bad_format.yaml')]
        self._verify_root_cause(resources)

    def test_yaml_not_dict(self):
        resources = [os.path.join(os.path.dirname(__file__),
                                  'resources',
                                  'inputs',
                                  'not_dict.yaml')]
        self._verify_not_dict(resources)

    def _verify_root_cause(self, resources):
        with self.assertRaisesRegex(CloudifyCliError, 'Root cause'):
            inputs.inputs_to_dict(resources)

    def _verify_not_dict(self, resources):
        with self.assertRaisesRegex(
                CloudifyCliError, 'does not represent a dictionary'):
            inputs.inputs_to_dict(resources)
