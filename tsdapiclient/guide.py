
def print_guide():
    guide_text = """\

        TSD API client command-line tool: tacl
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        Usage: tacl --pnum <pnum> [OPTIONS]

        Options help: tacl --help

        Registration
        ~~~~~~~~~~~~

        Suppose you want to register for p11 in test:

        tacl --pnum p11 --signup --client_name '<name>' --email '<email>'
        # returns a client_id
        # get your confirmation token in email
        # save this in a config file:
        # client_id: '<id>'
        # confirmation_token: '<token>'

        tacl --pnum p11 --confirm --config <file>
        # returns a password
        # ask for your client to be verified
        # add this to the config file
        # pass: '<pw>'

        tacl --pnum p11 --getapikey --config <file>
        # returns an API key
        # save this in the config file
        # api_key: <key>

        Management
        ~~~~~~~~~~
        tacl --pnum p11 --delapikey '<key>' --config <file>
        tacl --pnum p11 --pwreset --config <file>

        Importing a file to TSD
        ~~~~~~~~~~~~~~~~~~~~~~~
        tacl --pnum p11 --importfile <filename> --config <file>

        For more info please visit:
        test.api.tsd.usit.no/v1/docs/tsd-api-integration.html

    """
    print guide_text
