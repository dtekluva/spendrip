MAX_PRIORITIES = 3


def set_priority(order: list[str], plan_id: str, rank: int) -> tuple[list[str], list[str]]:
    """
    Put `plan_id` at position `rank` (1-based) in the priority order, or remove it (rank 0).
    Plans at that position and below move down one place. If that makes a 4th priority, the
    plan pushed out stops being a priority and is returned in `dropped`.
    """
    nxt = [x for x in order if x != plan_id]
    if rank > 0:
        nxt.insert(min(rank - 1, len(nxt)), plan_id)
    return nxt[:MAX_PRIORITIES], nxt[MAX_PRIORITIES:]
