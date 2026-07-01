from enum import IntFlag
from enum import StrEnum


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
