from mock import Mock

from cloudify_rest_client.tokens import Token

from cloudify_cli.tests.commands.test_base import CliCommandTest
from cloudify_cli.tests.commands.mocks import MockListResponse


TOKEN1 = {'id': 'abc123', 'role': 'someroleorother', 'username': 'user1',
          'description': 'areallyusefultoken',
          'value': 'ctok-something-willbehiddenbyserver'}
TOKEN2 = {'id': 'xyz4576', 'role': 'adifferentrole', 'username': 'user2',
          'description': 'trokenboken', 'last_used': 'A Long Time Ago',
          'expiration_date': 'Very very soon',
          'value': 'ctok-other-alsohiddenvalue'}


class TokensTest(CliCommandTest):

    def setUp(self):
        super(TokensTest, self).setUp()
        self.client.tokens.get = Mock()
        self.client.tokens.list = Mock()
        self.client.tokens.delete = Mock()
        self.client.tokens.create = Mock()
        self.use_manager()

    def test_old_command_error(self):
        # Make sure we give a helpful error on the old style token retrieval
        self.invoke('cfy tokens get', err_str_segment='`cfy tokens create`')

    def _check_output(self, tokens, output, expect_users=False,
                      expect_count=True, expect_value=False):
        for token in tokens:
            for key in ['id', 'role', 'description',
                        'expiration_date', 'last_used']:
                if token.get(key):
                    assert token.get(key) in output

            if expect_users:
                assert token['username'] in output
            else:
                assert token['username'] not in output

            if expect_value:
                assert token['value'] in output
            else:
                assert token['value'] not in output
        if expect_count:
            assert '{0} of {0}'.format(len(tokens)) in output

    def test_get_token(self):
        token = Token(TOKEN1)
        self.client.tokens.get.return_value = token
        output = self.invoke('cfy tokens get {}'.format(token['id'])).output
        self.client.tokens.get.assert_called_once_with(token['id'])
        self._check_output([token], output, expect_count=False)

    def test_delete_token(self):
        token_id = 'killthistoken'
        self.invoke('cfy tokens delete {}'.format(token_id))
        self.client.tokens.delete.assert_called_once_with(token_id)

    def test_list_single_user(self):
        tokens = MockListResponse(items=[Token(TOKEN1)])
        tokens.metadata.pagination.total = len(tokens)
        self.client.tokens.list.return_value = tokens
        output = self.invoke('cfy tokens list').output
        self.client.tokens.list.assert_called_once_with()
        self._check_output(tokens.items, output)

    def test_list_multi_user(self):
        tokens = MockListResponse(items=[Token(TOKEN1), Token(TOKEN2)])
        tokens.metadata.pagination.total = len(tokens)
        self.client.tokens.list.return_value = tokens
        output = self.invoke('cfy tokens list').output
        self.client.tokens.list.assert_called_once_with()
        self._check_output(tokens.items, output, expect_users=True)

    def test_create_token(self):
        token = Token(TOKEN1)
        self.client.tokens.create.return_value = token
        output = self.invoke('cfy tokens create').output
        self.client.tokens.create.assert_called_once_with(
            expiration=None, description=None,
        )
        self._check_output([token], output, expect_value=True,
                           expect_count=False)

    def test_create_token_extras(self):
        token = Token(TOKEN1)
        self.client.tokens.create.return_value = token
        self.invoke('cfy tokens create '
                    '--expiry something '
                    '--description descr')
        self.client.tokens.create.assert_called_once_with(
            expiration='something', description='descr',
        )
