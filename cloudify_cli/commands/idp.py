from cloudify_cli.cli import cfy


@cfy.group(name='identity')
@cfy.options.common_options
@cfy.assert_manager_active()
def idp():
    """Identity provider commands.
    """
    pass


@idp.command(name='get',
             short_help='Get the current identity provider for the manager.')
@cfy.pass_client()
@cfy.pass_logger
def get(client, logger):
    logger.info(client.idp.get())
