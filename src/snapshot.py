# -*- coding: utf-8 -*-
"""Pull the live room's draw into the page's built-in defaults.

The shared Firebase room is the truth while the event is running, and deploying
new HTML does not touch it. But the page still carries a default draw for a room
that is empty, and if that default drifts from reality then any wipe, or any
test page, brings back a draw nobody recognises. Run this after changing teams
or tee times on the site so the two agree:

    python src/snapshot.py

Reads nothing but the room and writes nothing but the DEFAULT_* block.
"""
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "template.html")
ROOM = "https://golf-5ac54-default-rtdb.firebaseio.com/shootout.json"

SIDES = {2: ["n", "g"], 4: ["n", "g", "c", "d"]}


def flat_list(v, n):
    """Realtime Database hands back a list or an object, depending on its mood."""
    if isinstance(v, list):
        return (v + [None] * n)[:n]
    if isinstance(v, dict):
        return [v.get(str(i)) for i in range(n)]
    return [None] * n


def main():
    raw = json.loads(urllib.request.urlopen(ROOM, timeout=20).read().decode("utf-8"))

    mode = 4 if raw.get("mode") == 4 else 2
    allow = SIDES[mode]
    teams = raw.get("teams") or {}
    slots = flat_list(raw.get("slots"), 16)
    mu = flat_list(raw.get("matchups"), 8)

    # ---- refuse to bake in a draw that does not hold together ----
    assert all(t in allow for t in teams.values()), "a player is on a side this mode has no room for"
    per = len(teams) // mode
    for t in allow:
        got = sum(1 for v in teams.values() if v == t)
        assert got == per, "side %s holds %d of %d" % (t, got, per)
    assert all(c in allow for c in mu), "matchups name a side this mode has no room for"
    seen = {t: 0 for t in allow}
    for i in range(4):
        a, b = mu[i * 2], mu[i * 2 + 1]
        assert a != b, "match %d has a team playing itself" % (i + 1)
        seen[a] += 1
        seen[b] += 1
    want = (16 // mode) // 2
    assert all(v == want for v in seen.values()), "each side must appear %d times: %s" % (want, seen)
    assert len([x for x in slots if x]) == 16, "the draw is not full"
    assert len(set(slots)) == 16, "somebody is seated twice"
    for i, pid in enumerate(slots):
        side = mu[(i // 4) * 2 + (0 if i % 4 < 2 else 1)]
        assert teams.get(pid) == side, "seat %d holds %s, who is not on %s" % (i, pid, side)

    # ---- rewrite the defaults ----
    src = io.open(TEMPLATE, encoding="utf-8").read()

    order = [p for p in slots]  # slot order reads better than alphabetical
    team_lines = []
    for i in range(0, 16, 4):
        chunk = ", ".join('%s:"%s"' % (pid, teams[pid]) for pid in order[i:i + 4])
        team_lines.append("  " + chunk + ("," if i < 12 else ""))
    teams_js = "var DEFAULT_TEAMS={\n" + "\n".join(team_lines) + "\n};"

    slot_lines = []
    for i in range(0, 16, 4):
        chunk = ", ".join('"%s"' % pid for pid in slots[i:i + 4])
        pad = "var DEFAULT_SLOTS=[" if i == 0 else " " * 19
        slot_lines.append(pad + chunk + ("," if i < 12 else "];"))
    slots_js = "\n".join(slot_lines)

    mode_js = "var DEFAULT_MODE=%d;" % mode
    mu_js = "var DEFAULT_MU=[%s];" % ",".join('"%s"' % c for c in mu)

    block = "\n".join([mode_js, mu_js, teams_js, slots_js])

    pat = re.compile(
        r"var DEFAULT_MODE=.*?var DEFAULT_SLOTS=\[.*?\];",
        re.S)
    if pat.search(src):
        src = pat.sub(block, src, count=1)
    else:
        old = re.compile(r"var DEFAULT_TEAMS=\{.*?\};\nvar DEFAULT_SLOTS=\[.*?\];", re.S)
        assert old.search(src), "cannot find the defaults block to replace"
        src = old.sub(block, src, count=1)

    io.open(TEMPLATE, "w", encoding="utf-8", newline="\n").write(src)

    NAME = dict(re.findall(r'\{id:"(\w+)",\s*name:"([^"]+)"', src))
    TEAM = {"n": "Team 1", "g": "Team 2", "c": "Team 3", "d": "Team 4"}
    print("snapshotted the live room into the page defaults")
    print("  mode      %d teams" % mode)
    for i in range(4):
        a, b = mu[i * 2], mu[i * 2 + 1]
        A = " / ".join(NAME.get(p, p) for p in slots[i * 4:i * 4 + 2])
        B = " / ".join(NAME.get(p, p) for p in slots[i * 4 + 2:i * 4 + 4])
        print("  match %d   %s: %s  v  %s: %s" % (i + 1, TEAM[a], A, TEAM[b], B))
    print("")
    print("  rebuild with: python src/build-site.py && python src/build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
