########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import tempfile
from mock import MagicMock, patch

from .test_base import CliCommandTest
from cloudify_rest_client import deployments, tenants
from cloudify_cli.exceptions import SuppressedCloudifyCliError
from cloudify_rest_client.client import CLOUDIFY_TENANT_HEADER

DEFAULT_TENANT_NAME = 'tenant0'


class AgentsTests(CliCommandTest):
    def setUp(self):
        super(AgentsTests, self).setUp()
        self.use_manager()

    @staticmethod
    def create_tenants_and_deployments(num_of_tenants, num_of_deps,
                                       unique_deps_id=True):
        tenants_list = []
        deps = {}
        index = 0
        # create requested num of tenants
        for i in range(num_of_tenants):
            ten = tenants.Tenant({'name': 'tenant{0}'.format(i)})
            tenants_list.append(ten)
        # create requested num of deployments for each tenant
        for tenant in tenants_list:
            if not unique_deps_id:
                index = 0
            deps[tenant['name']] = []
            index = AgentsTests.create_deployments_in_tenant(
                deps[tenant['name']], num_of_deps, tenant, index)
        return tenants_list, deps

    @staticmethod
    def create_deployments_in_tenant(deps_list, num_of_deps, tenant,
                                     start_index):
        for i in range(num_of_deps):
            deps_list.append(deployments.Deployment({
                'id': 'dep{0}'.format(start_index),
                'tenant_name': tenant['name']}))
            start_index += 1
        return start_index

    def mock_client(self, tenants, deps, nodes, deps_get):
        def dep_list():
            tenant_name = self.client._client.headers.get(
                CLOUDIFY_TENANT_HEADER)
            if not tenant_name:
                tenant_name = DEFAULT_TENANT_NAME
            return deps[tenant_name]
        self.client.tenants.list = MagicMock(return_value=tenants)
        self.client.deployments.list = dep_list
        self.client.node_instances.list = MagicMock(return_value=nodes)
        self.client.deployments.get = deps_get

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_multiple_tenants_and_deployments(self,
                                                             worker_mock):
        """
        Expected behavior: install agents for all deployments in current
                           tenant.
        """
        tenants_list, deps = self.create_tenants_and_deployments(2, 3)
        deps_id_list = [d['id'] for d in deps['tenant0']]
        self.mock_client(tenants_list, deps, [], True)
        self.invoke('cfy agents install')
        call_args = list(worker_mock.call_args)
        self.assertEqual(call_args[0][0], deps_id_list)
        self.assertEqual(1, worker_mock.call_count)

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_specific_deployment(self, worker_mock):
        """
        Expected behavior: install agents for a specified deployment
                           in current tenant.
        """
        tenants_list, deps = self.create_tenants_and_deployments(2, 4)
        deps_id_list = ['dep3']

        def f(dep_id):
            return True
        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install dep3')
        call_args = list(worker_mock.call_args)
        self.assertEqual(call_args[0][0], deps_id_list)
        self.assertEqual(1, worker_mock.call_count)

    def test_agents_install_fail_dep_in_specific_ten(self):
        """
        Since the given deployment_ID is not installed in tenant2 we
        expect an exception to be raised.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)

        def f():
            raise Exception
        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install -t tenant2 dep2',
                    exception=SuppressedCloudifyCliError,
                    err_str_segment='')

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_specific_dep_in_specific_ten(self, worker_mock):
        """
        Expected behavior: install agents for specified deployment in
                           specified tenant.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)
        deps_id_list = ['dep6']

        def f(dep_id):
            return True
        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install -t tenant2 dep6')
        call_args = list(worker_mock.call_args)
        self.assertEqual(call_args[0][0], deps_id_list)
        self.assertEqual(1, worker_mock.call_count)

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_in_specific_ten(self, worker_mock):
        """
        Expected behavior: install agents for all
                           deployments in specified tenant.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)
        deps_id_list = [d['id'] for d in deps['tenant2']]
        self.mock_client(tenants_list, deps, [], True)
        self.invoke('cfy agents install -t tenant2')
        call_args = list(worker_mock.call_args)
        self.assertEqual(call_args[0][0], deps_id_list)
        self.assertEqual(1, worker_mock.call_count)

    def test_agents_install_fail_when_t_and_all_togther(self):
        """
         This tests makes sure that if both flags '-t' and '--all-tenants'
         are requested, the right error occurs.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)
        self.mock_client(tenants_list, deps, [], True)
        outcome = self.invoke(
            'cfy agents install -t tenant2 --all-tenants',
            exception=SystemExit,
            err_str_segment='2'  # Exit code
        )
        self.assertIn('Illegal usage: `tenant_name` is mutually exclusive with'
                      ' arguments: [all_tenants]', outcome.output)

    def test_agents_install_fail_when_t_all_and_dep_togther(self):
        """
         This tests makes sure that if both flags '-t' and '--all-tenants'
         are requested and a deployment is specified, an error occurs.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)
        self.mock_client(tenants_list, deps, [], True)
        outcome = self.invoke(
            'cfy agents install -t tenant2 --all-tenants dep2',
            exception=SystemExit,
            err_str_segment='2'  # Exit code
        )
        self.assertIn('Illegal usage: `tenant_name` is mutually exclusive with'
                      ' arguments: [all_tenants]', outcome.output)

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_all_tenants_multiple_deployments(self,
                                                             worker_mock):
        """
        Expected behavior: install agents for all deployments
                           across all tenants.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)
        self.mock_client(tenants_list, deps, [], True)
        self.invoke('cfy agents install --all-tenants')
        self.assertEqual(3, worker_mock.call_count)  # 1 call per tenant
        tenant0_deployments = [d['id'] for d in deps['tenant0']]
        tenant1_deployments = [d['id'] for d in deps['tenant1']]
        tenant2_deployments = [d['id'] for d in deps['tenant2']]
        self.assertEqual(
            tenant0_deployments in worker_mock.call_args_list[0][0], True)
        self.assertEqual(
            tenant1_deployments in worker_mock.call_args_list[1][0], True)
        self.assertEqual(
            tenant2_deployments in worker_mock.call_args_list[2][0], True)

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_all_tenants_specific_deployments(self,
                                                             worker_mock):
        """
        Expected behavior: install agents for a specific deployment
                           across all tenants.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3, False)

        def f(dep_id):
            return True
        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install --all-tenants dep2')
        self.assertEqual(3, worker_mock.call_count)  # 1 call per tenant
        self.assertEqual(
            ['dep2'] in worker_mock.call_args_list[0][0], True)
        self.assertEqual(
            ['dep2'] in worker_mock.call_args_list[1][0], True)
        self.assertEqual(
            ['dep2'] in worker_mock.call_args_list[2][0], True)

    def test_agents_install_fail_spec_dep_in_spec_ten(self):
        """
        Expected behavior: when an unrecognized deployment ID is given, we
                           expect an exception.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3)

        def f():
            raise Exception

        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install -t tenant2 dep11',
                    exception=SuppressedCloudifyCliError,
                    err_str_segment='')

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_all_tenants_missing_deployments(self,
                                                            worker_mock):
        """
        3 tenants are created: t0 has no deployments, t1 and t2 has 3
        deployments each.
        Expected behavior: install agents for all deployments in t1 and t2
                           (no exceptions expected!).
        """
        # Create 3 tenants, tenant0 - no deployments, t1 & t2 with 3
        # deployments each.
        tenants_list = []
        deps = {}
        for i in range(3):
            ten = tenants.Tenant({'name': 'tenant{0}'.format(i)})
            tenants_list.append(ten)
        t0 = tenants_list[0]
        t1 = tenants_list[1]
        t2 = tenants_list[2]
        # t0 with no deployments
        deps[t0['name']] = []
        # t1 with 3 deployments
        deps[t1['name']] = []
        index = AgentsTests.create_deployments_in_tenant(
            deps[t1['name']], 3, t1, 0)
        # t2 with 3 deployments
        deps[t2['name']] = []
        AgentsTests.create_deployments_in_tenant(
            deps[t2['name']], 3, t2, index)
        # assert worker is only called for the non-empty tenants
        self.mock_client(tenants_list, deps, [], True)
        self.invoke('cfy agents install --all-tenants')
        self.assertEqual(2, worker_mock.call_count)  # 1 call per tenant
        tenant1_deployments = [d['id'] for d in deps['tenant1']]
        tenant2_deployments = [d['id'] for d in deps['tenant2']]
        self.assertEqual(
            tenant1_deployments in worker_mock.call_args_list[0][0], True)
        self.assertEqual(
            tenant2_deployments in worker_mock.call_args_list[1][0], True)

    def test_agents_install_fail_all_tenants_no_deployments(self):
        """
        3 tenants are created: t0,t1,t2. All of them have no deployments,
        Expected behavior: Exception should be raised.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 0)

        def f(*args):
            raise Exception

        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install --all-tenants',
                    exception=SuppressedCloudifyCliError,
                    err_str_segment='')

    def test_agents_install_fail_all_tenants_specific_dep_not_found(self):
        """
        3 tenants are created: t0,t1,t2. In each one 3 deployments are created:
        'dep0', 'dep1', 'dep2'. The user tries to install agents for 'dep99'
        across all tenants ('dep99' doesn't exist in any of them).
        Expected behavior: Exception should be raised.
        """
        tenants_list, deps = self.create_tenants_and_deployments(3, 3, False)

        def f(*args):
            raise Exception

        self.mock_client(tenants_list, deps, [], f)
        self.invoke('cfy agents install --all-tenants dep99',
                    exception=SuppressedCloudifyCliError,
                    err_str_segment='')

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_with_manager_ip_and_ssl_cert(self, worker_mock):
        """
        Assert that the arguments `manager_ip` and `manager_certificate` are
        passed as expected
        """
        tenants_list, deps = self.create_tenants_and_deployments(2, 3)
        self.mock_client(tenants_list, deps, [], True)
        with tempfile.NamedTemporaryFile(delete=False)as f:
            cert_content = 'certificate content...'
            f.write(cert_content)
            f.close()
            self.invoke('cfy agents install --manager-ip 10.10.10.10'
                        ' --manager_certificate {0}'.format(f.name))
            call_args = list(worker_mock.call_args)
            self.assertEqual(call_args[0][5]['manager_ip'], '10.10.10.10')
            self.assertEqual(
                call_args[0][5]['manager_certificate'], cert_content)
            self.assertEqual(1, worker_mock.call_count)

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_with_manager_ip(self, worker_mock):
        """
        Assert that the argument `manager_ip` is passed as expected
        """
        tenants_list, deps = self.create_tenants_and_deployments(2, 3)
        self.mock_client(tenants_list, deps, [], True)
        self.invoke('cfy agents install --manager-ip 10.10.10.10')
        call_args = list(worker_mock.call_args)
        self.assertEqual(call_args[0][5]['manager_ip'], '10.10.10.10')
        self.assertEqual(1, worker_mock.call_count)

    @patch('cloudify_cli.commands.agents.run_worker')
    def test_agents_install_with_ssl_cert(self, worker_mock):
        """
        Assert that the argument `manager_certificate` is passed as expected
        """
        tenants_list, deps = self.create_tenants_and_deployments(2, 3)
        self.mock_client(tenants_list, deps, [], True)
        with tempfile.NamedTemporaryFile(delete=False)as f:
            cert_content = 'certificate content...'
            f.write(cert_content)
            f.close()
            self.invoke(
                'cfy agents install --manager_certificate {0}'.format(f.name))
            call_args = list(worker_mock.call_args)
            self.assertEqual(
                call_args[0][5]['manager_certificate'], cert_content)
            self.assertEqual(1, worker_mock.call_count)

    def test_agents_install_fail_ssl_cert_file_not_exists(self):
        self.invoke('cfy agents install --manager-ip 0.0.0.0'
                    ' --manager_certificate cert.txt',
                    exception=IOError,
                    err_str_segment="Manager's SSL certificate file does not"
                                    " exist in the following path:")

    def test_agents_install_fail_no_permission_to_ssl_cert_file(self):
        with tempfile.NamedTemporaryFile() as f:
            os.chmod(f.name, 000)
            command = 'cfy agents install --manager-ip 0.0.0.0' \
                      ' --manager_certificate {0}'.format(f.name)
            self.invoke(command, exception=IOError,
                        err_str_segment="Could not read Manager's SSL"
                                        " certificate from the given path:")
