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
