# `users` commands

Create and update the local MuseFlow user. All other commands identify the user with `--email`.

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

## Next step

Connect the user to Spotify with [`spotify connect`](spotify.md#spotify-connect).
