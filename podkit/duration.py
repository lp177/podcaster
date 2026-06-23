MIN_MINUTES = 3
MAX_MINUTES = 20
DEFAULT_MINUTES = 10

WORDS_PER_MINUTE = 145


def clamp_minutes(minutes: int) -> int:
    return max(MIN_MINUTES, min(MAX_MINUTES, int(minutes)))


def plan_for(minutes: int) -> dict:
    minutes = clamp_minutes(minutes)
    target_words = minutes * WORDS_PER_MINUTE
    longform = minutes > 6
    chunks = max(2, round(minutes / 1.3)) if longform else 0
    return {
        "minutes": minutes,
        "longform": longform,
        "target_words": target_words,
        "max_num_chunks": chunks,
        "min_chunk_size": 600,
    }
