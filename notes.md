maybe
-----
https://stackoverflow.com/questions/44185486/generate-and-stream-compressed-file-with-flask
https://stackoverflow.com/questions/10405210/create-and-stream-a-large-archive-without-storing-it-in-memory-or-on-disk
https://github.com/gourneau/SpiderOak-zipstream
probably
--------
https://bitbucket.usit.uio.no/projects/TSD/repos/tsd-prace-instruments/browse

tar cf - dir | gpg --encrypt -r <recipient> -o test.gz.gpg
do not compress and then encrypt
https://blog.appcanary.com/2016/encrypt-or-compress.html
bla.tar.gpg.gz

# and the on the API: decode pw header, gpg decrypt it
# openssl enc -aes-256-cbc -a -d -pass file:<( echo $PW ) |
# tar -C t -xvf -

https://security.stackexchange.com/questions/29106/openssl-recover-key-and-iv-by-passphrase
https://crypto.stackexchange.com/questions/34884/length-of-encryption-password-aes-256-cbc
