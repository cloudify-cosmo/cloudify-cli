########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import sys
import mock
import json
import yaml
import shutil
import logging
import tarfile
import zipfile
import requests
import tempfile
from contextlib import closing
from cStringIO import StringIO
from mock import MagicMock, patch
from itertools import chain, repeat, count

from cloudify import logs

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import NotClusterMaster
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.client import DEFAULT_API_VERSION

import dsl_parser
from dsl_parser.constants import IMPORT_RESOLVER_KEY, \
    RESOLVER_IMPLEMENTATION_KEY, RESLOVER_PARAMETERS_KEY
from dsl_parser.import_resolver.default_import_resolver import \
    DefaultImportResolver

from .. import env
from .. import utils
from .. import inputs
from .. import logger
from .. import constants
from ..config import config
from .. import local as cli_local
from ..exceptions import CloudifyCliError
from ..colorful_event import ColorfulEvent
from ..exceptions import ExecutionTimeoutError
from ..exceptions import EventProcessingTimeoutError
from ..execution_events_fetcher import wait_for_execution
from ..execution_events_fetcher import ExecutionEventsFetcher

from . import cfy

from .commands.test_base import CliCommandTest
from .commands.mocks import mock_stdout, MockListResponse
from .commands.constants import BLUEPRINTS_DIR, SAMPLE_BLUEPRINT_PATH


class TestCLIBase(CliCommandTest):

    def setUp(self):
        super(TestCLIBase, self).setUp()
        cfy.invoke('init -r')

    def tearDown(self):
        super(TestCLIBase, self).tearDown()
        self._reset_verbosity_and_loggers()
        cfy.purge_dot_cloudify()

    def test_verbosity(self):
        def test(flag, expected):
            self._reset_verbosity_and_loggers()
            self.invoke('cfy profiles list {0}'.format(flag))
            self.assertEqual(logger.verbosity_level, expected)
            self.assertEqual(logs.EVENT_VERBOSITY_LEVEL, expected)
            if expected >= logger.HIGH_VERBOSE:
                expected_logging_level = logging.DEBUG
            else:
                expected_logging_level = logging.INFO
            for logger_name in ['cloudify.cli.main',
                                'cloudify.rest_client.http']:
                log = logging.getLogger(logger_name)
                self.assertEqual(log.level, expected_logging_level)

        test('', logger.NO_VERBOSE)
        test('-v', logger.LOW_VERBOSE)
        test('-vv', logger.MEDIUM_VERBOSE)
        test('-vvv', logger.HIGH_VERBOSE)

    def _reset_verbosity_and_loggers(self):
        logger.verbosity_level = logger.NO_VERBOSE
        logs.EVENT_VERBOSITY_LEVEL = logger.NO_VERBOSE
        logger.configure_loggers()


class CliEnvTests(CliCommandTest):

    def setUp(self):
        super(CliEnvTests, self).setUp()
        cfy.invoke('init -r')

    def tearDown(self):
        super(CliEnvTests, self).tearDown()
        cfy.purge_dot_cloudify()

    def _make_mock_profile(self, profile_name='10.10.1.10'):
        profile_path = os.path.join(env.PROFILES_DIR, profile_name)
        os.makedirs(profile_path)
        with open(os.path.join(profile_path, 'context'), 'w') as profile:
            profile.write('nothing_for_now')
        return profile_path

    def test_delete_profile(self):
        profile_path = self._make_mock_profile()
        env.delete_profile('10.10.1.10')
        self.assertFalse(os.path.isdir(profile_path))

    def test_delete_non_existing_profile(self):
        profile = 'non-existing-profile'
        ex = self.assertRaises(
            CloudifyCliError,
            env.delete_profile,
            profile_name=profile)
        self.assertEqual(
            'Profile {0} does not exist'.format(profile),
            str(ex))

    def test_profile_exists(self):
        self.assertFalse(env.is_profile_exists('non-existing-profile'))

    def test_profile_does_not_exist(self):
        self._make_mock_profile()
        self.assertTrue(env.is_profile_exists('10.10.1.10'))

    def test_assert_profile_exists(self):
        self._make_mock_profile()
        env.assert_profile_exists('10.10.1.10')

    def test_assert_non_existing_profile_exists(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.assert_profile_exists,
            profile_name='non-existing-profile')
        self.assertIn(
            'Profile {0} does not exist'.format('non-existing-profile'),
            str(ex))

    def test_set_active_profile(self):
        env.set_active_profile('10.10.1.10')
        with open(env.ACTIVE_PRO_FILE) as active_profile:
            self.assertEqual(active_profile.read(), '10.10.1.10')

    def test_get_active_profile(self):
        self.assertEqual(env.get_active_profile(), 'local')

    def test_assert_manager_not_active(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.assert_manager_active)
        self.assertIn(
            'This command is only available when using a manager',
            str(ex))

    def test_assert_manager_is_active(self):
        self.use_manager()
        env.assert_manager_active()

    def test_assert_manager_is_active_not_init(self):
        # The environment is not even initialized
        # so it should return that a manager isn't active.
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        self.assertFalse(env.is_manager_active())

    def test_assert_local_is_active(self):
        self.use_manager()
        ex = self.assertRaises(
            CloudifyCliError,
            env.assert_local_active)
        self.assertIn(
            'This command is not available when using a manager',
            str(ex))

    def test_assert_local_not_active(self):
        env.assert_local_active()

    def test_manager_not_active(self):
        self.assertFalse(env.is_manager_active())

    def test_manager_is_active(self):
        self.use_manager()
        self.assertTrue(env.is_manager_active())

    def test_use_manager_fails_without_profile(self):
        self.assertRaises(CloudifyCliError, self.use_manager, manager_ip=None)

    def test_get_profile_context(self):
        self.use_manager()
        context = env.get_profile_context()
        self.assertTrue(hasattr(context, 'manager_ip'))
        self.assertEqual(context.manager_ip, '10.10.1.10')

    def test_get_profile_context_for_local(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_profile_context)
        self.assertEqual('Local profile does not have context', str(ex))

    def test_get_context_path(self):
        profile = self.use_manager()
        context_path = env.get_context_path(profile.manager_ip)
        self.assertEqual(
            context_path,
            os.path.join(env.PROFILES_DIR, '10.10.1.10', 'context'))

    def test_fail_get_context_for_local_profile(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_profile_context)
        self.assertEqual('Local profile does not have context', str(ex))

    def test_get_context_path_suppress_error(self):
        profile = self.use_manager()
        context_path = env.get_context_path(profile.manager_ip,
                                            suppress_error=True)
        self.assertEqual(
            context_path,
            os.path.join(env.PROFILES_DIR, '10.10.1.10', 'context'))

    def test_fail_get_context_path_suppress_error(self):
        context_path = env.get_context_path('not.existing.profile',
                                            suppress_error=True)
        self.assertIs(None, context_path)

    def test_get_default_rest_cert_local_path(self):
        profile = self.use_manager()
        rest_cert_path = env.get_default_rest_cert_local_path()
        expected = os.path.join(env.get_profile_dir(profile.profile_name),
                                constants.PUBLIC_REST_CERT)
        self.assertEqual(expected, rest_cert_path)

    def test_get_default_rest_cert_local_path_no_profile(self):
        # if there's no profile, default to inside CFY_WORKDIR
        rest_cert_path = env.get_default_rest_cert_local_path()
        expected = os.path.join(env.CLOUDIFY_WORKDIR,
                                constants.PUBLIC_REST_CERT)
        self.assertEqual(expected, rest_cert_path)

    def test_fail_get_context_not_initialized(self):
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_context_path,
            'test'
        )
        self.assertEqual('Profile directory does not exist', str(ex))

    def test_get_profile_dir(self):
        self.use_manager()
        profile_dir = env.get_profile_dir()
        self.assertEqual(
            profile_dir,
            os.path.join(env.PROFILES_DIR, '10.10.1.10'))
        self.assertTrue(os.path.isdir(profile_dir))

    def test_get_non_existing_profile_dir(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_profile_dir)
        self.assertEqual('Profile directory does not exist', str(ex))

    def test_get_profile_dir_suppress_error(self):
        self.use_manager()
        profile_dir = env.get_profile_dir(suppress_error=True)
        self.assertEqual(
            profile_dir,
            os.path.join(env.PROFILES_DIR, '10.10.1.10'))
        self.assertTrue(os.path.isdir(profile_dir))

    def test_get_non_existing_profile_dir_suppress_error(self):
        profile_dir = env.get_profile_dir(suppress_error=True)
        self.assertIs(None, profile_dir)

    def test_set_empty_profile_context(self):
        manager_ip = '10.10.1.10'
        profile = env.ProfileContext()
        profile.manager_ip = manager_ip
        profile.save()

        context = env.get_profile_context(manager_ip)
        self.assertEqual(context.ssh_user, None)

    def test_set_profile_context_with_settings(self):
        manager_ip = '10.10.1.10'
        profile = env.ProfileContext()
        profile.manager_ip = manager_ip
        profile.save()

        context = env.get_profile_context(manager_ip)
        self.assertEqual(context.manager_ip, manager_ip)

    def test_raise_uninitialized(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.raise_uninitialized)
        self.assertEqual('Cloudify environment is not initialized', str(ex))

    def test_build_manager_host_string(self):
        self.assertRaises(CloudifyCliError, env.build_manager_host_string)

        self.assertTrue(
            env.build_manager_host_string('user'),
            'user@'
        )

        self.assertTrue(
            env.build_manager_host_string('user', 'ip'),
            'user@ip'
        )

        self.use_manager(ssh_user='host_string_test')

        self.assertTrue(
            env.build_manager_host_string(ip='ip'),
            'host_string_test@ip'
        )

        self.use_manager(ssh_user='host_string_test', manager_ip='test_ip')

        self.assertTrue(
            env.build_manager_host_string(),
            'host_string_test@test_ip'
        )


class CliInputsTests(CliCommandTest):

    def test_parsing_input_as_string(self):
        self._test_string_inputs(test_inputs_to_dict=False)

    def test_string_to_dict_error_handling(self):

        expected_err_msg = "Invalid input format: {0}, the expected " \
                           "format is: key1=value1;key2=value2"

        input_str = "my_key1"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict, input_str)

        input_str = "my_key1;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict, input_str)

        input_str = "my_key1=my_value1;myvalue2;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

        input_str = "my_key1=my_value1;my_key2=myvalue2;my_other_value2;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

        input_str = "my_key1=my_value1;my_key2=myvalue2;my_other_value2;"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

        input_str = "my_key1:my_value1;my_key2:my_value2"
        self.assertRaisesRegexp(CloudifyCliError,
                                expected_err_msg.format(input_str),
                                inputs.plain_string_to_dict,
                                input_str)

    def test_inputs_to_dict_strings(self):
        self._test_string_inputs(test_inputs_to_dict=True)

    def test_inputs_to_dict_directory(self):
        input_files_directory, expected_dict = \
            self._generate_multiple_input_files()

        self.assertEqual(
            inputs.inputs_to_dict([input_files_directory]),
            expected_dict
        )

    def test_inputs_to_dict_wildcard(self):
        input_files_directory, expected_dict = \
            self._generate_multiple_input_files()

        wildcard_string = '{0}/f*.yaml'.format(input_files_directory)
        self.assertEqual(
            inputs.inputs_to_dict([wildcard_string]),
            expected_dict
        )

    def _test_string_inputs(self, test_inputs_to_dict=False):
        self._test_multiple_inputs(
            ('', ' ', ';', ' ; '),
            {},
            test_inputs_to_dict
        )

        self._test_multiple_inputs(
            (
                "my_key1=my_value1;my_key2=my_value2",
                " my_key1 = my_value1 ;my_key2=my_value2; ",
                " my_key1 = my_value1 ;my_key2=my_value2; "
            ),
            dict(my_key1="my_value1", my_key2="my_value2"),
            test_inputs_to_dict
        )

        self._test_multiple_inputs(
            (" my_key1=", " my_key1=;"),
            dict(my_key1=""),
            test_inputs_to_dict
        )

        self._test_multiple_inputs(
            (" my_key1 = my_value1 ;my_key2=my_value2,my_other_value2; ", ),
            dict(my_key1="my_value1", my_key2="my_value2,my_other_value2"),
            test_inputs_to_dict
        )

    def _test_multiple_inputs(
            self,
            test_inputs,
            expected_dict,
            test_inputs_to_dict
    ):
        if test_inputs_to_dict:
            func_to_test = inputs.inputs_to_dict
        else:
            func_to_test = inputs.plain_string_to_dict

        for test_input in test_inputs:
            if test_inputs_to_dict:
                test_input = [test_input]
            self.assertEqual(func_to_test(test_input), expected_dict)

    def _generate_multiple_input_files(self):
        input_files_directory = tempfile.mkdtemp()
        with open(os.path.join(input_files_directory, 'f1.yaml'), 'w') as f:
            f.write('input1: new_input1\ninput2: new_input2')
        with open(os.path.join(input_files_directory, 'f2.yaml'), 'w') as f:
            f.write('input3: new_input3')
        expected_dict = {
            'input1': 'new_input1',
            'input2': 'new_input2',
            'input3': 'new_input3'
        }
        return input_files_directory, expected_dict


class TestProgressBar(CliCommandTest):
    def test_progress_bar_1(self):
        results = (
            '\r test |------------------------| 0.0%',
            '\r test |#####-------------------| 20.0%',
            '\r test |##########--------------| 40.0%',
            '\r test |##############----------| 60.0%',
            '\r test |###################-----| 80.0%',
            '\r test |########################| 100.0%\n')

        try:
            progress_func = utils.generate_progress_handler(
                file_path='test', max_bar_length=40)
            total_size = 5
            for iteration in xrange(6):
                sys.stdout = captured = StringIO()
                progress_func(iteration, total_size)
                self.assertEqual(captured.getvalue(), results[iteration])

        finally:
            sys.stdout = sys.__stdout__

    def test_progress_bar_2(self):
        results = (
            '\r test |----------------------------------| 0.0%',
            '\r test |----------------------------------| 0.38%',
            '\r test |#---------------------------------| 3.84%',
            '\r test |#############---------------------| 38.44%',
            '\r test |#############---------------------| 39.38%',
            '\r test |#####################-------------| 62.5%',
            '\r test |##################################| 100.0%\n')

        total_size = 32000
        increments = (0, 123, 1230, 12300, 12600, 20000, 32000)

        try:
            progress_func = utils.generate_progress_handler(
                file_path='test', max_bar_length=50)
            for iteration in xrange(7):
                sys.stdout = captured = StringIO()
                progress_func(increments[iteration], total_size)
                self.assertEqual(captured.getvalue(), results[iteration])

        finally:
            sys.stdout = sys.__stdout__


class TestLogger(CliCommandTest):

    def test_text_events_logger(self):
        events_logger = logger.get_events_logger(json_output=False)
        events = [{'key': 'output'}, {'key': 'hide'}]

        def mock_create_message(event):
            return None if event['key'] == 'hide' else event['key']

        with mock_stdout() as output:
            with patch('cloudify.logs.create_event_message_prefix',
                       mock_create_message):
                events_logger(events)
        self.assertEqual(events[0]['key'], output.getvalue().strip())

    def test_json_events_logger(self):
        events_logger = logger.get_events_logger(json_output=True)
        events = [{'key': 'value1'}, {'key': 'value2'}]
        with mock_stdout() as output:
            events_logger(events)
        self.assertEqual('{0}\n{1}\n'.format(json.dumps(events[0]),
                                             json.dumps(events[1])),
                         output.getvalue())


class ExecutionEventsFetcherTest(CliCommandTest):

    events = []

    def setUp(self):
        super(ExecutionEventsFetcherTest, self).setUp()
        self.client = CloudifyClient()
        self.client.executions.get = MagicMock()
        self.client.events.list = self._mock_list

    def _mock_list(self, include_logs=False, message=None,
                   from_datetime=None, to_datetime=None, _include=None,
                   sort='@timestamp', **kwargs):
        from_event = kwargs.get('_offset', 0)
        batch_size = kwargs.get('_size', 100)
        if from_event >= len(self.events):
            return MockListResponse([], len(self.events))
        until_event = min(from_event + batch_size, len(self.events))
        return MockListResponse(
            self.events[from_event:until_event], len(self.events))

    def _generate_events(self, count):
        """Generate mock events to use them for testing.

        :param count: How many events to generate
        :type count: int
        :return: Generated events
        :rtype: list(dict(str))

        """
        events = [
            {
                'deployment_id': '<deployment_id>',
                'execution_id': '<execution_id>',
                'node_name': '<node_name>',
                'operation': '<operation>',
                'workflow_id': '<workflow_id>',
                'node_instance_id': '<node_instance_id>',
                'message': '<message>',
                'error_causes': '<error_causes>',
            }
            for _ in xrange(count)
        ]
        return events

    def test_no_events(self):
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=2)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(0, events_count)

    def test_new_events_after_fetched_all(self):
        self.events = self._generate_events(10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id')
        events_fetcher.fetch_and_process_events()
        added_events = self._generate_events(5)
        self.events.extend(added_events)
        added_events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(added_events), added_events_count)

    def test_fetch_and_process_events_implicit_single_batch(self):
        self.events = self._generate_events(10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id',
                                                batch_size=100)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(self.events), events_count)

    def test_fetch_and_process_events_implicit_several_batches(self):
        event_log = {}
        self.batch_counter = 0
        self.events = self._generate_events(5)

        def test_events_logger(events):
            self.batch_counter += 1
            for index in range(0, len(events)):
                event_log[index] = 'event {0} of {1} in batch {2}'.\
                    format(index + 1, len(events), self.batch_counter)

        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=2)
        # internally this will get 10 events in 2 batches of 2 events each
        # and a last batch of 1 event
        events_count = events_fetcher.fetch_and_process_events(
            events_handler=test_events_logger)
        # assert all events were handled
        self.assertEqual(len(self.events), events_count)
        # assert batching was as expected (2*2, 1*1)
        event_log[0] = 'event 1 of 2 in batch 1'
        event_log[1] = 'event 2 of 2 in batch 1'
        event_log[2] = 'event 1 of 2 in batch 2'
        event_log[3] = 'event 2 of 2 in batch 2'
        event_log[4] = 'event 1 of 1 in batch 3'
        # there shouldn't be any remaining events, verify that
        remaining_events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(0, remaining_events_count)

    def test_fetch_and_process_events_explicit_several_batches(self):
            total_events_count = 0
            self.events = self._generate_events(9)
            batch_size = 2
            events_fetcher = ExecutionEventsFetcher(self.client,
                                                    'execution_id',
                                                    batch_size=batch_size)
            for i in range(0, 4):
                events_batch_count, _ = \
                    events_fetcher.fetch_and_process_events_batch()
                self.assertEqual(events_batch_count, batch_size)
                total_events_count += events_batch_count
            remaining_events_count, _ = \
                events_fetcher.fetch_and_process_events_batch()
            self.assertEqual(remaining_events_count, 1)
            total_events_count += remaining_events_count
            self.assertEqual(len(self.events), total_events_count)

    def test_fetch_events_explicit_single_batch(self):
        self.events = self._generate_events(10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id',
                                                batch_size=100)
        batch_events = events_fetcher._fetch_events_batch().items
        self.assertListEqual(self.events, batch_events)

    def test_fetch_events_explicit_several_batches(self):
        all_fetched_events = []
        self.events = self._generate_events(9)
        batch_size = 2
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=batch_size)

        for i in range(0, 4):
            events_batch = events_fetcher._fetch_events_batch()
            self.assertEqual(len(events_batch), batch_size)
            all_fetched_events.extend(events_batch)

        remaining_events_batch = events_fetcher._fetch_events_batch()
        self.assertEqual(len(remaining_events_batch), 1)
        all_fetched_events.extend(remaining_events_batch)
        self.assertEqual(self.events, all_fetched_events)

    def test_fetch_and_process_events_timeout(self):
        self.events = self._generate_events(2000000)
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=1)
        self.assertRaises(EventProcessingTimeoutError,
                          events_fetcher.fetch_and_process_events, timeout=2)

    def test_events_processing_progress(self):
        events_bulk1 = self._generate_events(5)
        self.events = events_bulk1
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=100)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk1), events_count)
        events_bulk2 = self._generate_events(10)
        self.events.extend(events_bulk2)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk2), events_count)
        events_bulk3 = self._generate_events(7)
        self.events.extend(events_bulk3)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk3), events_count)

    def test_wait_for_execution_timeout(self):
        self.events = self._generate_events(5)
        mock_execution = self.client.executions.get('deployment_id')
        self.assertRaises(ExecutionTimeoutError, wait_for_execution,
                          self.client, mock_execution,
                          timeout=2)


class WaitForExecutionTests(CliCommandTest):

    def setUp(self):
        super(WaitForExecutionTests, self).setUp()
        self.client = CloudifyClient()

        time_patcher = patch('cloudify_cli.execution_events_fetcher.time')
        self.time = time_patcher.start()
        self.addCleanup(time_patcher.stop)
        # prepare mock time.time() calls - return 0, 1, 2, 3...
        self.time.time.side_effect = count(0)

    def test_wait_for_log_after_execution_finishes(self):
        """wait_for_execution polls logs once, after execution status
        is terminated
        """

        # prepare mock executions.get() calls - first return a status='started'
        # then continue returning status='terminated'
        executions = chain(
            [MagicMock(status=Execution.STARTED)],
            repeat(MagicMock(status=Execution.TERMINATED))
        )

        # prepare mock events.list() calls - first return empty,
        # and only then return a 'workflow_succeeded' event
        events = chain(
            [
                MockListResponse([], 0),
                MockListResponse([{
                    'deployment_id': '<deployment_id>',
                    'execution_id': '<execution_id>',
                    'node_name': '<node_name>',
                    'operation': '<operation>',
                    'workflow_id': '<workflow_id>',
                    'node_instance_id': '<node_instance_id>',
                    'message': '<message>',
                    'error_causes': '<error_causes>',
                    'event_type': 'workflow_succeeded',
                }], 1)
            ],
            repeat(MockListResponse([], 0))
        )

        self.client.executions.get = MagicMock(side_effect=executions)
        self.client.events.list = MagicMock(side_effect=events)

        mock_execution = MagicMock(status=Execution.STARTED)
        wait_for_execution(self.client, mock_execution, timeout=None)

        calls_count = len(self.client.events.list.mock_calls)
        self.assertEqual(calls_count, 2, """wait_for_execution didnt poll
            events once after execution terminated (expected 2
            call, got %d)""" % calls_count)

    def test_wait_for_execution_after_log_succeeded(self):
        """wait_for_execution continues polling the execution status,
        even after it received a "workflow succeeded" log
        """

        # prepare mock executions.get() calls - return a status='started'
        # execution the first 100 times, and then return a 'terminated' one
        executions = chain(
            [MagicMock(status=Execution.STARTED)] * 100,
            repeat(MagicMock(status=Execution.TERMINATED))
        )

        # prepare mock events.get() calls - return a 'workflow_succeeded'
        # immediately, and there's no events after that
        events = chain(
            [MockListResponse([{
                'deployment_id': '<deployment_id>',
                'execution_id': '<execution_id>',
                'node_name': '<node_name>',
                'operation': '<operation>',
                'workflow_id': '<workflow_id>',
                'node_instance_id': '<node_instance_id>',
                'message': '<message>',
                'error_causes': '<error_causes>',
                'event_type': 'workflow_succeeded',
            }], 1)],
            repeat(MockListResponse([], 0))
        )

        self.client.executions.get = MagicMock(side_effect=executions)
        self.client.events.list = MagicMock(side_effect=events)

        mock_execution = MagicMock(status=Execution.STARTED)
        wait_for_execution(self.client, mock_execution, timeout=None)

        calls_count = len(self.client.executions.get.mock_calls)
        self.assertEqual(calls_count, 101, """wait_for_execution didnt keep
            polling the execution status after it received a workflow_succeeded
            event (expected 101 calls, got %d)""" % calls_count)


@mock.patch('cloudify_cli.env.is_initialized', lambda: True)
class TestCLIConfig(CliCommandTest):

    def setUp(self):
        super(TestCLIConfig, self).setUp()
        self.config_file_path = tempfile.mkstemp()[1]

        with open(self.config_file_path, 'w') as f:
            yaml.dump({'colors': True, 'auto_generate_ids': True}, f)

        patcher = mock.patch('cloudify_cli.config.config.CLOUDIFY_CONFIG_PATH',
                             self.config_file_path)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        super(TestCLIConfig, self).tearDown()
        os.remove(self.config_file_path)

    def test_colors_configuration(self):
        self.assertTrue(config.is_use_colors())

    def test_missing_colors_configuration(self):
        # when colors configuration is missing, default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertFalse(config.is_use_colors())

    def test_auto_generate_ids_configuration(self):
        self.assertTrue(config.is_auto_generate_ids())

    def test_missing_auto_generate_ids_configuration(self):
        # when auto_generate_ids configuration is missing,
        # default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertFalse(config.is_auto_generate_ids())


@mock.patch('cloudify_cli.env.is_initialized', lambda: True)
class TestCLIColors(CliCommandTest):
    def setUp(self):
        super(TestCLIColors, self).setUp()
        # We want to make sure that the event class is not a colorful event
        logs.EVENT_CLASS = "doesn't matter"

    @mock.patch('cloudify_cli.logger._configure_from_file', mock.MagicMock())
    @mock.patch('cloudify_cli.logger.is_use_colors', lambda: True)
    def test_configure_colors_for_events_and_logs(self):
        self.assertNotEquals(ColorfulEvent, logs.EVENT_CLASS)

        with mock.patch('colorama.init') as m:
            # calling logs configuration method
            logger.configure_loggers()
            # verifying that colorama was initialized and
            # ColorfulEvent is used for events and logs output
            self.assertEquals(ColorfulEvent, logs.EVENT_CLASS)
            m.assert_called_once_with(autoreset=True)


class TestCLIColorfulEvent(CliCommandTest):

    def test_simple_property_color(self):
        event = {
            'timestamp': 'mock-timestamp'
        }
        timestamp_out = ColorfulEvent(event).timestamp
        self.assertIn(ColorfulEvent.TIMESTAMP_COLOR, timestamp_out)
        self.assertIn(ColorfulEvent.RESET_COLOR, timestamp_out)

    def test_property_with_nested_color(self):
        operation = 'mock-operation'
        node_id = 'mock-node-id'

        event = {
            'context': {
                'operation': operation,
                'node_id': node_id
            }
        }
        operation_info_out = ColorfulEvent(event).operation_info

        # verifying output is in the format:
        # [operation.node_id]
        # where operation and node_id each has its own color,
        # and the brackets and dot use the color for "operation info"
        self.assertEquals(
            '{op_info_clr}[{node_id_clr}{node_id}{op_info_clr}.{op_clr}{op}'
            '{op_info_clr}]{reset_clr}'.format(
                op_info_clr=ColorfulEvent.OPERATION_INFO_COLOR,
                node_id_clr=ColorfulEvent.NODE_ID_COLOR,
                op_clr=ColorfulEvent.OPERATION_COLOR,
                reset_clr=ColorfulEvent.RESET_COLOR,
                node_id=node_id,
                op=operation),
            operation_info_out)


class CustomImportResolver(DefaultImportResolver):
    def __init__(self, param):
        if not param:
            raise ValueError('failed to initialize resolver')
        self.param = param


def update_config_file(resolver_configuration):
    config_path = config.CLOUDIFY_CONFIG_PATH
    with open(config_path, 'a') as f:
        yaml.dump(resolver_configuration, f)


def create_resolver_configuration(implementation=None, parameters=None):
    import_resolver_config = {IMPORT_RESOLVER_KEY: {}}
    if implementation:
        import_resolver_config[IMPORT_RESOLVER_KEY][
            RESOLVER_IMPLEMENTATION_KEY] = implementation
    if parameters:
        import_resolver_config[IMPORT_RESOLVER_KEY][
            RESLOVER_PARAMETERS_KEY] = parameters
    return import_resolver_config


class GetImportResolverTests(CliCommandTest):

    def setUp(self):
        super(GetImportResolverTests, self).setUp()
        cfy.invoke('cfy init -r')
        self.use_manager()

    def tearDown(self):
        super(GetImportResolverTests, self).tearDown()
        cfy.purge_dot_cloudify()

    def test_get_resolver(self):
        resolver_configuration = create_resolver_configuration(
            implementation='mock implementation',
            parameters='mock parameters')
        update_config_file(resolver_configuration=resolver_configuration)
        with mock.patch('dsl_parser.utils.create_import_resolver') as \
                mock_create_import_resolver:
            config.get_import_resolver()
            mock_create_import_resolver.assert_called_once_with(
                resolver_configuration[IMPORT_RESOLVER_KEY])

    def test_get_custom_resolver(self):
        parameters = {'param': 'custom-parameter'}
        custom_resolver_class_path = "%s:%s" % (
            CustomImportResolver.__module__, CustomImportResolver.__name__)
        import_resolver_config = create_resolver_configuration(
            implementation=custom_resolver_class_path, parameters=parameters)
        update_config_file(resolver_configuration=import_resolver_config)
        resolver = config.get_import_resolver()
        self.assertEqual(type(resolver), CustomImportResolver)
        self.assertEqual(resolver.param, 'custom-parameter')


class ImportResolverLocalUseTests(CliCommandTest):

    def setUp(self):
        super(ImportResolverLocalUseTests, self).setUp()
        self.use_manager()

    @mock.patch('cloudify_cli.config.config.get_import_resolver')
    def _test_using_import_resolver(self,
                                    command,
                                    blueprint_path,
                                    mocked_module,
                                    mock_get_resolver):
        cfy.invoke('cfy init -r')

        # create an import resolver
        parameters = {
            'rules':
                [{'rule1prefix': 'rule1replacement'}]
        }
        resolver = DefaultImportResolver(**parameters)
        # set the return value of mock_get_resolver -
        # this is the resolver we expect to be passed to
        # the parse_from_path method.
        mock_get_resolver.return_value = resolver

        # run the cli command and check that
        # parse_from_path was called with the expected resolver
        cli_command = 'cfy {0} {1}'.format(command, blueprint_path)
        kwargs = {
            'dsl_file_path': blueprint_path,
            'resolver': resolver,
            'validate_version': True
        }
        self.assert_method_called(
            cli_command, mocked_module, 'parse_from_path', kwargs=kwargs)
        cfy.purge_dot_cloudify()

    def test_validate_blueprint_uses_import_resolver(self):
        from cloudify_cli.commands import blueprints
        blueprint_path = '{0}/local/blueprint.yaml'.format(BLUEPRINTS_DIR)
        self._test_using_import_resolver(
            'blueprints validate', blueprint_path, blueprints)

    @mock.patch('cloudify_cli.local.get_storage', new=mock.MagicMock)
    @mock.patch('cloudify.workflows.local._prepare_nodes_and_instances')
    @mock.patch('dsl_parser.tasks.prepare_deployment_plan')
    def test_local_init(self, *_):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        self._test_using_import_resolver(
            'init', blueprint_path, dsl_parser.parser)


TRUST_ALL = 'non-empty-value'
CERT_PATH = 'path-to-certificate'


class TestGetRestClient(CliCommandTest):

    def setUp(self):
        super(TestGetRestClient, self).setUp()
        cfy.invoke('init -r')

        os.environ[constants.CLOUDIFY_USERNAME_ENV] = 'test_username'
        os.environ[constants.CLOUDIFY_PASSWORD_ENV] = 'test_password'
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = TRUST_ALL
        os.environ[constants.LOCAL_REST_CERT_FILE] = CERT_PATH
        with open(CERT_PATH, 'w') as cert:
            cert.write('cert content')

    def tearDown(self):
        super(TestGetRestClient, self).tearDown()
        os.remove(CERT_PATH)
        del os.environ[constants.CLOUDIFY_USERNAME_ENV]
        del os.environ[constants.CLOUDIFY_PASSWORD_ENV]
        del os.environ[constants.CLOUDIFY_SSL_TRUST_ALL]
        del os.environ[constants.LOCAL_REST_CERT_FILE]
        cfy.purge_dot_cloudify()

    def test_get_rest_client(self):
        client = self.original_utils_get_rest_client(
            rest_host='localhost',
            skip_version_check=True
        )
        self.assertIsNotNone(client._client.headers[
            constants.CLOUDIFY_AUTHENTICATION_HEADER])

    def test_get_secured_rest_client(self):
        rest_protocol = 'https'
        host = 'localhost'
        port = 443
        skip_version_check = True

        client = self.original_utils_get_rest_client(
            rest_host=host,
            rest_port=port,
            rest_protocol=rest_protocol,
            rest_cert=CERT_PATH,
            skip_version_check=skip_version_check
        )

        self.assertEqual(CERT_PATH, client._client.cert)
        self.assertTrue(client._client.trust_all)
        self.assertEqual('{0}://{1}:{2}/api/{3}'.format(
            rest_protocol, host, port, DEFAULT_API_VERSION),
            client._client.url)


class TestUtils(CliCommandTest):
    _TAR_TYPES_TO_FLAGS = {'tar': 'w', 'tar.gz': 'w:gz', 'tar.bz2': 'w:bz2'}

    def _create_archive_types(self):
        self.destination = dict()
        for arch_type in utils.SUPPORTED_ARCHIVE_TYPES:
            _, self.destination[arch_type] = tempfile.mkstemp()
            if arch_type == 'zip':
                with closing(
                        zipfile.ZipFile(self.destination[arch_type],
                                        'w')
                ) as zip_file:
                    zip_file.write(SAMPLE_BLUEPRINT_PATH, arcname='test')

            else:
                flag = TestUtils._TAR_TYPES_TO_FLAGS[arch_type]
                with closing(
                        tarfile.open(self.destination[arch_type], flag)
                ) as tar:
                    tar.add(SAMPLE_BLUEPRINT_PATH, arcname='test')

    def test_is_archive(self):
        self._create_archive_types()

        for arch_type in utils.SUPPORTED_ARCHIVE_TYPES:
            self.assertTrue(utils.is_archive(self.destination[arch_type]))

    def test_extract_archive(self):
        self._create_archive_types()

        with open(SAMPLE_BLUEPRINT_PATH, 'r') as f:
            test_file = f.read()

        for arch_type in utils.SUPPORTED_ARCHIVE_TYPES:
            temp_dest = utils.extract_archive(self.destination[arch_type])
            temp_dest = os.path.join(temp_dest, 'test')
            with open(temp_dest, 'r') as f:
                self.assertEqual(test_file, f.read())


class TestLocal(CliCommandTest):
    _BLUEPRINT_PATH = os.path.join(
        BLUEPRINTS_DIR,
        'helloworld',
        'simple_blueprint.yaml'
    )

    _DEFAULT_INPUTS = {
        'key1': 'default_val1',
        'key2': 'default_val2',
        'key3': 'default_val3'
    }

    def test_storage_dir(self):
        self.assertEqual(
            cli_local.storage_dir(),
            '/tmp/.cloudify-test/profiles/local'
        )

        self.assertEqual(
            cli_local.storage_dir('blueprint_id'),
            '/tmp/.cloudify-test/profiles/local/blueprint_id'
        )

    def test_initialize_blueprint_default_single_env(self):
        self._test_initialize_blueprint(
            name='local',
            custom_inputs={},
            expected_inputs=TestLocal._DEFAULT_INPUTS,
        )

    def test_initialize_blueprint_custom_single_env(self):

        custom_inputs = {
            'key1': 'val1',
            'key2': 'val2',
            'key3': 'val3'
        }

        self._test_initialize_blueprint(
            name='temp',
            custom_inputs=custom_inputs,
            expected_inputs=custom_inputs,
        )

    def test_initialize_blueprint_default_multi_env(self):
        """Initialize blueprint with multiple local blueprints enabled."""
        self._test_initialize_blueprint(
            name='test',
            custom_inputs={},
            expected_inputs=TestLocal._DEFAULT_INPUTS,
        )

    def _test_initialize_blueprint(self,
                                   name,
                                   custom_inputs,
                                   expected_inputs):
        environment = cli_local.initialize_blueprint(
            TestLocal._BLUEPRINT_PATH,
            name,
            inputs=custom_inputs
        )
        self.assertEqual(environment.name, name)
        self.assertEqual(environment.plan['inputs'], expected_inputs)
        self.assertIn('mock_workflow', environment.plan['workflows'])


class TestClusterRestClient(CliCommandTest):
    def _mock_get(self, master, followers, offline):
        """Mock cloudify-rest-client's requests.get for the cluster tests.

        When the rest client queries the master ip, a valid response is
        returned.
        When one of the ips in the followers set is queried, the
        'not cluster master' response is returned.
        When one of the ips in the offline set is queried, a connection
        error is raised.
        """
        def _mocked_get(request_url, *args, **kwargs):
            if master in request_url:
                response = mock.Mock()
                # any valid response; tests won't assert anything about its
                # actual contents
                response.status_code = 200
                response.json.return_value = {'items': [], 'metadata': {}}
                return response

            if any(follower in request_url for follower in followers):
                response = mock.Mock()
                response.status_code = 400
                response.json.return_value = {
                    'message': '',
                    'error_code': NotClusterMaster.ERROR_CODE
                }
                return response

            if any(node in request_url for node in offline):
                raise requests.exceptions.ConnectionError()

            self.fail('Unexpected url: {0}'.format(request_url))

        return mock.patch('cloudify_rest_client.client.requests.get',
                          side_effect=_mocked_get)

    def test_master_offline(self):
        env.profile.manager_ip = '127.0.0.1'
        env.profile.cluster = [
            {'manager_ip': '127.0.0.1'},
            {'manager_ip': '127.0.0.2'}
        ]
        c = env.CloudifyClusterClient(env.profile, host='127.0.0.1')

        with self._mock_get('127.0.0.2', [], ['127.0.0.1']) as mocked_get:
            response = c.blueprints.list()

        self.assertEqual([], list(response))
        self.assertEqual(2, len(mocked_get.mock_calls))
        self.assertEqual('127.0.0.2', env.profile.cluster[0]['manager_ip'])

    def test_master_changed(self):
        env.profile.manager_ip = '127.0.0.1'
        env.profile.cluster = [
            {'manager_ip': '127.0.0.1'},
            {'manager_ip': '127.0.0.2'},
            {'manager_ip': '127.0.0.3'},
            # only those two will be called (because .4 will be the new master)
            # for a total of 3 calls (original failed .1, then .5, then .4)
            {'manager_ip': '127.0.0.4'},
            {'manager_ip': '127.0.0.5'}
        ]
        master = '127.0.0.4'
        followers = ['127.0.0.1', '127.0.0.5']
        offline = ['127.0.0.2', '127.0.0.3']

        c = env.CloudifyClusterClient(env.profile, host='127.0.0.1')
        with self._mock_get(master, followers, offline) as mocked_get:
            response = c.blueprints.list()

        self.assertEqual([], list(response))
        self.assertEqual(4, len(mocked_get.mock_calls))
        self.assertEqual('127.0.0.4', env.profile.cluster[0]['manager_ip'])
