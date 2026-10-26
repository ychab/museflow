# Spotify data export

MuseFlow builds its library from the **Extended streaming history** that Spotify provides on request. This is
a different export from the default "Account data": it contains the full listing history, not just the last
year.

## Requesting the export

1. Open the Spotify account page in a browser and go to **Privacy settings**.
2. In the **Download your data** section, select **Extended streaming history**.
3. Confirm the request, then confirm it again from the email that Spotify sends.
4. Wait. Spotify states that it can take **up to 30 days**; it is often faster.
5. An email arrives with a download link. Download the **ZIP** archive and unzip it.

!!! note
    Spotify occasionally changes the wording and layout of the privacy page. Look for the extended streaming
    history option rather than the standard account data one.

## What is in the archive

The unzipped folder contains several JSON files. The ones that matter are the audio history files:

```text
Streaming_History_Audio_2015-2017_0.json
Streaming_History_Audio_2018-2020_1.json
Streaming_History_Audio_2021-2024_2.json
```

The other files of the export (video history, user data, and so on) are not needed.

!!! note
    `tracks history` only reads the `Streaming_History_Audio_*.json` files of the directory it is given. The other
    files of the export can stay in the folder, so you can point `--directory` at the unzipped export as is.

## What MuseFlow reads

For each entry of each file, only these fields are used:

| Field | Used for |
| --- | --- |
| `master_metadata_track_name` | Track name |
| `master_metadata_album_artist_name` | Artist |
| `master_metadata_album_album_name` | Album |
| `spotify_track_uri` | Track identity (`spotify:track:<id>`) |
| `ts` | Timestamp of the play (first and last played dates, play count) |
| `ms_played` | Duration played, for the minimum-duration filter |

Everything else is ignored, including the IP address, the country and the device or platform fields.

## What gets skipped

Entries are skipped, and counted in the import report, when:

- there is no timestamp (`ts`);
- the play is shorter than the minimum duration;
- there is no valid track URI or track name (podcast episodes and local files, for instance).

### Minimum duration

`--min-duration-played` is expressed in seconds and defaults to **90**. A play shorter than that, typically a
track skipped after a few seconds, does not count as a listen. Lower it to keep more plays, raise it to keep
only tracks that were really listened to.

Tracks are identified by a fingerprint of name and artist, so the same song appearing under several Spotify
IDs is merged into one track with the combined play times.

## Importing

```bash
museflow tracks history --email user@example.com --directory ~/Downloads/MySpotifyData
```

See [`tracks history`](commands/tracks.md#tracks-history) for all options and the printed report.
