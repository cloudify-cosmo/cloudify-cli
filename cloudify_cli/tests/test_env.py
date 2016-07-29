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
import json
import shutil
import logging
import tempfile
from cStringIO import StringIO
from itertools import chain, repeat, count

import mock
import yaml
import testtools
from mock import MagicMock, patch

from cloudify import logs
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.client import CloudifyClient

from .. import env
from .. import utils
from .. import inputs
from .. import logger
from ..logger import configure_loggers
from ..exceptions import CloudifyCliError
from ..colorful_event import ColorfulEvent
from ..exceptions import EventProcessingTimeoutError, \
    ExecutionTimeoutError
from ..execution_events_fetcher import ExecutionEventsFetcher, \
    wait_for_execution

from . import cfy
from .commands import utils as test_utils
from .resources.mocks.mock_list_response import MockListResponse


class TestCLIBase(testtools.TestCase):

    def tearDown(self):
        self._reset_verbosity_and_loggers()

    @patch('argparse.ArgumentParser.print_help')
    def test_help_shows_if_no_cli_arguments(self, print_help_mock):

        # SystemExit is raised when sys.exit is called
        self.assertRaises(SystemExit, cli_runner.run_cli, 'cfy')
        self.assertTrue(print_help_mock.called)

    def test_longest_longest_command_length(self):

        sample_dict = {'a': 'v1', 'ab': 'v2'}

        self.assertEqual(longest_command_length(sample_dict), 2)

    def test_verbosity(self):
        def test(flag, expected):
            self._reset_verbosity_and_loggers()
            with patch('cloudify_cli.commands.status'):
                cli_runner.run_cli('cfy status {0}'.format(flag))
            self.assertEqual(cli.verbosity_level, expected)
            self.assertEqual(logs.EVENT_VERBOSITY_LEVEL, expected)
            if expected >= cli.HIGH_VERBOSE:
                expected_logging_level = logging.DEBUG
            else:
                expected_logging_level = logging.INFO
            self.assertTrue(logger.all_loggers())
            for logger_name in logger.all_loggers():
                log = logging.getLogger(logger_name)
                self.assertEqual(log.level, expected_logging_level)

        test('', cli.NO_VERBOSE)
        test('-v', cli.LOW_VERBOSE)
        test('-vv', cli.MEDIUM_VERBOSE)
        test('-vvv', cli.HIGH_VERBOSE)
        test('--debug', cli.HIGH_VERBOSE)
        test('--debug -v', cli.HIGH_VERBOSE)

    def _reset_verbosity_and_loggers(self):
        cli.verbosity_level = cli.NO_VERBOSE
        logs.EVENT_VERBOSITY_LEVEL = cli.NO_VERBOSE
        logger.configure_loggers()


class CliEnvTests(testtools.TestCase):

    @classmethod
    def setUpClass(cls):
        env.CLOUDIFY_WORKDIR = '/tmp/.cloudify-test'
        env.CLOUDIFY_CONFIG_PATH = os.path.join(
            env.CLOUDIFY_WORKDIR, 'config.yaml')
        env.PROFILES_DIR = os.path.join(
            env.CLOUDIFY_WORKDIR, 'profiles')
        env.ACTIVE_PRO_FILE = os.path.join(
            env.CLOUDIFY_WORKDIR, 'active.profile')

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

    def _set_manager(self):
        env.update_profile_context(
            manager_ip='10.10.1.10',
            ssh_key_path='test',
            ssh_user='~/.my_key',
            ssh_port='22',
            rest_port='80',
            rest_protocol='http',
            provider_context='abc')

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
        self._set_manager()
        env.assert_manager_active()

    def test_assert_manager_is_active_not_init(self):
        # The environment is not even initialized
        # so it should return that a manager isn't active.
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        self.assertFalse(env.is_manager_active())

    def test_assert_local_is_active(self):
        self._set_manager()
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
        self._set_manager()
        self.assertTrue(env.is_manager_active())

    def test_get_profile_context(self):
        self._set_manager()
        context = env.get_profile_context()
        self.assertTrue(hasattr(context, 'get_manager_ip'))
        self.assertEqual(context.get_manager_ip(), '10.10.1.10')

    def test_get_profile_context_for_local(self):
        context = env.get_profile_context()
        self.assertIsNone(context)

    def test_get_context_path(self):
        self._set_manager()
        context_path = env.get_context_path()
        self.assertEqual(
            context_path,
            os.path.join(env.PROFILES_DIR, '10.10.1.10', 'context'))

    def test_fail_get_context_for_local_profile(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_context_path)
        self.assertEqual('Local profile does not contain context', str(ex))

    def test_fail_get_context_not_initalized(self):
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_context_path)
        self.assertEqual('Profile directory does not exist', str(ex))

    def test_get_profile_dir(self):
        self._set_manager()
        profile_dir = env.get_init_path()
        self.assertEqual(
            profile_dir,
            os.path.join(env.PROFILES_DIR, '10.10.1.10'))
        self.assertTrue(os.path.isdir(profile_dir))

    def test_get_non_existing_profile_dir(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.get_init_path)
        self.assertEqual('Profile directory does not exist', str(ex))

    def test_set_cfy_config(self):
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        os.makedirs(env.CLOUDIFY_WORKDIR)
        self.assertFalse(os.path.isfile(
            os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')))
        env.set_cfy_config()
        self.assertTrue(os.path.isfile(
            os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')))

    def test_set_empty_profile_context(self):
        env.set_profile_context(profile_name='10.10.1.10')
        context = env.get_profile_context('10.10.1.10')
        self.assertEqual(context.get_manager_ip(), None)

    def test_set_profile_context_with_settings(self):
        settings = env.ProfileContext()
        settings.set_manager_ip('10.10.1.10')
        env.set_profile_context(settings, profile_name='10.10.1.10')
        context = env.get_profile_context('10.10.1.10')
        self.assertEqual(context.get_manager_ip(), '10.10.1.10')

    def test_raise_uninitialized(self):
        ex = self.assertRaises(
            CloudifyCliError,
            env.raise_uninitialized)
        self.assertEqual('Cloudify environment is not initalized', str(ex))

    def test_update_profile_context(self):
        profile_data = dict(
            manager_ip='10.10.1.10',
            ssh_key_path='~/.my_key',
            ssh_user='test_user',
            ssh_port=24,
            rest_port=80,
            rest_protocol='http',
            provider_context='provider_context',
            bootstrap_state=True)
        env.update_profile_context(**profile_data)
        context = env.get_profile_context('10.10.1.10')
        self.assertEqual(context.get_manager_ip(), '10.10.1.10')
        self.assertEqual(context.get_manager_key(), '~/.my_key')
        self.assertEqual(context.get_manager_user(), 'test_user')
        self.assertEqual(context.get_manager_port(), 24)
        self.assertEqual(context.get_rest_port(), 80)
        self.assertEqual(context.get_rest_protocol(), 'http')
        self.assertEqual(context.get_provider_context(), 'provider_context')
        self.assertEqual(context.get_bootstrap_state(), True)

    def test_get_profile(self):
        profile_input = dict(
            manager_ip='10.10.1.10',
            ssh_key_path='~/.my_key',
            ssh_user='test_user',
            ssh_port=24,
            rest_port=80,
            rest_protocol='http',
            alias=None)
        env.update_profile_context(**profile_input)
        profile_output = env.get_profile('10.10.1.10')
        self.assertDictEqual(profile_output, profile_input)


class CliInputsTests(testtools.TestCase):

    # TODO: Test inputs_to_dict
    def test_parsing_input_as_string(self):

        self.assertEqual(inputs.plain_string_to_dict(""), {})
        self.assertEqual(inputs.plain_string_to_dict(" "), {})
        self.assertEqual(inputs.plain_string_to_dict(";"), {})
        self.assertEqual(inputs.plain_string_to_dict(" ; "), {})

        expected_dict = dict(my_key1="my_value1", my_key2="my_value2")

        parsed_dict = inputs.plain_string_to_dict(
            "my_key1=my_value1;my_key2=my_value2")
        self.assertEqual(parsed_dict, expected_dict)

        parsed_dict = inputs.plain_string_to_dict(
            " my_key1 = my_value1 ;my_key2=my_value2; ")
        self.assertEqual(parsed_dict, expected_dict)

        parsed_dict = inputs.plain_string_to_dict(
            " my_key1 = my_value1 ;my_key2=my_value2; ")
        self.assertEqual(parsed_dict, expected_dict)

        expected_dict = dict(my_key1="")
        parsed_dict = inputs.plain_string_to_dict(" my_key1=")
        self.assertEqual(parsed_dict, expected_dict)

        parsed_dict = inputs.plain_string_to_dict(" my_key1=;")
        self.assertEqual(parsed_dict, expected_dict)

        expected_dict = dict(my_key1="my_value1",
                             my_key2="my_value2,my_other_value2")
        parsed_dict = inputs.plain_string_to_dict(
            " my_key1 = my_value1 ;my_key2=my_value2,my_other_value2; ")
        self.assertEqual(parsed_dict, expected_dict)

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

    # TODO: Add several other input tests (e.g. wildcard, paths, etc)
    def test_inputs_to_dict_error_handling(self):
        configure_loggers()
        input_list = ["my_key1=my_value1;my_key2"]

        expected_err_msg = \
            ("Invalid input: {0}. It must represent a dictionary. "
             "Valid values can be one of:\n "
             "- A path to a YAML file\n "
             "- A path to a directory containing YAML files\n "
             "- A single quoted wildcard based path ")

        self.assertRaisesRegexp(
            CloudifyCliError,
            expected_err_msg.format(input_list[0]),
            inputs.inputs_to_dict,
            input_list)


class TestProgressBar(testtools.TestCase):
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


class TestLogger(testtools.TestCase):

    def test_text_events_logger(self):
        events_logger = logger.get_events_logger(json_output=False)
        events = [{'key': 'output'}, {'key': 'hide'}]

        def mock_create_message(event):
            return None if event['key'] == 'hide' else event['key']

        with test_utils.mock_logger('cloudify_cli.logger._lgr') as output:
            with patch('cloudify.logs.create_event_message_prefix',
                       mock_create_message):
                events_logger(events)
        self.assertEqual(events[0]['key'], output.getvalue())

    def test_json_events_logger(self):
        events_logger = logger.get_events_logger(json_output=True)
        events = [{'key': 'value1'}, {'key': 'value2'}]
        with test_utils.mock_stdout() as output:
            events_logger(events)
        self.assertEqual('{0}\n{1}\n'.format(json.dumps(events[0]),
                                             json.dumps(events[1])),
                         output.getvalue())


class ExecutionEventsFetcherTest(testtools.TestCase):

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

    def test_no_events(self):
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=2)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(0, events_count)

    def test_new_events_after_fetched_all(self):
        self.events = range(0, 10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id')
        events_fetcher.fetch_and_process_events()
        added_events = range(20, 25)
        self.events.extend(added_events)
        added_events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(added_events), added_events_count)

    def test_fetch_and_process_events_implicit_single_batch(self):
        self.events = range(0, 10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id',
                                                batch_size=100)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(self.events), events_count)

    def test_fetch_and_process_events_implicit_several_batches(self):
        event_log = {}
        self.batch_counter = 0
        self.events = range(0, 5)

        def test_events_logger(events):
            self.batch_counter += 1
            for index in range(0, len(events)):
                event_log[events[index]] = 'event {0} of {1} in batch {2}'.\
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
        event_log[self.events[0]] = 'event 1 of 2 in batch 1'
        event_log[self.events[1]] = 'event 2 of 2 in batch 1'
        event_log[self.events[2]] = 'event 1 of 2 in batch 2'
        event_log[self.events[3]] = 'event 2 of 2 in batch 2'
        event_log[self.events[4]] = 'event 1 of 1 in batch 3'
        # there shouldn't be any remaining events, verify that
        remaining_events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(0, remaining_events_count)

    def test_fetch_and_process_events_explicit_several_batches(self):
            total_events_count = 0
            self.events = range(0, 9)
            batch_size = 2
            events_fetcher = ExecutionEventsFetcher(self.client,
                                                    'execution_id',
                                                    batch_size=batch_size)
            for i in range(0, 4):
                events_batch_count = \
                    events_fetcher._fetch_and_process_events_batch()
                self.assertEqual(events_batch_count, batch_size)
                total_events_count += events_batch_count
            remaining_events_count = \
                events_fetcher._fetch_and_process_events_batch()
            self.assertEqual(remaining_events_count, 1)
            total_events_count += remaining_events_count
            self.assertEqual(len(self.events), total_events_count)

    def test_fetch_events_explicit_single_batch(self):
        self.events = range(0, 10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id',
                                                batch_size=100)
        batch_events = events_fetcher._fetch_events_batch()
        self.assertListEqual(self.events, batch_events)

    def test_fetch_events_explicit_several_batches(self):
        all_fetched_events = []
        self.events = range(0, 9)
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
        self.events = range(0, 2000000)
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=1)
        self.assertRaises(EventProcessingTimeoutError,
                          events_fetcher.fetch_and_process_events, timeout=2)

    def test_events_processing_progress(self):
        events_bulk1 = range(0, 5)
        self.events = events_bulk1
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=100)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk1), events_count)
        events_bulk2 = range(0, 10)
        self.events.extend(events_bulk2)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk2), events_count)
        events_bulk3 = range(0, 7)
        self.events.extend(events_bulk3)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk3), events_count)

    def test_wait_for_execution_timeout(self):
        self.events = [{'id': num} for num in range(0, 5)]
        mock_execution = self.client.executions.get('deployment_id')
        self.assertRaises(ExecutionTimeoutError, wait_for_execution,
                          self.client, mock_execution,
                          timeout=2)


class WaitForExecutionTests(testtools.TestCase):

    def setUp(self):
        super(WaitForExecutionTests, self).setUp()
        self.client = CloudifyClient()

        time_patcher = patch('cloudify_cli.execution_events_fetcher.time')
        self.time = time_patcher.start()
        self.addCleanup(time_patcher.stop)
        # prepare mock time.time() calls - return 0, 1, 2, 3...
        self.time.time.side_effect = count(0)

    def test_wait_for_log_after_execution_finishes(self):
        """wait_for_execution continues polling logs, after execution status
        is terminated
        """

        # prepare mock executions.get() calls - first return a status='started'
        # then continue returning status='terminated'
        executions = chain(
            [MagicMock(status=Execution.STARTED)],
            repeat(MagicMock(status=Execution.TERMINATED))
        )

        # prepare mock events.list() calls - first return empty events 100
        # times and only then return a 'workflow_succeeded' event
        events = chain(
            repeat(MockListResponse([], 0), 100),
            [MockListResponse([{'event_type': 'workflow_succeeded'}], 1)],
            repeat(MockListResponse([], 0))
        )

        self.client.executions.get = MagicMock(side_effect=executions)
        self.client.events.list = MagicMock(side_effect=events)

        mock_execution = MagicMock(status=Execution.STARTED)
        wait_for_execution(self.client, mock_execution, timeout=None)

        calls_count = len(self.client.events.list.mock_calls)
        self.assertEqual(calls_count, 101, """wait_for_execution didnt keep
            polling events after execution terminated (expected 101
            calls, got %d)""" % calls_count)

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
            [MockListResponse([{'event_type': 'workflow_succeeded'}], 1)],
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
class TestCLIConfig(testtools.TestCase):

    def setUp(self):
        super(TestCLIConfig, self).setUp()
        self.config_file_path = tempfile.mkstemp()[1]

        with open(self.config_file_path, 'w') as f:
            yaml.dump({'colors': True, 'auto_generate_ids': True}, f)

        patcher = mock.patch('cloudify_cli.env.CLOUDIFY_CONFIG_PATH',
                             self.config_file_path)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        super(TestCLIConfig, self).tearDown()
        os.remove(self.config_file_path)

    def test_colors_configuration(self):
        self.assertTrue(env.is_use_colors())

    def test_missing_colors_configuration(self):
        # when colors configuration is missing, default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertFalse(env.is_use_colors())

    def test_auto_generate_ids_configuration(self):
        self.assertTrue(env.is_auto_generate_ids())

    def test_missing_auto_generate_ids_configuration(self):
        # when auto_generate_ids configuration is missing,
        # default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertFalse(env.is_auto_generate_ids())


@mock.patch('cloudify_cli.env.is_initialized', lambda: True)
class TestCLIColors(testtools.TestCase):

    @mock.patch('cloudify_cli.logger._configure_from_file', mock.MagicMock())
    @mock.patch('cloudify_cli.env.is_use_colors', lambda: True)
    def test_configure_colors_for_events_and_logs(self):
        self.assertNotEquals(ColorfulEvent, logs.EVENT_CLASS)

        with mock.patch('colorama.init') as m:
            # calling logs configuration method
            logger.configure_loggers()
            # verifying that colorama was initialized and
            # ColorfulEvent is used for events and logs output
            self.assertEquals(ColorfulEvent, logs.EVENT_CLASS)
            m.assert_called_once_with(autoreset=True)


class TestCLIColorfulEvent(testtools.TestCase):

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
