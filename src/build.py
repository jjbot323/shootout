import json, sys, io, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "template.html")
OUT  = os.path.join(HERE, "shootout.html")

M_STATE = "%%" + "STATE" + "%%"
M_SRC   = "%%" + "SRC" + "%%"
CLOSE   = "</" + "script>"
ESCAPED = "<\\/" + "script>"

tpl = io.open(SRC, encoding="utf-8").read()

def check(cond, label):
    print(("  ok  " if cond else " FAIL ") + label)
    if not cond:
        sys.exit(1)


# PANEL GUARD: the tab marked aria-selected must have a panel that is NOT hidden,
# or the page opens blank (this shipped once).
import re as _re
_sel = _re.search(r'id="tab-([a-z]+)"[^>]*aria-selected="true"', tpl)
assert _sel, "no tab is marked selected"
_pid = 'id="p-%s"' % _sel.group(1)
_panel = _re.search(r'<div class="panel" ' + _re.escape(_pid) + r'[^>]*>', tpl)
assert _panel and 'hidden' not in _panel.group(0),     "the selected tab's panel (%s) must not be hidden" % _pid

print("template checks")
check(tpl.count(M_STATE) == 1, "one literal STATE marker (found %d)" % tpl.count(M_STATE))
check(tpl.count(M_SRC) == 1, "one literal SRC marker (found %d)" % tpl.count(M_SRC))
check(tpl.count(CLOSE) == 3, "three real closing script tags (found %d)" % tpl.count(CLOSE))
check(tpl.index(M_STATE) < tpl.index(M_SRC), "STATE marker precedes SRC marker")
check(tpl.count(ESCAPED) == 0, "no pre-escaped closing tags (found %d)" % tpl.count(ESCAPED))
# HIDDEN GUARD: `hidden` must be unconditional, or a later class rule with a
# display value silently reveals dialogs and badges (this has happened twice).
check('[hidden]{display:none !important}' in tpl, "global [hidden] rule carries !important")

# the self-source copy: identical to the template but with closing tags neutralised
stored = tpl.replace(CLOSE, ESCAPED)
check(CLOSE not in stored, "stored copy holds no parser-terminating tag")

# ---- the draw the page actually ships -------------------------------------
# This used to check a hardcoded list that had drifted years out of date, so it
# passed no matter what the template said. Read the real defaults instead: if a
# snapshot ever bakes in a draw that does not hold together, the build stops.
SIDE_NAMES = {2: ["n", "g"], 4: ["n", "g", "c", "d"]}

ROSTER = re.findall(r'\{id:"(\w+)",\s*name:"([^"]+)",\s*hcp:(\d+)\}', tpl)
assert len(ROSTER) == 16, "expected 16 players in the template, found %d" % len(ROSTER)
PLAYERS = [r[0] for r in ROSTER]
HCP = {r[0]: int(r[2]) for r in ROSTER}
NAME = {r[0]: r[1] for r in ROSTER}

MODE = int(re.search(r"var DEFAULT_MODE=(\d+);", tpl).group(1))
MU = re.search(r'var DEFAULT_MU=\[([^\]]*)\];', tpl).group(1)
MU = re.findall(r'"(\w+)"', MU)
TEAMS = dict(re.findall(r'(\w+):"(\w)"',
                        re.search(r"var DEFAULT_TEAMS=\{(.*?)\};", tpl, re.S).group(1)))
SLOTS = re.findall(r'"(\w+)"',
                   re.search(r"var DEFAULT_SLOTS=\[(.*?)\];", tpl, re.S).group(1))

allow = SIDE_NAMES[MODE]
per = 16 // MODE
check(sorted(SLOTS) == sorted(PLAYERS), "the default draw seats each player exactly once")
check(sorted(TEAMS) == sorted(PLAYERS), "every player has a side")
check(all(t in allow for t in TEAMS.values()), "no player sits on a side this mode lacks")
counts = {t: sum(1 for v in TEAMS.values() if v == t) for t in allow}
check(all(v == per for v in counts.values()),
      "%d a side (%s)" % (per, ", ".join("%s %d" % (t, counts[t]) for t in allow)))

check(len(MU) == 8 and all(c in allow for c in MU), "the pairing names real sides")
seen = {t: 0 for t in allow}
selfplay = False
for i in range(4):
    a, b = MU[i * 2], MU[i * 2 + 1]
    if a == b:
        selfplay = True
    seen[a] += 1
    seen[b] += 1
check(not selfplay, "no team is drawn against itself")
check(all(v == per // 2 for v in seen.values()),
      "each side appears in exactly %d tee times" % (per // 2))

bad = [i for i, pid in enumerate(SLOTS)
       if TEAMS.get(pid) != MU[(i // 4) * 2 + (0 if i % 4 < 2 else 1)]]
check(not bad, "every seat holds a player from its own side")

spread = max(sum(HCP[p] for p in PLAYERS if TEAMS[p] == t) for t in allow) - \
         min(sum(HCP[p] for p in PLAYERS if TEAMS[p] == t) for t in allow)
print("  ok  %d teams, handicap spread %d (%s)" % (
    MODE, spread,
    ", ".join("%s %d" % (t, sum(HCP[p] for p in PLAYERS if TEAMS[p] == t)) for t in allow)))

state = {"v": 7, "mode": MODE, "matchups": MU, "teams": TEAMS, "slots": SLOTS,
         "locked": False, "roster": {},
         "gross": {p: [None] * 18 for p in PLAYERS}}
blob = json.dumps(state, separators=(",", ":"))

out = tpl.replace(M_STATE, blob, 1).replace(M_SRC, stored, 1)

print("output checks")
check(out.count(CLOSE) == 3, "output still closes exactly three script tags (found %d)" % out.count(CLOSE))
check(out.count(M_STATE) == 1, "output keeps one STATE slot for the next generation")
check(out.count(M_SRC) == 1, "output keeps one SRC slot for the next generation")

# round trip: reproduce what buildPage() does in the browser
open_tag = '<script id="src" type="text/plain">'
a = out.index(open_tag) + len(open_tag)
b = out.index(CLOSE, a)
recovered_stored = out[a:b]
check(recovered_stored == stored, "#src content survives HTML embedding byte-for-byte")
recovered_tpl = recovered_stored.replace(ESCAPED, CLOSE)
check(recovered_tpl == tpl, "unescaping #src reproduces the template exactly")

# and one more generation, to prove the fixed point holds: the same state in must
# give the same bytes out, so the page can republish itself indefinitely
gen2 = recovered_tpl.replace(M_STATE, blob, 1).replace(M_SRC, recovered_stored, 1)
check(gen2 == out, "a second regeneration is byte-identical (stable fixed point)")

# a DIFFERENT state must change only the state slot, never the embedded source
moved = dict(state)
moved["gross"] = dict(state["gross"])
moved["gross"][PLAYERS[0]] = [4] + [None] * 17
blob2 = json.dumps(moved, separators=(",", ":"))
gen3 = recovered_tpl.replace(M_STATE, blob2, 1).replace(M_SRC, recovered_stored, 1)
a = gen3.index('<script id="src" type="text/plain">')
b = gen3.index(CLOSE, a)
check(gen3[a:b] == out[out.index('<script id="src" type="text/plain">'):
                       out.index(CLOSE, out.index('<script id="src" type="text/plain">'))],
      "a score change leaves the embedded source untouched")

io.open(OUT, "w", encoding="utf-8", newline="").write(out)
print("\nwrote %s  (%.1f KB)" % (OUT, len(out.encode("utf-8")) / 1024.0))
