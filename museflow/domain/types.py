from enum import IntFlag
from enum import StrEnum

type TrackOrdering = list[tuple[TrackOrderBy, SortOrder]]
type ScoreAdvisor = float
type ScoreReconciler = float
type LocaleCode = str  # ISO 639-1 two-letter lowercase language code, e.g. "fr", "en"


def validate_locale(v: object) -> "LocaleCode | None":
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if len(v) == 2 and v.isalpha() else None


DISCOVERY_TRACK_SCORE_MIN: int = 0
DISCOVERY_TRACK_SCORE_MAX: int = 10


class TrackSource(IntFlag):
    HISTORY = 1
    DISCOVERY = 2


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class MusicAdvisor(StrEnum):
    GEMINI = "gemini"


class TasteProfiler(StrEnum):
    GEMINI = "gemini"


class DiscoveryFocus(StrEnum):
    EXPANSION = "expansion"
    ROOTS_REVIVAL = "roots_revival"
    CULTURAL_BRIDGE = "cultural_bridge"


class PlaylistType(StrEnum):
    DISCOVERY = "discovery"  # AI-curated playlist
    HISTORY = "history"  # persisted "best of"


class MoodTag(StrEnum):
    ENERGETIC = "energetic"  # high energy, driving tempo
    CHILL = "chill"  # relaxed, low-key
    MELANCHOLIC = "melancholic"  # sad, bittersweet, nostalgic
    UPBEAT = "upbeat"  # positive, feel-good
    AGGRESSIVE = "aggressive"  # intense, confrontational
    ROMANTIC = "romantic"  # love, tenderness
    FOCUS = "focus"  # concentration, minimal distraction
    PARTY = "party"  # dancefloor, social
    INTROSPECTIVE = "introspective"  # reflective, inward
    EUPHORIC = "euphoric"  # elation, peak emotion
    PEACEFUL = "peaceful"  # calm, serene
    DARK = "dark"  # moody, ominous, heavy


class TrackOrderBy(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PLAYED_AT_LAST = "played_at_last"
    PLAYED_AT_FIRST = "played_at_first"
    PLAYED_COUNT = "played_count"
    SCORE = "score"
    RANDOM = "random"

    @property
    def nullable(self) -> bool:
        """True for nullable columns — NULLs are sorted last in both ASC and DESC."""
        return self in (TrackOrderBy.PLAYED_AT_LAST, TrackOrderBy.PLAYED_AT_FIRST, TrackOrderBy.SCORE)


class PlaylistHistoryOrderBy(StrEnum):
    PLAYED_COUNT = "played_count"  # Sort by how many times the track was played
    SCORE = "score"  # Sort by the track's rating score


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class GenreTag(StrEnum):
    # Convention: genres list is ordered [macro, meso, micro?]
    # ── L1 Macro (broad umbrella) ────────────────────────────────────────────
    HIP_HOP = "hip-hop"  # umbrella for rap, trap, drill, lo-fi
    ELECTRONIC = "electronic"  # house, techno, dnb, trance, dubstep
    ROCK = "rock"  # indie, punk, alt, grunge, post-rock, prog
    POP = "pop"  # synth-pop, electro-pop, dance-pop, k-pop
    RNB = "r-n-b"  # contemporary r&b, neo-soul, funk, trap-soul
    JAZZ = "jazz"  # fusion, bebop, nu-jazz, smooth
    CLASSICAL = "classical"  # baroque, romantic, contemporary classical
    REGGAE = "reggae"  # roots, dancehall, dub
    COUNTRY = "country"  # outlaw, bluegrass, americana
    LATIN = "latin"  # reggaeton, salsa, cumbia, bossa-nova
    METAL = "metal"  # heavy, black, death, nu, thrash, doom
    FOLK = "folk"  # indie-folk, acoustic-folk, singer-songwriter
    WORLD = "world"  # afrobeats, arabic, balkan, celtic
    # ── L2 Meso (subgenre) ───────────────────────────────────────────────────
    # hip-hop
    RAP = "rap"
    TRAP = "trap"
    DRILL = "drill"
    BOOM_BAP = "boom-bap"
    LO_FI_HIP_HOP = "lo-fi hip-hop"
    # electronic
    HOUSE = "house"
    TECHNO = "techno"
    DRUM_AND_BASS = "drum-and-bass"
    AMBIENT_ELECTRONIC = "ambient-electronic"
    TRANCE = "trance"
    DUBSTEP = "dubstep"
    # rock
    INDIE_ROCK = "indie-rock"
    ALTERNATIVE_ROCK = "alternative-rock"
    PUNK = "punk"
    HARD_ROCK = "hard-rock"
    GRUNGE = "grunge"
    POST_ROCK = "post-rock"
    PROGRESSIVE_ROCK = "progressive-rock"
    PSYCHEDELIC_ROCK = "psychedelic-rock"
    # pop
    SYNTH_POP = "synth-pop"
    ELECTRO_POP = "electro-pop"
    DANCE_POP = "dance-pop"
    INDIE_POP = "indie-pop"
    K_POP = "k-pop"
    # r-n-b
    CONTEMPORARY_RNB = "contemporary-r-n-b"
    NEO_SOUL = "neo-soul"
    FUNK = "funk"
    TRAP_SOUL = "trap-soul"
    # jazz
    JAZZ_FUSION = "jazz-fusion"
    SMOOTH_JAZZ = "smooth-jazz"
    BEBOP = "bebop"
    NU_JAZZ = "nu-jazz"
    # classical
    BAROQUE = "baroque"
    ROMANTIC = "romantic"
    CONTEMPORARY_CLASSICAL = "contemporary-classical"
    # reggae
    ROOTS_REGGAE = "roots-reggae"
    DANCEHALL = "dancehall"
    DUB = "dub"
    # country
    OUTLAW_COUNTRY = "outlaw-country"
    FOLK_COUNTRY = "folk-country"
    BLUEGRASS = "bluegrass"
    # latin
    REGGAETON = "reggaeton"
    SALSA = "salsa"
    CUMBIA = "cumbia"
    BOSSA_NOVA = "bossa-nova"
    LATIN_POP = "latin-pop"
    FLAMENCO = "flamenco"
    # metal
    HEAVY_METAL = "heavy-metal"
    BLACK_METAL = "black-metal"
    DEATH_METAL = "death-metal"
    NU_METAL = "nu-metal"
    THRASH_METAL = "thrash-metal"
    DOOM_METAL = "doom-metal"
    # folk
    INDIE_FOLK = "indie-folk"
    ACOUSTIC_FOLK = "acoustic-folk"
    SINGER_SONGWRITER = "singer-songwriter"
    # world
    AFROBEATS = "afrobeats"
    ARABIC = "arabic"
    BALKAN = "balkan"
    CELTIC = "celtic"
    # ── L3 Micro (specific variant / style) ──────────────────────────────────
    # rap
    AFRO_RAP = "afro rap"  # rap from African diaspora (Hamza, Freeze Corleone, Gazo)
    CLOUD_RAP = "cloud rap"  # ethereal, hazy production (A$AP Rocky, SpaceGhostPurrp)
    MELODIC_RAP = "melodic rap"  # singing + rapping hybrid (Juice WRLD, Rod Wave)
    CONSCIOUS_RAP = "conscious rap"
    GANGSTA_RAP = "gangsta rap"
    MUMBLE_RAP = "mumble rap"
    # trap
    PHONK = "phonk"
    PLUGG = "plugg"
    RAGE_TRAP = "rage trap"
    SAD_TRAP = "sad trap"
    # drill
    UK_DRILL = "uk drill"
    NY_DRILL = "ny drill"
    CHICAGO_DRILL = "chicago drill"
    # boom-bap
    EAST_COAST_RAP = "east coast rap"
    GOLDEN_AGE = "golden age hip-hop"
    # lo-fi hip-hop
    LO_FI_BEATS = "lo-fi beats"
    LO_FI_JAZZ_HOP = "lo-fi jazz hop"
    # house
    DEEP_HOUSE = "deep house"
    TECH_HOUSE = "tech house"
    AFRO_HOUSE = "afro house"
    PROGRESSIVE_HOUSE = "progressive house"
    TROPICAL_HOUSE = "tropical house"
    FUTURE_HOUSE = "future house"
    # techno
    INDUSTRIAL_TECHNO = "industrial techno"
    MINIMAL_TECHNO = "minimal techno"
    MELODIC_TECHNO = "melodic techno"
    HARD_TECHNO = "hard techno"
    # drum-and-bass
    LIQUID_DNB = "liquid dnb"
    NEUROFUNK = "neurofunk"
    JUMP_UP = "jump up"
    # ambient-electronic
    DARK_AMBIENT = "dark ambient"
    CHILLWAVE = "chillwave"
    VAPORWAVE = "vaporwave"
    # trance
    PSYTRANCE = "psytrance"
    PROGRESSIVE_TRANCE = "progressive trance"
    UPLIFTING_TRANCE = "uplifting trance"
    # dubstep
    FUTURE_BASS = "future bass"
    BROSTEP = "brostep"
    # indie-rock
    SHOEGAZE = "shoegaze"
    EMO = "emo"
    MATH_ROCK = "math rock"
    # punk
    HARDCORE_PUNK = "hardcore punk"
    POST_PUNK = "post-punk"
    POP_PUNK = "pop-punk"
    GARAGE_PUNK = "garage punk"
    # post-rock
    CINEMATIC_ROCK = "cinematic rock"
    # progressive-rock
    ART_ROCK = "art rock"
    KRAUTROCK = "krautrock"
    # synth-pop
    DARKWAVE = "darkwave"
    NEW_WAVE = "new wave"
    DREAM_POP = "dream pop"
    # electro-pop
    HYPERPOP = "hyperpop"
    BEDROOM_POP = "bedroom pop"
    # dance-pop
    DISCO_POP = "disco pop"
    NU_DISCO = "nu disco"
    # indie-pop
    CHAMBER_POP = "chamber pop"
    # k-pop
    KPOP_GROUP = "kpop group"
    KPOP_SOLO = "kpop solo"
    # contemporary-r-n-b
    ALT_RNB = "alt r-n-b"
    QUIET_STORM = "quiet storm"
    # neo-soul
    SOUL_JAZZ = "soul jazz"
    ACOUSTIC_SOUL = "acoustic soul"
    # funk
    G_FUNK = "g-funk"
    P_FUNK = "p-funk"
    # jazz
    ECM_JAZZ = "ecm jazz"
    HARD_BOP = "hard bop"
    COOL_JAZZ = "cool jazz"
    JAZZ_HOP = "jazz hop"
    SPIRITUAL_JAZZ = "spiritual jazz"
    # classical
    MINIMALIST = "minimalist"
    NEO_CLASSICAL = "neo-classical"
    # reggae
    LOVERS_ROCK = "lovers rock"
    AFRO_DANCEHALL = "afro dancehall"
    # latin
    LATIN_TRAP = "latin trap"
    SALSA_ROMANTICA = "salsa romantica"
    TIMBA = "timba"
    POP_EN_ESPANOL = "pop en español"
    BALADA = "balada"
    FLAMENCO_NUEVO = "flamenco nuevo"
    # metal
    STONER_METAL = "stoner metal"
    SLUDGE_METAL = "sludge metal"
    ATMOSPHERIC_BLACK = "atmospheric black metal"
    SYMPHONIC_METAL = "symphonic metal"
    MELODIC_DEATH = "melodic death metal"
    FUNERAL_DOOM = "funeral doom"
    RAP_METAL = "rap metal"
    # folk
    FREAK_FOLK = "freak folk"
    AMERICANA_FOLK = "americana folk"
    # world
    AFROPOP = "afropop"
    AFRO_FUSION = "afro fusion"
    KHALEEJI = "khaleeji"
    NORTH_AFRICAN = "north african"
    LEVANT_POP = "levant pop"


GENRE_MACRO_TAGS: tuple[GenreTag, ...] = (
    GenreTag.HIP_HOP,
    GenreTag.ELECTRONIC,
    GenreTag.ROCK,
    GenreTag.POP,
    GenreTag.RNB,
    GenreTag.JAZZ,
    GenreTag.CLASSICAL,
    GenreTag.REGGAE,
    GenreTag.COUNTRY,
    GenreTag.LATIN,
    GenreTag.METAL,
    GenreTag.FOLK,
    GenreTag.WORLD,
)


GENRE_MESO_TAGS: tuple[GenreTag, ...] = (
    # hip-hop
    GenreTag.RAP,
    GenreTag.TRAP,
    GenreTag.DRILL,
    GenreTag.BOOM_BAP,
    GenreTag.LO_FI_HIP_HOP,
    # electronic
    GenreTag.HOUSE,
    GenreTag.TECHNO,
    GenreTag.DRUM_AND_BASS,
    GenreTag.AMBIENT_ELECTRONIC,
    GenreTag.TRANCE,
    GenreTag.DUBSTEP,
    # rock
    GenreTag.INDIE_ROCK,
    GenreTag.ALTERNATIVE_ROCK,
    GenreTag.PUNK,
    GenreTag.HARD_ROCK,
    GenreTag.GRUNGE,
    GenreTag.POST_ROCK,
    GenreTag.PROGRESSIVE_ROCK,
    GenreTag.PSYCHEDELIC_ROCK,
    # pop
    GenreTag.SYNTH_POP,
    GenreTag.ELECTRO_POP,
    GenreTag.DANCE_POP,
    GenreTag.INDIE_POP,
    GenreTag.K_POP,
    # r-n-b
    GenreTag.CONTEMPORARY_RNB,
    GenreTag.NEO_SOUL,
    GenreTag.FUNK,
    GenreTag.TRAP_SOUL,
    # jazz
    GenreTag.JAZZ_FUSION,
    GenreTag.SMOOTH_JAZZ,
    GenreTag.BEBOP,
    GenreTag.NU_JAZZ,
    # classical
    GenreTag.BAROQUE,
    GenreTag.ROMANTIC,
    GenreTag.CONTEMPORARY_CLASSICAL,
    # reggae
    GenreTag.ROOTS_REGGAE,
    GenreTag.DANCEHALL,
    GenreTag.DUB,
    # country
    GenreTag.OUTLAW_COUNTRY,
    GenreTag.FOLK_COUNTRY,
    GenreTag.BLUEGRASS,
    # latin
    GenreTag.REGGAETON,
    GenreTag.SALSA,
    GenreTag.CUMBIA,
    GenreTag.BOSSA_NOVA,
    GenreTag.LATIN_POP,
    GenreTag.FLAMENCO,
    # metal
    GenreTag.HEAVY_METAL,
    GenreTag.BLACK_METAL,
    GenreTag.DEATH_METAL,
    GenreTag.NU_METAL,
    GenreTag.THRASH_METAL,
    GenreTag.DOOM_METAL,
    # folk
    GenreTag.INDIE_FOLK,
    GenreTag.ACOUSTIC_FOLK,
    GenreTag.SINGER_SONGWRITER,
    # world
    GenreTag.AFROBEATS,
    GenreTag.ARABIC,
    GenreTag.BALKAN,
    GenreTag.CELTIC,
)


GENRE_MICRO_TAGS: tuple[GenreTag, ...] = (
    # rap
    GenreTag.AFRO_RAP,
    GenreTag.CLOUD_RAP,
    GenreTag.MELODIC_RAP,
    GenreTag.CONSCIOUS_RAP,
    GenreTag.GANGSTA_RAP,
    GenreTag.MUMBLE_RAP,
    # trap
    GenreTag.PHONK,
    GenreTag.PLUGG,
    GenreTag.RAGE_TRAP,
    GenreTag.SAD_TRAP,
    # drill
    GenreTag.UK_DRILL,
    GenreTag.NY_DRILL,
    GenreTag.CHICAGO_DRILL,
    # boom-bap
    GenreTag.EAST_COAST_RAP,
    GenreTag.GOLDEN_AGE,
    # lo-fi hip-hop
    GenreTag.LO_FI_BEATS,
    GenreTag.LO_FI_JAZZ_HOP,
    # house
    GenreTag.DEEP_HOUSE,
    GenreTag.TECH_HOUSE,
    GenreTag.AFRO_HOUSE,
    GenreTag.PROGRESSIVE_HOUSE,
    GenreTag.TROPICAL_HOUSE,
    GenreTag.FUTURE_HOUSE,
    # techno
    GenreTag.INDUSTRIAL_TECHNO,
    GenreTag.MINIMAL_TECHNO,
    GenreTag.MELODIC_TECHNO,
    GenreTag.HARD_TECHNO,
    # drum-and-bass
    GenreTag.LIQUID_DNB,
    GenreTag.NEUROFUNK,
    GenreTag.JUMP_UP,
    # ambient-electronic
    GenreTag.DARK_AMBIENT,
    GenreTag.CHILLWAVE,
    GenreTag.VAPORWAVE,
    # trance
    GenreTag.PSYTRANCE,
    GenreTag.PROGRESSIVE_TRANCE,
    GenreTag.UPLIFTING_TRANCE,
    # dubstep
    GenreTag.FUTURE_BASS,
    GenreTag.BROSTEP,
    # indie-rock
    GenreTag.SHOEGAZE,
    GenreTag.EMO,
    GenreTag.MATH_ROCK,
    # punk
    GenreTag.HARDCORE_PUNK,
    GenreTag.POST_PUNK,
    GenreTag.POP_PUNK,
    GenreTag.GARAGE_PUNK,
    # post-rock
    GenreTag.CINEMATIC_ROCK,
    # progressive-rock
    GenreTag.ART_ROCK,
    GenreTag.KRAUTROCK,
    # synth-pop
    GenreTag.DARKWAVE,
    GenreTag.NEW_WAVE,
    GenreTag.DREAM_POP,
    # electro-pop
    GenreTag.HYPERPOP,
    GenreTag.BEDROOM_POP,
    # dance-pop
    GenreTag.DISCO_POP,
    GenreTag.NU_DISCO,
    # indie-pop
    GenreTag.CHAMBER_POP,
    # k-pop
    GenreTag.KPOP_GROUP,
    GenreTag.KPOP_SOLO,
    # contemporary-r-n-b
    GenreTag.ALT_RNB,
    GenreTag.QUIET_STORM,
    # neo-soul
    GenreTag.SOUL_JAZZ,
    GenreTag.ACOUSTIC_SOUL,
    # funk
    GenreTag.G_FUNK,
    GenreTag.P_FUNK,
    # jazz
    GenreTag.ECM_JAZZ,
    GenreTag.HARD_BOP,
    GenreTag.COOL_JAZZ,
    GenreTag.JAZZ_HOP,
    GenreTag.SPIRITUAL_JAZZ,
    # classical
    GenreTag.MINIMALIST,
    GenreTag.NEO_CLASSICAL,
    # reggae
    GenreTag.LOVERS_ROCK,
    GenreTag.AFRO_DANCEHALL,
    # latin
    GenreTag.LATIN_TRAP,
    GenreTag.SALSA_ROMANTICA,
    GenreTag.TIMBA,
    GenreTag.POP_EN_ESPANOL,
    GenreTag.BALADA,
    GenreTag.FLAMENCO_NUEVO,
    # metal
    GenreTag.STONER_METAL,
    GenreTag.SLUDGE_METAL,
    GenreTag.ATMOSPHERIC_BLACK,
    GenreTag.SYMPHONIC_METAL,
    GenreTag.MELODIC_DEATH,
    GenreTag.FUNERAL_DOOM,
    GenreTag.RAP_METAL,
    # folk
    GenreTag.FREAK_FOLK,
    GenreTag.AMERICANA_FOLK,
    # world
    GenreTag.AFROPOP,
    GenreTag.AFRO_FUSION,
    GenreTag.KHALEEJI,
    GenreTag.NORTH_AFRICAN,
    GenreTag.LEVANT_POP,
)
