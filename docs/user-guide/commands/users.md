# `users` commands

Create, update and delete the local MuseFlow user. These commands never use `MUSEFLOW_CLI_DEFAULT_EMAIL`: they always
name the account. All other commands identify the user with `--email`, or with `MUSEFLOW_CLI_DEFAULT_EMAIL` when it
is omitted.

## `users create`

Creates a user account.

```bash
museflow users create --email <email> [--password <password>]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--password` | prompted | User password. When omitted, it is prompted for with hidden input and a confirmation. |

**Example**

```bash
museflow users create --email user@example.com
```

**Output.** `User user@example.com created successfully!`. If the email is already registered, the command
exits with an error.

!!! tip
    Prefer the interactive prompt over `--password`: a password passed as an argument ends up in the shell
    history.

## `users update`

Changes the email and/or the password of an existing user.

```bash
museflow users update <user_id> [--email <new_email>] [--password <new_password>]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `user_id` | required | ID (UUID) of the user to update. |
| `--email` | unchanged | New email address. |
| `--password` | unchanged | New password. |

**Example**

```bash
museflow users update 3f2b8c1e-0000-4000-8000-000000000000 --email new@example.com
```

## `users delete`

Deletes a user account and all of its data: tracks, playlists, taste profiles, blacklist, provider tokens and LLM
usage. Asks for confirmation first.

```bash
museflow users delete --email <email> [--yes]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--yes`, `-y` | off | Skip the confirmation prompt. |

**Example**

```bash
museflow users delete --email user@example.com
```

**Output.** `User user@example.com deleted.`. If the email is unknown, the command exits with an error.

!!! warning
    This cannot be undone, and it only touches the local database: the playlists already on Spotify stay there, and
    MuseFlow stays authorized on the Spotify account until access is removed from the Spotify settings.

## Next step

Connect the user to Spotify with [`provider connect`](provider.md#provider-connect).
