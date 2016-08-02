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
import filecmp
import logging
import tempfile
from cStringIO import StringIO
from itertools import chain, repeat, count

import mock
import yaml
from mock import MagicMock, patch

import cloudify
from cloudify import logs
from cloudify.workflows import local
from cloudify.exceptions import NonRecoverableError

from cloudify_rest_client.nodes import Node
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.client import DEFAULT_API_VERSION
from cloudify_rest_client.node_instances import NodeInstance

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
from ..bootstrap import bootstrap
from ..logger import configure_loggers
from ..exceptions import CloudifyCliError
from ..colorful_event import ColorfulEvent
from ..exceptions import ExecutionTimeoutError
from ..exceptions import CloudifyBootstrapError
from ..exceptions import EventProcessingTimeoutError
from ..execution_events_fetcher import wait_for_execution
from ..execution_events_fetcher import ExecutionEventsFetcher

from . import cfy

from .commands.constants import BLUEPRINTS_DIR
from .commands.test_base import CliCommandTest
from .commands.mocks import mock_logger, mock_stdout, MockListResponse


env.CLOUDIFY_WORKDIR = '/tmp/.cloudify-test'
env.CLOUDIFY_CONFIG_PATH = os.path.join(
    env.CLOUDIFY_WORKDIR, 'config.yaml')
env.PROFILES_DIR = os.path.join(
    env.CLOUDIFY_WORKDIR, 'profiles')
env.ACTIVE_PRO_FILE = os.path.join(
    env.CLOUDIFY_WORKDIR, 'active.profile')


class TestCLIBase(CliCommandTest):
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
        super(TestCLIBase, self).setUp()
        cfy.invoke('init -r')

    def tearDown(self):
        super(TestCLIBase, self).tearDown()
        self._reset_verbosity_and_loggers()
        cfy.purge_dot_cloudify()

    def test_verbosity(self):
        def test(flag, expected):
            self._reset_verbosity_and_loggers()
            with patch('cloudify_cli.commands.status'):
                cfy.invoke('cfy status {0}'.format(flag))
            self.assertEqual(logger.verbosity_level, expected)
            self.assertEqual(logs.EVENT_VERBOSITY_LEVEL, expected)
            if expected >= logger.HIGH_VERBOSE:
                expected_logging_level = logging.DEBUG
            else:
                expected_logging_level = logging.INFO
            self.assertTrue(logger.all_loggers())
            for logger_name in logger.all_loggers():
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
        self.use_manager(
            profile_name='10.10.1.10',
            key='~/.my_key',
            user='test',
            port='22',
            provider_context='abc',
            rest_port=80,
            rest_protocol='http')

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
        self.assertEqual('Cloudify environment is not initialized', str(ex))

    def test_update_profile_context(self):
        with env.update_profile_context('10.10.1.10') as context:
            context.set_manager_ip('10.10.1.10')
            context.set_rest_port('80')
            context.set_rest_protocol('http')
            context.set_provider_context('provider_context')
            context.set_manager_key('~/.my_key')
            context.set_manager_user('test_user')
            context.set_manager_port(24)
            context.set_bootstrap_state(True)
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
        with env.update_profile_context(manager_ip) as context:
            context.set_manager_ip(profile_input['manager_ip'])
            context.set_rest_port(profile_input['rest_port'])
            context.set_rest_protocol(profile_input['rest_protocol'])
            context.set_manager_key(profile_input['ssh_key_path'])
            context.set_manager_user(profile_input['ssh_user'])
            context.set_manager_port(profile_input['ssh_port'])
        env.update_profile_context(**profile_input)
        profile_output = env.get_profile('10.10.1.10')
        self.assertDictEqual(profile_output, profile_input)


class CliInputsTests(CliCommandTest):

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

        with mock_logger('cloudify_cli.logger._lgr') as output:
            with patch('cloudify.logs.create_event_message_prefix',
                       mock_create_message):
                events_logger(events)
        self.assertEqual(events[0]['key'], output.getvalue())

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
class TestCLIConfig(CliCommandTest):

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
class TestCLIColors(CliCommandTest):

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
    config_path = env.CLOUDIFY_CONFIG_PATH
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
            env.get_import_resolver()
            mock_create_import_resolver.assert_called_once_with(
                resolver_configuration[IMPORT_RESOLVER_KEY])

    def test_get_custom_resolver(self):
        parameters = {'param': 'custom-parameter'}
        custom_resolver_class_path = "%s:%s" % (
            CustomImportResolver.__module__, CustomImportResolver.__name__)
        import_resolver_config = create_resolver_configuration(
            implementation=custom_resolver_class_path, parameters=parameters)
        update_config_file(resolver_configuration=import_resolver_config)
        resolver = env.get_import_resolver()
        self.assertEqual(type(resolver), CustomImportResolver)
        self.assertEqual(resolver.param, 'custom-parameter')


class ImportResolverLocalUseTests(CliCommandTest):

    def setUp(self):
        super(ImportResolverLocalUseTests, self).setUp()
        self.use_manager()

    @mock.patch('cloudify_cli.env.get_import_resolver')
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

    @mock.patch.object(local._Environment, 'execute')
    @mock.patch.object(dsl_parser.tasks, 'prepare_deployment_plan')
    def test_bootstrap_uses_import_resolver_for_parsing(self, *_):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')

        old_validate_dep_size = bootstrap.validate_manager_deployment_size
        old_load_env = bootstrap.load_env
        old_init = cloudify.workflows.local.FileStorage.init
        old_get_nodes = cloudify.workflows.local.FileStorage.get_nodes
        old_get_node_instances = \
            cloudify.workflows.local.FileStorage.get_node_instances

        bootstrap.validate_manager_deployment_size =\
            lambda blueprint_path: None

        def mock_load_env(name):
            raise IOError('mock load env')
        bootstrap.load_env = mock_load_env

        def mock_init(self, name, plan, nodes, node_instances, blueprint_path,
                      provider_context):
            return 'mock init'
        bootstrap.local.FileStorage.init = mock_init

        def mock_get_nodes(self):
            return [
                Node({'id': 'mock_node',
                      'type_hierarchy': 'cloudify.nodes.CloudifyManager'})
            ]
        cloudify.workflows.local.FileStorage.get_nodes = mock_get_nodes

        def mock_get_node_instances(self):
            return [
                NodeInstance({'node_id': 'mock_node',
                              'runtime_properties': {
                                  'provider': 'mock_provider',
                                  'manager_ip': 'mock_manager_ip',
                                  'manager_user': 'mock_manager_user',
                                  'manager_key_path': 'mock_manager_key_path',
                                  'rest_port': 'mock_rest_port'}})
            ]
        cloudify.workflows.local.FileStorage.get_node_instances = \
            mock_get_node_instances

        try:
            self._test_using_import_resolver(
                'bootstrap', blueprint_path, dsl_parser.parser)
        finally:
            bootstrap.validate_manager_deployment_size = old_validate_dep_size
            bootstrap.load_env = old_load_env
            bootstrap.local.FileStorage.init = old_init
            cloudify.workflows.local.FileStorage.get_nodes = old_get_nodes
            cloudify.workflows.local.FileStorage.get_node_instances = \
                old_get_node_instances

    @mock.patch('cloudify_cli.common.storage', new=mock.MagicMock)
    @mock.patch('cloudify.workflows.local._prepare_nodes_and_instances')
    @mock.patch('dsl_parser.tasks.prepare_deployment_plan')
    def test_local_init(self, *_):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        self._test_using_import_resolver(
            'init', blueprint_path, dsl_parser.parser)


# TODO: Move to commands
class CliBootstrapUnitTests(CliCommandTest):
    """Unit tests for functions in bootstrap/bootstrap.py"""

    def setUp(self):
        # TODO: create an actual non-local profile here.
        self.bootstrap_dir = os.path.join(
            env.PROFILES_DIR, 'local', 'bootstrap')
        self.manager_dir = os.path.join(self.bootstrap_dir, 'manager')
        os.makedirs(self.bootstrap_dir)

        cfy.invoke('init -r')

    def tearDown(self):
        cfy.purge_dot_cloudify()

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

    def test_ssl_configuration_without_cert_path(self):
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: '',
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: ''
        }
        self.assertRaisesRegexp(
            NonRecoverableError,
            'SSL is enabled => certificate path must be provided',
            tasks._handle_ssl_configuration,
            configurations)

    def test_ssl_configuration_wrong_cert_path(self):
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: 'wrong-path',
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: ''
        }
        self.assertRaisesRegexp(
            NonRecoverableError,
            'The certificate path \[wrong-path\] does not exist',
            tasks._handle_ssl_configuration,
            configurations)

    def test_ssl_configuration_without_key_path(self):
        this_dir = os.path.dirname(os.path.dirname(__file__))
        cert_path = os.path.join(this_dir, 'cert.file')
        open(cert_path, 'a+').close()
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: cert_path,
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: ''
        }
        try:
            self.assertRaisesRegexp(
                NonRecoverableError,
                'SSL is enabled => private key path must be provided',
                tasks._handle_ssl_configuration,
                configurations)
        finally:
            os.remove(cert_path)

    def test_ssl_configuration_wrong_key_path(self):
        this_dir = os.path.dirname(os.path.dirname(__file__))
        cert_path = os.path.join(this_dir, 'cert.file')
        open(cert_path, 'a+').close()
        configurations = {
            constants.SSL_ENABLED_PROPERTY_NAME: True,
            constants.SSL_CERTIFICATE_PATH_PROPERTY_NAME: cert_path,
            constants.SSL_PRIVATE_KEY_PROPERTY_NAME: 'wrong-path'
        }
        try:
            self.assertRaisesRegexp(
                NonRecoverableError,
                'The private key path \[wrong-path\] does not exist',
                tasks._handle_ssl_configuration,
                configurations)
        finally:
            os.remove(cert_path)

    def test_get_install_agent_pkgs_cmd(self):
        agent_packages = {
            'agent_tar': 'agent.tar.gz',
            'agent_deb': 'agent.deb'
        }
        agents_pkg_path = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'

        command = self._get_install_agent_pkgs_cmd(
            agent_packages, agents_pkg_path, agents_dest_dir)

        self.assertIn('curl -O agent.tar.gz', command)
        self.assertIn('curl -O agent.deb', command)
        self.assertIn('dpkg -i {1}/*.deb && '
                      'mkdir -p {0}/agents && '
                      'mv {1}/agent.tar.gz {0}/agents/agent_tar.tar.gz'.format(
                          agents_dest_dir, agents_pkg_path), command)

    def test_get_install_agent_pkgs_cmd_tars_only(self):
        agent_packages = {
            'agent_tar1': 'agent1.tar.gz',
            'agent_tar2': 'agent2.tar.gz',
        }
        agents_pkg_path = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'

        command = self._get_install_agent_pkgs_cmd(
            agent_packages, agents_pkg_path, agents_dest_dir)

        self.assertIn('curl -O agent1.tar.gz', command)
        self.assertIn('curl -O agent2.tar.gz', command)
        self.assertIn('mv {1}/agent1.tar.gz {0}/agents/agent_tar1.tar.gz'
                      .format(agents_dest_dir, agents_pkg_path), command)
        self.assertIn('mv {1}/agent2.tar.gz {0}/agents/agent_tar2.tar.gz'
                      .format(agents_dest_dir, agents_pkg_path), command)

    def test_get_install_agent_pkgs_cmd_debs_only(self):
        agent_packages = {
            'agent_deb1': 'agent1.deb',
            'agent_deb2': 'agent2.deb',
        }
        agents_pkg_path = '/tmp/work_dir'
        agents_dest_dir = '/opt/manager/resources/packages'

        command = self._get_install_agent_pkgs_cmd(
            agent_packages, agents_pkg_path, agents_dest_dir)

        self.assertIn('curl -O agent1.deb', command)
        self.assertIn('curl -O agent2.deb', command)
        self.assertIn('dpkg -i {1}/*.deb'.format(
            agents_dest_dir, agents_pkg_path), command)

    def _copy_manager1_dir_to_manager_dir(self):
        manager1_original_dir = os.path.join(
            os.path.dirname(__file__),
            'resources', 'storage', 'manager1')
        shutil.copytree(manager1_original_dir, self.manager_dir)

        # renaming git folder to be under its proper name
        os.rename(os.path.join(self.manager_dir, 'dotgit'),
                  os.path.join(self.manager_dir, '.git'))

        return manager1_original_dir


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

    def tearDown(self):
        super(TestGetRestClient, self).tearDown()
        del os.environ[constants.CLOUDIFY_USERNAME_ENV]
        del os.environ[constants.CLOUDIFY_PASSWORD_ENV]
        del os.environ[constants.CLOUDIFY_SSL_TRUST_ALL]
        del os.environ[constants.LOCAL_REST_CERT_FILE]

        cfy.purge_dot_cloudify()

    def test_get_rest_client(self):
        client = env.get_rest_client(rest_host='localhost',
                                     skip_version_check=True)
        self.assertIsNotNone(client._client.headers[
            constants.CLOUDIFY_AUTHENTICATION_HEADER])

    def test_get_secured_rest_client(self):
        rest_protocol = 'https'
        host = 'localhost'
        port = 443
        skip_version_check = True

        client = env.get_rest_client(
            rest_host=host, rest_port=port, rest_protocol=rest_protocol,
            skip_version_check=skip_version_check)

        self.assertEqual(CERT_PATH, client._client.cert)
        self.assertTrue(client._client.trust_all)
        self.assertEqual('{0}://{1}:{2}/api/{3}'.format(
            rest_protocol, host, port, DEFAULT_API_VERSION),
            client._client.url)
