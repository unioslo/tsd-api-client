## TSD API Client

Transport files and directories, no limits on size or amount, resumable by default, synchronise if needed.

## Install

```bash
pip3 install tsd-api-client
pip3 install tsd-api-client --upgrade # to get the latest version
```

## tacl

Get started with `tacl`:

```bash
tacl --guide topics # to see all guides available
tacl --help
```

Set up shell completion:

```sh
# for Bash, in ~/.bashrc:
eval "$(_TACL_COMPLETE=source_bash tacl)"

# for Zsh, in ~/.zshrc:
eval "$(_TACL_COMPLETE=source_zsh tacl)"

# for Fish, in ~/.config/fish/completions/tacl.fish
eval (env _TACL_COMPLETE=source_fish tacl)
```

## Running in a container

You can run the container like this:

```console
$ podman run --rm -ti ghcr.io/unioslo/tsd-api-client
tacl --help, for basic help
tacl --guide topics, for extended help
```

The container entrypoint is `tacl`, meaning you can pass runtime parameters to
the `ghcr.io/unioslo/tsd-api-client` image as if you were running `tacl` on your
host.

```console
$ podman run --rm -ti ghcr.io/unioslo/tsd-api-client --version
tacl v3.5.13
- OS/Arch: Linux/aarch64
- Python: 3.12.2
```

You should bind mount a writable volume to `/config/tacl` in the container, so
that your configuration and session data persists between separate invocation.

```console
$ podman run --rm -ti -v $HOME/.config/tacl:/config/tacl ghcr.io/unioslo/tsd-api-client --register
Choose the API environment by typing one of the following numbers:
1 - for normal production usage
2 - for use over fx03 network
3 - for testing
4 - for Educloud normal production usage
5 - for Educloud testing
 >
```

Likely you will also want to bind mount in another volume to upload data from
or write exported data to.

```console
$ podman run --rm -ti \
    -v $HOME/.config/tacl:/config/tacl \
    -v $PWD:/data \
    ghcr.io/unioslo/tsd-api-client
    p11 --upload /data/README.md
/data/README.md ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
