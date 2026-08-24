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

print("template checks")
check(tpl.count(M_STATE) == 1, "one literal STATE marker (found %d)" % tpl.count(M_STATE))
check(tpl.count(M_SRC) == 1, "one literal SRC marker (found %d)" % tpl.count(M_SRC))
check(tpl.count(CLOSE) == 3, "three real closing script tags (found %d)" % tpl.count(CLOSE))
check(tpl.index(M_STATE) < tpl.index(M_SRC), "STATE marker precedes SRC marker")
check(tpl.count(ESCAPED) == 0, "no pre-escaped closing tags (found %d)" % tpl.count(ESCAPED))

# the self-source copy: identical to the template but with closing tags neutralised
stored = tpl.replace(CLOSE, ESCAPED)
check(CLOSE not in stored, "stored copy holds no parser-terminating tag")

HCP = {"lee":2,"kallan":3,"alec":4,"camden":7,"johng":9,
       "will":12,"brett":12,"sam":12,"josh":12,"brady":12,"zach":12,"rob":12,
       "stephen":15,"cain":15,"towner":15,
       "p16":12}                       # the open sixteenth seat
PLAYERS = list(HCP.keys())
assert len(PLAYERS) == 16

# opening draw: an exactly even 83-v-83 split on the adjusted handicaps
SLOTS = ["alec","towner","lee","cain",
         "camden","rob","kallan","stephen",
         "johng","p16","will","brett",
         "sam","josh","brady","zach"]
assert sorted(SLOTS) == sorted(PLAYERS), "opening assignment must use each player once"

TEAMS = {pid: ("n" if i % 4 < 2 else "g") for i, pid in enumerate(SLOTS)}
n_h = sum(HCP[p] for p in PLAYERS if TEAMS[p] == "n")
g_h = sum(HCP[p] for p in PLAYERS if TEAMS[p] == "g")
assert sum(1 for t in TEAMS.values() if t == "n") == 8
assert sum(1 for t in TEAMS.values() if t == "g") == 8
check(n_h == g_h, "opening sides are level on handicap (%d v %d)" % (n_h, g_h))
for i, pid in enumerate(SLOTS):
    assert TEAMS[pid] == ("n" if i % 4 < 2 else "g"), i
print("  ok  8 a side, every seat holds its own side")

state = {"v": 4, "teams": TEAMS, "slots": SLOTS, "locked": False,
         "sub": {"name": "", "hcp": HCP["p16"]},
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
moved["gross"]["lee"] = [4] + [None] * 17
blob2 = json.dumps(moved, separators=(",", ":"))
gen3 = recovered_tpl.replace(M_STATE, blob2, 1).replace(M_SRC, recovered_stored, 1)
a = gen3.index('<script id="src" type="text/plain">')
b = gen3.index(CLOSE, a)
check(gen3[a:b] == out[out.index('<script id="src" type="text/plain">'):
                       out.index(CLOSE, out.index('<script id="src" type="text/plain">'))],
      "a score change leaves the embedded source untouched")

io.open(OUT, "w", encoding="utf-8", newline="").write(out)
print("\nwrote %s  (%.1f KB)" % (OUT, len(out.encode("utf-8")) / 1024.0))
