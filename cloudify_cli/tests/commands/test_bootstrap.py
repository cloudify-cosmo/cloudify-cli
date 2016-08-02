from mock import patch

from ... import common
from ...bootstrap import bootstrap
from .test_base import CliCommandTest
from .constants import BLUEPRINTS_DIR, SAMPLE_BLUEPRINT_PATH


class BootstrapTest(CliCommandTest):

    def test_bootstrap_install_plugins(self):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap --install-plugins {0}'.format(blueprint_path)

        with patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.assert_method_called(
                command=command,
                module=common,
                function_name='install_blueprint_plugins',
                kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_no_validations_install_plugins(self):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = ('cfy bootstrap --skip-validations '
                   '--install-plugins {0}'.format(blueprint_path))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='install_blueprint_plugins',
            kwargs=dict(blueprint_path=blueprint_path)
        )

    def test_bootstrap_no_validations_add_ignore_bootstrap_validations(self):
        command = ('cfy bootstrap --skip-validations {0} '
                   '-i "some_input=some_value"'.format(
                    SAMPLE_BLUEPRINT_PATH))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='add_ignore_bootstrap_validations_input',
            args=[{
                u'some_input': u'some_value',
                'key1': 'default_val1',
                'key2': 'default_val2',
                'key3': 'default_val3'
            }]
        )

    def test_viable_ignore_bootstrap_validations_input(self):
        inputs = dict()
        common.add_ignore_bootstrap_validations_input(inputs)
        self.assertTrue(inputs['ignore_bootstrap_validations'])

    def test_bootstrap_missing_plugin(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap {0}'.format(blueprint_path)

        with patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.invoke(
                command=command,
                err_str_segment='No module named tasks',
                exception=ImportError
                # TODO: put back
                # possible_solutions=[
                #     "Run 'cfy local install-plugins {0}'".format(
                #         blueprint_path),
                #     "Run 'cfy bootstrap --install-plugins {0}'".format(
                #         blueprint_path)]
            )

    def test_bootstrap_no_validation_missing_plugin(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap --skip-validations {0}'.format(
            blueprint_path)

        self.invoke(
            command=command,
            err_str_segment='No module named tasks',
            exception=ImportError
            # TODO: put back
            # possible_solutions=[
            #     "Run 'cfy local install-plugins -p {0}'"
            #     .format(blueprint_path),
            #     "Run 'cfy bootstrap --install-plugins -p {0}'"
            #     .format(blueprint_path)
            # ]
        )

    def test_bootstrap_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is called before
        # calling bootstrap
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = 'cfy bootstrap --validate-only {0}'.format(blueprint_path)

        self.assert_method_called(
            command=command,
            module=bootstrap,
            function_name='validate_manager_deployment_size',
            kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_skip_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is not called
        # when the "--skip-validation" flag is used
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = ('cfy bootstrap --validate-only --skip-validations '
                   '{0}'.format(blueprint_path))

        self.assert_method_not_called(
            command=command,
            module=bootstrap,
            function_name='validate_manager_deployment_size')