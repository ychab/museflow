import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from museflow.domain.entities.taste import TasteEra
    from museflow.domain.entities.taste import TasteProfileData


def era_sort_key(era: "TasteEra") -> str:
    time_range = era["time_range"]
    if "Contemporary" in time_range:
        return "9999-99-99"
    if "Undated" in time_range or "unknown" in time_range:
        return "0000-00-00"
    match = re.search(r"(\d{4}-\d{2}-\d{2})", time_range)
    return match.group(1) if match else "0000-00-00"


def timeline_summary(profile: "TasteProfileData") -> str:
    eras = profile.get("taste_timeline", [])
    return " → ".join(era["era_label"] for era in eras) or "No timeline"


def core_identity_summary(profile: "TasteProfileData", top_n: int = 5) -> str:
    identity = profile.get("core_identity", {})
    top = sorted(identity.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return ", ".join(f"{k} ({v:.2f})" for k, v in top) or "unknown"


def behavioral_traits_summary(profile: "TasteProfileData") -> str:
    traits = profile.get("behavioral_traits", {})
    return ", ".join(f"{k}: {v:.2f}" for k, v in traits.items()) or "unknown"


def personality_archetype(profile: "TasteProfileData") -> str:
    return profile.get("personality_archetype") or "unknown"


def oldest_era_label(profile: "TasteProfileData") -> str:
    eras = profile.get("taste_timeline", [])
    return eras[0]["era_label"] if eras else "earliest era"


def current_era_label(profile: "TasteProfileData") -> str:
    eras = profile.get("taste_timeline", [])
    return eras[-1]["era_label"] if eras else "current era"
