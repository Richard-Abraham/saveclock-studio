"""The offline keyword table (DECISIONS §8f): the last rung when no model is used.

Data, not logic: changing a list is a content change (bump TABLE_VERSION and review it as such).
Search terms are portrait friendly: places, weather, motion, light; no brands, no people.
"""

TABLE_VERSION = "1"

# fmt: off
TABLE: dict[tuple[str, str, str], tuple[str, ...]] = {
    ("low", "slow", "default"): (
        "foggy forest", "calm lake", "rain window", "slow clouds", "candle flame",
        "snow falling", "empty beach", "sunrise mist", "leaves wind", "night sky",
    ),
    ("low", "mid", "default"): (
        "morning window light", "steaming coffee", "gentle waves", "drifting clouds",
        "quiet street", "wind in grass", "soft rain", "lake reflection", "sunlit curtains",
        "paper lanterns",
    ),
    ("low", "fast", "default"): (
        "city rain night", "car window rain", "passing trains", "moving clouds",
        "airport lights", "highway dusk", "wind through trees", "blurred lights", "night bus",
        "falling leaves",
    ),
    ("low", "vfast", "default"): (
        "time-lapse clouds", "night sky stars", "light trails", "rain on glass",
        "traffic timelapse", "fast river", "wind turbines", "moving fog", "speeding train",
        "neon reflections",
    ),
    ("mid", "slow", "default"): (
        "golden hour field", "ocean sunset", "mountain mist", "slow river", "street cafe",
        "autumn forest", "hot air balloon", "sailing boat", "flower field", "drifting smoke",
    ),
    ("mid", "mid", "default"): (
        "city street", "walking street", "beach waves", "coastal road", "busy market",
        "bicycle ride", "sunset skyline", "river bridge", "forest path", "festival lights",
    ),
    ("mid", "fast", "default"): (
        "city traffic", "subway train", "skateboarding", "running water", "road trip",
        "cloud timelapse", "street lights", "rooftop city", "motorbike", "rapids river",
    ),
    ("mid", "vfast", "default"): (
        "speeding road", "fast traffic", "racing car", "spinning lights", "waterfall",
        "time-lapse city", "bike race", "drone city", "wind surfing", "neon signs",
    ),
    ("high", "slow", "default"): (
        "storm clouds", "ocean waves", "volcano", "thunderstorm", "fire flames", "big waves",
        "stadium lights", "dramatic sky", "sunrise peak", "mountain summit",
    ),
    ("high", "mid", "default"): (
        "concert lights", "fireworks", "crowd cheering", "dance floor", "waves crashing",
        "fire sparks", "city skyline night", "laser lights", "festival crowd", "sparklers",
    ),
    ("high", "fast", "default"): (
        "neon city night", "fireworks", "crowd lights", "speeding road", "city traffic",
        "lightning storm", "dance floor", "skateboard", "waves crashing", "fire sparks",
    ),
    ("high", "vfast", "default"): (
        "strobe lights", "racing cars", "lightning", "fast fireworks", "explosion sparks",
        "speed tunnel", "night drive", "drum sticks", "turbo city", "motocross",
    ),
}
# fmt: on


def table_keywords(energy: str, tempo: str, style: str = "default") -> tuple[str, ...]:
    """The row for the buckets; an unknown style uses the `default` row."""
    return TABLE.get((energy, tempo, style)) or TABLE[(energy, tempo, "default")]
