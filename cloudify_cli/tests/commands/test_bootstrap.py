import os
import shutil
import filecmp

from mock import patch

from .. import cfy
from ... import env
from ... import common
from ...bootstrap import bootstrap
from .test_base import CliCommandTest
from ...commands.init import init_profile
from ...exceptions import CloudifyBootstrapError
from .constants import BLUEPRINTS_DIR, SAMPLE_BLUEPRINT_PATH

from dsl_parser.exceptions import MissingRequiredInputError


class BootstrapTest(CliCommandTest):

    def setUp(self):
        super(BootstrapTest, self).setUp()
        self.bootstrap_dir = os.path.join(
            env.PROFILES_DIR, 'test', 'bootstrap')
        self.manager_dir = os.path.join(self.bootstrap_dir, 'manager')
        os.makedirs(self.bootstrap_dir)

        cfy.invoke('init -r')
        init_profile(profile_name='test')

    def test_manager_deployment_dump(self, remove_deployment=True):
        manager1_original_dir = self._copy_manager1_dir_to_manager_dir()
        result = bootstrap.dump_manager_deployment()
        if remove_deployment:
            shutil.rmtree(self.manager_dir)
            self.assertTrue(
                bootstrap.read_manager_deployment_dump_if_needed(result))
        else:
            # simulating existing read manager deployment dump - .git folder
            # shouldn't appear there, so removing it alone
            shutil.rmtree(os.path.join(self.manager_dir, '.git'))
            self.assertFalse(
                bootstrap.read_manager_deployment_dump_if_needed(result))
        comparison = filecmp.dircmp(manager1_original_dir,
                                    self.manager_dir)
        self.assertIn('dir1', comparison.common)
        self.assertIn('dir2', comparison.common)
        self.assertIn('file1', comparison.common)
        self.assertIn('file2', comparison.common)
        self.assertEqual([], comparison.common_funny)
        self.assertEqual([], comparison.diff_files)
        self.assertEqual([], comparison.funny_files)
        self.assertEqual([], comparison.right_only)
        # .git folder is ignored when archiving manager deployment, and should
        # not appear in the new manager dir, only in the original one;
        # (however, since in the original dir it's named "dotgit" rather than
        # ".git", we check for that instead - yet neither should be in the
        # manager deployment either way)
        self.assertEqual(['dotgit'], comparison.left_only)

    def test_manager_deployment_dump_read_empty(self):
        self.assertFalse(
            bootstrap.read_manager_deployment_dump_if_needed(''))
        self.assertFalse(os.path.exists(self.manager_dir))

    def test_manager_deployment_dump_read_already_exists(self):
        self.test_manager_deployment_dump(remove_deployment=False)

    def test_validate_manager_deployment_size_success(self):
        # reusing the copying code, but actually there's no significance for
        # the directory being the "manager_dir" one; it's simply a directory
        # containing a "blueprint" (in this case, "file1")
        self._copy_manager1_dir_to_manager_dir()
        bootstrap.validate_manager_deployment_size(
            os.path.join(self.manager_dir, 'file1'))

    def test_validate_manager_deployment_size_failure(self):
        self._copy_manager1_dir_to_manager_dir()
        # setting max deployment size to be very small, so the validation fails
        with patch.object(bootstrap, 'MAX_MANAGER_DEPLOYMENT_SIZE', 10):
            self.assertRaisesRegexp(
                CloudifyBootstrapError,
                "The manager blueprint's folder is above the maximum allowed "
                "size when archived",
                bootstrap.validate_manager_deployment_size,
                blueprint_path=os.path.join(self.manager_dir, 'file1'))

    def test_validate_manager_deployment_size_ignore_gitfile_success(self):
        # this test checks that the validation of the manager deployment size
        # also ignores the .git folder
        self._copy_manager1_dir_to_manager_dir()
        # getting the archive's size when compressed with the .git folder
        # included in the archive
        with patch.object(bootstrap, 'blueprint_archive_filter_func',
                          lambda tarinfo: tarinfo):
            archive_obj = bootstrap.tar_manager_deployment()
            manager_dep_size = len(archive_obj.getvalue())
        # setting the limit to be smaller than the archive's size when
        # compressed with the .git folder included in the archive
        with patch.object(bootstrap, 'MAX_MANAGER_DEPLOYMENT_SIZE',
                          manager_dep_size - 1):
            # validation should pass as the limit is still bigger than
            # the size of the archive when the .git folder is excluded
            bootstrap.validate_manager_deployment_size(
                os.path.join(self.manager_dir, 'file1'))

    def _copy_manager1_dir_to_manager_dir(self):
        manager1_original_dir = os.path.join(
            os.path.dirname(__file__),
            '..', 'resources', 'storage', 'manager1')
        shutil.copytree(manager1_original_dir, self.manager_dir)

        # renaming git folder to be under its proper name
        os.rename(os.path.join(self.manager_dir, 'dotgit'),
                  os.path.join(self.manager_dir, '.git'))

        return manager1_original_dir

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

    def test_bootstrap_archive_default_filename(self):
        blueprint_path = '{0}/{1}'.format(
            BLUEPRINTS_DIR, 'simple_manager_blueprint.tar.gz')
        command = 'cfy bootstrap {0}'.format(blueprint_path)
        self.invoke(command, err_str_segment='Could not find `blueprint.yaml`')

    def test_bootstrap_archive_with_filename(self):
        blueprint_path = '{0}/{1}'.format(
            BLUEPRINTS_DIR, 'simple_manager_blueprint.tar.gz')
        command = 'cfy bootstrap {0} -n simple-manager-blueprint.yaml'\
            .format(blueprint_path)

        # Should pass the initialization of the blueprint, and only fail on
        # missing inputs
        self.invoke(
            command,
            err_str_segment='Required inputs',
            exception=MissingRequiredInputError
        )

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