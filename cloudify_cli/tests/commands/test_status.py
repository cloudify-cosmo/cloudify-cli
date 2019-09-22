from mock import MagicMock, patch

from .test_base import CliCommandTest

from cloudify_rest_client.exceptions import UserUnauthorizedError


class StatusTest(CliCommandTest):

    def setUp(self):
        super(StatusTest, self).setUp()
        self.client.manager.get_status = MagicMock()
        self.client.maintenance_mode.status = MagicMock()

    def test_status_command(self):
        self.use_manager()
        self.invoke('cfy status')

    def test_status_no_manager_server_defined(self):
        # Running a command which requires a target manager server without
        # first calling "cfy profiles use" or providing a target server
        # explicitly
        self.invoke(
            'cfy status',
            'This command is only available when using a manager'
        )

    def test_status_by_unauthorized_user(self):
        self.use_manager()
        with patch.object(self.client.manager, 'get_status') as mock:
            mock.side_effect = UserUnauthorizedError('Unauthorized user')
            outcome = self.invoke('cfy status')
            self.assertIn('User is unauthorized', outcome.logs)

    def test_status_result_services(self):
        self.use_manager()

        status_result = {
            "status": "OK",
            "services": {
                "name1": {
                    "status": "state1",
                    "extra_info": {
                        "systemd": {}
                    },
                    "isExternal": False
                },
                "name2": {
                    "status": "state2",
                    "isExternal": True
                }
            }
        }

        self.client.manager.get_status = MagicMock(return_value=status_result)

        outcome = self.invoke('cfy status')
        outcome = [o.strip() for o in outcome.output.split('\n')]

        expected_outputs = [
            '| name1                          | state1 |',
            '| name2                          | state2 |',
        ]

        for output in expected_outputs:
            self.assertIn(output, outcome)
