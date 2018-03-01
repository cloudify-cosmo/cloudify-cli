from mock import MagicMock

from .test_base import CliCommandTest


class TokensTest(CliCommandTest):

    def setUp(self):
        super(TokensTest, self).setUp()
        self.client.tokens.get = MagicMock()
        self.use_manager()

    def test_tokens_command(self):
        self.use_manager()
        self.invoke('cfy tokens get')

    def test_tokens_wrong_argument(self):
        outcome = self.invoke('cfy tokens get -t',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Error: no such option: -t', outcome.output)
