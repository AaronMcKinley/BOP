"""scoring.py: shared battle scoring - finishing positions, points, leaderboard.

Used by simulate.py (to embed a provisional leaderboard into events.json so the
rendered video can show the standings) and by save.py (to commit the same
points for real).
"""

POINTS = {1: 4, 2: 3, 3: 2, 4: 1, 5: 0}


def finishing_positions(events):
    """ball_id -> finishing position (1 = winner, higher = eliminated earlier).

    The winner is 1st; the elimination order reversed gives 2nd, 3rd, ... etc.
    """
    winner = int(events["winner"]["ball_id"])
    positions = {winner: 1}
    elims = events.get("eliminations", [])
    for i, e in enumerate(reversed(elims)):
        positions[int(e["ball_id"])] = i + 2
    return positions


def battle_points(positions):
    """ball_id -> points earned this battle (4/3/2/1/0 by finishing position)."""
    return {bid: POINTS[pos] for bid, pos in positions.items()}


def leaderboard_current(stats):
    """Current standings (before this battle), sorted by points, kills as the
    tiebreaker - equal points are ordered by kills so the table moves between
    battles. Each row: {id, name, points, wins, kills, position}.
    """
    rows = []
    for ball in stats.get("balls", []):
        rows.append({
            "id": ball["id"],
            "name": ball["name"],
            "points": ball.get("points", 0),
            "wins": ball.get("wins", 0),
            "kills": ball.get("kills", 0),
        })
    rows.sort(key=lambda r: (-r["points"], -r["kills"], -r["wins"], r["id"]))
    for i, row in enumerate(rows, 1):
        row["position"] = i
    return rows


def leaderboard_after(stats, positions, points, battle_stats=None):
    """The season standings as they would look after this battle, sorted by
    points with kills as the tiebreaker.

    Each row: {id, name, points, wins, podiums, kills, delta, position}.
    """
    rows = []
    for ball in stats.get("balls", []):
        bid = ball["id"]
        pos = positions.get(bid)
        if pos is None:
            continue
        pts = points.get(bid, 0)
        kills = ball.get("kills", 0)
        if battle_stats:
            # battle_stats keys may be int (in-memory) or str (after JSON).
            bstats = battle_stats.get(bid) or battle_stats.get(str(bid), {})
            kills += bstats.get("kills", 0)
        rows.append({
            "id": bid,
            "name": ball["name"],
            "points": ball.get("points", 0) + pts,
            "wins": ball.get("wins", 0) + (1 if pos == 1 else 0),
            "podiums": ball.get("podiums", 0) + (1 if pos <= 3 else 0),
            "kills": kills,
            "delta": pts,
        })
    rows.sort(key=lambda r: (-r["points"], -r["kills"], -r["wins"], r["id"]))
    for i, row in enumerate(rows, 1):
        row["position"] = i
    return rows
