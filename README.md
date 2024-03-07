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
tacl --guide config
tacl --guide uploads
tacl --guide downloads
tacl --guide sync
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

First build the container from this repo:

```console
git clone https://github.com/unioslo/tsd-api-client.git
cd tsd-api-client
podman build -t tsd-api-client .
```

Then run it, mounting a volume for saving configuration to `/config` in the
container:

```console
podman run --rm -ti -v $HOME/.config/tacl:/config/tacl tsd-api-client --register
```

Likely you will also want to bind mount in another volume to upload data from
or write exported data to.
