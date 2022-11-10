import click

from cloudify_cli.cli import cfy


@cfy.group(name='community')
@cfy.options.common_options
def community():
    """Commands specific for the Cloudify Community edition"""


@community.command(name='register',
                   short_help='Register a new Cloudify Community contact')
@click.option('-f', '--first-name',
              help='The contact\'s first name', required=True)
@click.option('-l', '--last-name',
              help='The contact\'s last name', required=True)
@click.option('-e', '--email',
              help='The contact\'s Email address', required=True)
@click.option('-p', '--phone',
              help='The contact\'s phone number', required=True)
@click.option('-a', '--accept-eula', is_flag=True,
              help='By using this flag you agree to the terms of the '
                   'End User License Agreement    '
                   '(https://cloudify.co/license-community)')
@cfy.pass_client()
@cfy.pass_logger
def register(first_name, last_name, email, phone, accept_eula, logger, client):
    """Register a new Cloudify Community contact.
    """
    customer_id = client.community_contacts.create(
        first_name,
        last_name,
        email,
        phone,
        accept_eula,
    )
    logger.info('Cloudify Community registered successfully. Customer ID:'
                ' "%s"', customer_id)
