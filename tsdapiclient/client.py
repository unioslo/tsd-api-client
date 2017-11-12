
"""Command-line interface to administrative tasks in API."""

import click

def signup(pnum, client_name, email):
    pass

def confirm(pnum, client_id, confirmation_token):
    pass

def get_api_key(pnum, client_id, password):
    pass

def del_api_key(pnum, client_id, password, api_key):
    pass

def pw_reset(pnum, client_id, password):
    pass

def print_guide():
    guide_text = """\

        TSD API command line tool help
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        Usage: tac --pnum <pnum> [OPTIONS]

        Options:
            --env           test (default) or prod.
            --pnum          project number, e.g. p143.
            --signup        register your client.
            --confirm       confirm your client.
            --getapikey     get a persistent API key.
            --delapikey     revoke an API key.
            --pwreset       reset your password.
            --guide         print this guide.

        Registration guide
        ~~~~~~~~~~~~~~~~~~

        Suppose you want to register for p11 in test:

        tac --pnum p11 --signup --client_name <name> --email <email>
        # returns a client_id
        # get your confirmation token in email

        tac --pnum p11 --confirm --client_id <id> --confirmation_token <token>
        # returns a password
        # ask for your client to be verified

        tac --pnum p11 --getapikey --client_id <id> --password <pw>
        # returns an API key

        For more info please visit:
        test.api.tsd.usit.no/v1/docs/tsd-api-integration.html

    """
    print guide_text


@click.command()
@click.option('--env', default='test', help='which environment you want to interact with')
@click.option('--pnum', default=None, help='project numbers')
@click.option('--signup', is_flag=True, default=False, help='register an API client')
@click.option('--confirm', is_flag=True, default=False, help='confirm your details')
@click.option('--getapikey', is_flag=True, default=False, help='get a persistent API key')
@click.option('--delapikey', is_flag=True, default=False, help='revoke an API key')
@click.option('--pwreset', is_flag=True, default=False, help='reset your password')
@click.option('--guide', is_flag=True, default=False, help='print help text')
@click.option('--client_name', default=None, help='your client\'s name')
@click.option('--email', default=None, help='your email address')
@click.option('--client_id', default=None, help='your client id')
@click.option('--confirmation_token', default=None, help='your confirmation token')
@click.option('--password', default=None, help='your API client password')
@click.option('--api_key', default=None, help='your persistent API key')
def main(env, pnum, signup, confirm, getapikey, delapikey, pwreset, guide,
         client_name, email, client_id, confirmation_token, password,
         api_key):
    if guide:
        print_guide()
    return


if __name__ == '__main__':
    main()
