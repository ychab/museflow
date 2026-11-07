import re
from typing import TYPE_CHECKING

from museflow.domain.const import TASTE_SEGMENT_WEIGHT
from museflow.domain.const import TASTE_TIMELINE_MAX_ERAS
from museflow.domain.const import TASTE_WEIGHT_DECIMALS

if TYPE_CHECKING:  # pragma: no cover
    from museflow.domain.entities.taste import TasteEra
    from museflow.domain.entities.taste import TasteProfileData
    from museflow.domain.entities.taste import TechnicalFingerprint

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _span_time_range(first: str, last: str) -> str:
    """From the start of `first` to the end of `last`; a range without dates is kept as written."""
    starts = _DATE_PATTERN.findall(first)
    ends = _DATE_PATTERN.findall(last)
    return f"{starts[0] if starts else first} to {ends[-1] if ends else last}"


def _mean(first: float, second: float) -> float:
    return round((first + second) / 2, TASTE_WEIGHT_DECIMALS)


def _combine_eras(older: TasteEra, newer: TasteEra, label: str | None) -> TasteEra:
    older_fp = older["technical_fingerprint"]
    newer_fp = newer["technical_fingerprint"]
    fingerprint: TechnicalFingerprint = {
        "energy": _mean(older_fp["energy"], newer_fp["energy"]),
        "acousticness": _mean(older_fp["acousticness"], newer_fp["acousticness"]),
        "rhythmic_complexity": _mean(older_fp["rhythmic_complexity"], newer_fp["rhythmic_complexity"]),
        "atmospheric": _mean(older_fp["atmospheric"], newer_fp["atmospheric"]),
        "instrumentalness": _mean(older_fp["instrumentalness"], newer_fp["instrumentalness"]),
    }
    return {
        "era_label": label or older["era_label"],
        "time_range": _span_time_range(older["time_range"], newer["time_range"]),
        "technical_fingerprint": fingerprint,
        "dominant_moods": list(dict.fromkeys(older["dominant_moods"] + newer["dominant_moods"])),
    }


def blend_weights(
    foundation: dict[str, float],
    segment: dict[str, float],
    segment_weight: float,
) -> dict[str, float]:
    """Weighted average of two tag maps over all their tags; a tag missing from one side weighs 0 there."""
    blended = {
        tag: round(
            foundation.get(tag, 0.0) * (1 - segment_weight) + segment.get(tag, 0.0) * segment_weight,
            TASTE_WEIGHT_DECIMALS,
        )
        for tag in foundation | segment
    }
    return {tag: weight for tag, weight in blended.items() if weight}  # a zero weight carries no signal


def merge_taste_profiles(
    foundation: TasteProfileData,
    segment: TasteProfileData,
    *,
    absorb: bool,
    oldest_label: str | None,
) -> TasteProfileData:
    """Merges a segment into the foundation, the timeline per the decisions a profiler took on it.

    Args:
        absorb: the segment continues the foundation's last era, which is extended to the segment's end date
            (label, fingerprint and moods unchanged); otherwise the segment's era is appended.
        oldest_label: the label of the era the two oldest become, when the timeline outgrows its limit; the older
            label is kept when None.
    """
    timeline = list(foundation["taste_timeline"])
    segment_eras = segment["taste_timeline"]
    if absorb and timeline and segment_eras:
        last_era = timeline[-1].copy()
        last_era["time_range"] = _span_time_range(last_era["time_range"], segment_eras[-1]["time_range"])
        timeline[-1] = last_era
    else:
        timeline.extend(segment_eras)

    while len(timeline) > TASTE_TIMELINE_MAX_ERAS:
        timeline[:2] = [_combine_eras(timeline[0], timeline[1], oldest_label)]

    merged: TasteProfileData = {
        "taste_timeline": timeline,
        "core_identity": blend_weights(foundation["core_identity"], segment["core_identity"], TASTE_SEGMENT_WEIGHT),
        "current_vibe": dict(segment["current_vibe"]),
        "personality_archetype": None,
        "life_phase_insights": [],
        "musical_identity_summary": None,
        "behavioral_traits": {},
        "discovery_style": None,
    }
    return merged


def era_sort_key(era: TasteEra) -> str:
    time_range = era["time_range"]
    if "Contemporary" in time_range:
        return "9999-99-99"
    if "Undated" in time_range or "unknown" in time_range:
        return "0000-00-00"
    match = re.search(r"(\d{4}-\d{2}-\d{2})", time_range)
    return match.group(1) if match else "0000-00-00"


def timeline_summary(profile: TasteProfileData) -> str:
    eras = profile.get("taste_timeline", [])
    return " → ".join(era["era_label"] for era in eras) or "No timeline"


def core_identity_summary(profile: TasteProfileData, top_n: int = 5) -> str:
    identity = profile.get("core_identity", {})
    top = sorted(identity.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return ", ".join(f"{k} ({v:.2f})" for k, v in top) or "unknown"


def behavioral_traits_summary(profile: TasteProfileData) -> str:
    traits = profile.get("behavioral_traits", {})
    return ", ".join(f"{k}: {v:.2f}" for k, v in traits.items()) or "unknown"


def personality_archetype(profile: TasteProfileData) -> str:
    return profile.get("personality_archetype") or "unknown"


def oldest_era_label(profile: TasteProfileData) -> str:
    eras = profile.get("taste_timeline", [])
    return eras[0]["era_label"] if eras else "earliest era"


def current_era_label(profile: TasteProfileData) -> str:
    eras = profile.get("taste_timeline", [])
    return eras[-1]["era_label"] if eras else "current era"


def current_vibe_summary(profile: TasteProfileData, top_n: int = 5) -> str:
    vibe = profile.get("current_vibe", {})
    top = sorted(vibe.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return ", ".join(f"{k} ({v:.2f})" for k, v in top) or "unknown"
