
## Setting up automated data import

To import data to your TSD project(s) in an automated way, you firstly need to organise access for your machine(s) to the TSD API, by proividing an IP address/range. If your machine(s) are located on a Uninett network, then TSD's current security policy allows enabling access without issue. If not, then you will have to provide a description of how you secure your machine(s) and include it in the risk analysis of your project.

Given that this level of access is taken care of, and that you have obtained TSD credentials for your project(s), you can set up automated data import in the following way. Suppose you have installed the `tsd-api-client` and you have credentials for TSD projects pXX and pYY.

```bash
tacl --register
# API environment - test or prod > prod
# username > pXX-username
# password > ...
# otp > ...

tacl --register
# API environment - test or prod > prod
# username > pYY-username
# password > ...
# otp > ...

# confirm that you have your API keys for pXX and pYY
tacl --show-config

# then you can import data as such
tacl --pnum pXX --import myfile-for-pXX
tacl --pnum pYY --import myfile-for-pYY
```

The last two commands in this example, could therefore be included in a data pipeline (run via cron, for example) which generates the files which you want to import. It is, therefore, your responsibility to ensure that the correct file is imported to the correct project by providing the appropriate project number.
