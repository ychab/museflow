# Example taste profiles

A taste profile is the central artifact of MuseFlow: a structured portrait of a listener, built by an LLM from the streaming history and the track ratings. The history is analysed in batches, the partial results are merged into a single profile, and a final reflection pass adds the psychographic layer (archetype, traits, narrative). Playlists and recommendations are then steered by this profile.

The three profiles below are entirely fictional. They exist to show what the output looks like without publishing anyone's real listening data.

<div class="grid cards" markdown>

-   **Pop**

    ---

    Mainstream radio hits, dancefloor years, a K-pop detour and a settling into indie pop.

    [:octicons-browser-24: View the profile](pop.html){ target=_blank }
    · [:octicons-download-24: pop.yaml](pop.yaml){ target=_blank }

-   **Rock**

    ---

    Classic rock foundations, grunge, an indie decade, an instrumental escape and a return to heavy fuzz.

    [:octicons-browser-24: View the profile](rock.html){ target=_blank }
    · [:octicons-download-24: rock.yaml](rock.yaml){ target=_blank }

-   **Hip-hop**

    ---

    An international, producer-driven path from golden age boom bap through trap to jazz rap and UK drill.

    [:octicons-browser-24: View the profile](rap.html){ target=_blank }
    · [:octicons-download-24: rap.yaml](rap.yaml){ target=_blank }

</div>

The YAML files are in the exact format written by `museflow taste export`, so they can be loaded with `museflow taste import`.

The HTML pages are the output of `museflow taste view --format html`. They load Tailwind CSS and a web font from public CDNs, so they need an internet connection to be styled.

## Anatomy of a profile

| Section | What it contains |
|---------|------------------|
| `personality_archetype` | One evocative label summarising the listener. |
| `musical_identity_summary` | A short narrative of the listener's evolution from the earliest to the latest era. |
| `core_identity` | The stable "DNA": long-term genre and mood affinities, weighted from 0 to 1. |
| `current_vibe` | What the most recent listening reveals right now; replaced at each merge. |
| `taste_timeline` | Chronological eras, each with a label, a date range, dominant moods and a technical fingerprint (energy, acousticness, rhythmic complexity, atmosphere, instrumentalness). |
| `behavioral_traits` | Scores from 0 to 1 for openness, adventurousness, nostalgia bias and rhythmic dependency. |
| `discovery_style` | A short label describing how the listener finds new music. |
| `life_phase_insights` | Observed shifts in listening that hint at life transitions. |
| `profiler_metadata`, `logic_version` | Which models produced each stage (segment, merge, reflect) and the version of the profiling logic. |
| `tracks_count`, `status` | How many tracks were analysed and whether the build is finished. |

Genres and moods in `core_identity`, `current_vibe` and `dominant_moods` come from a closed vocabulary shared with the rest of the application.
