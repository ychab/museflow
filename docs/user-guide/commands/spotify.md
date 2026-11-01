# `spotify` commands

Link a user to a Spotify account and inspect the link.

## `spotify connect`

Connects a user account to Spotify through OAuth. A browser window opens on the Spotify consent page; the
command then polls until the authorisation has been completed.

```bash
museflow spotify connect --email <email> [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--timeout` | `60.0` | Seconds to wait for authentication (minimum 10). |
| `--poll-interval` | `2.0` | Seconds between status checks (minimum 0.5). |

**Prerequisites**

- The user exists ([`users create`](users.md#users-create)).
- The API server is running and reachable at the redirect URI configured in the `SPOTIFY_REDIRECT_URI`
  setting. It receives the Spotify callback.

**Example**

```bash
museflow spotify connect --email user@example.com --timeout 120
```

**Output.** The authorisation URL is printed and opened in the browser, then dots are printed while waiting,
and finally `Authentication successful!`. On timeout the command exits with an error asking whether the browser
was opened and the consent accepted. If the browser cannot be opened automatically, copy the printed URL.

!!! note
    A connected account is needed by the commands that talk to Spotify: [`playlist discover`](playlist.md#playlist-discover),
    [`playlist history`](playlist.md#playlist-history), playback with `--play` in [`rate`](rate.md), and
    `playlist delete --include-remote`.

## `spotify info`

Prints the stored Spotify OAuth token of a user, for diagnostics.

```bash
museflow spotify info --email <email>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--show-tokens` | off | Print the access and refresh tokens in clear, after a confirmation. |

**Output.** A `Spotify Auth Token:` header followed by the token record. Nothing is printed when the user has no
token. The access and refresh tokens are masked to their last 4 characters (`****abcd`), enough to tell whether a
token changed. With `--show-tokens` they are printed in clear, for instance to pass the refresh token to the live
Spotify tests: do not paste that output in public.
