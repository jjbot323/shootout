import json, io, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
PAR = [5,4,3,4,5,3,4,4,4,4,5,4,3,5,3,4,4,4]
SI  = [10,2,18,14,6,16,8,4,12,5,3,11,17,9,15,13,1,7]

# adjusted handicaps as supplied; p16 is the open sixteenth seat
NAME = {
    "lee":"Lee Cooper","kallan":"Kallan Walters","alec":"Alec Bove",
    "camden":"Camden Cooper","johng":"John Gressett","will":"Will Hayward",
    "brett":"Brett Fair","sam":"Sam Brown","josh":"Josh John",
    "brady":"Brady Gayle","zach":"Zach Brantley","rob":"Rob Wallace",
    "stephen":"Stephen Wheatcroft","blake":"Blake Clifton","towner":"Towner Webster",
    "jack":"Jack Rohrman",
}
HCP = {"lee":2,"kallan":3,"alec":4,"camden":7,"johng":9,
       "will":12,"brett":12,"sam":12,"josh":12,"brady":12,"zach":12,"rob":12,
       "stephen":15,"blake":2,"towner":21,"jack":25}
IDS = list(HCP.keys())

SLOTS = ["alec","zach","kallan","stephen",
         "camden","will","johng","sam",
         "brett","josh","blake","towner",
         "lee","jack","brady","rob"]
TEAMS = {pid: ("n" if i % 4 < 2 else "g") for i, pid in enumerate(SLOTS)}

print("setup")
assert sum(PAR) == 72
assert sorted(SI) == list(range(1, 19)), "stroke indexes must be 1..18 exactly once"
print("  ok  par 72, stroke indexes 1-18 unique")

assert len(IDS) == 16 and sorted(SLOTS) == sorted(IDS)
assert "harrison" not in IDS and "collin" not in IDS and "cain" not in IDS and "p16" not in IDS
assert HCP["rob"] == 12 and HCP["blake"] == 2 and HCP["jack"] == 25
print("  ok  16 named players, no placeholder: Jack Rohrman 25 completes the field")

n_h = sum(HCP[p] for p in IDS if TEAMS[p] == "n")
g_h = sum(HCP[p] for p in IDS if TEAMS[p] == "g")
assert sum(1 for t in TEAMS.values() if t == "n") == 8
assert sum(1 for t in TEAMS.values() if t == "g") == 8
print("  ok  sides 8 v 8, handicap %d v %d (gap %d)" % (n_h, g_h, abs(n_h - g_h)))
assert abs(n_h - g_h) <= 2, "opening draw should be close"

for i, pid in enumerate(SLOTS):
    assert TEAMS[pid] == ("n" if i % 4 < 2 else "g"), (i, pid)
print("  ok  every tee-time seat holds a player from its own side")

# strokes are the adjusted handicap, applied straight down the stroke index
def stroke_on(pid, h):
    """A handicap over 18 wraps: one stroke everywhere plus a second inside the remainder."""
    return HCP[pid] // 18 + (1 if SI[h] <= HCP[pid] % 18 else 0)

for pid in IDS:
    got = sum(stroke_on(pid, h) for h in range(18))
    assert got == HCP[pid], (pid, HCP[pid], got)
print("  ok  each player's strokes equal their handicap, including over 18")
over = [NAME[p] for p in IDS if HCP[p] > 18]
if over:
    print("  ok  wrapping handicaps: %s" % ", ".join(over))

# the par-3 situation CHANGED with the new handicaps: 15s now stroke on hole 15
par3 = [h for h in range(18) if PAR[h] == 3]
who = sorted({NAME[p] for p in IDS for h in par3 if stroke_on(p, h)})
holes = sorted({h + 1 for p in IDS for h in par3 if stroke_on(p, h)})
print("  ok  par-3 strokes now exist: holes %s, for %s" % (holes, ", ".join(who)))
assert holes, "somebody should stroke on a par 3 now"

# ---- deterministic synthetic round ---------------------------------------
rng = random.Random(20260824)
gross = {}
for pid in IDS:
    row = []
    for h in range(18):
        bump = rng.choice([-1, 0, 0, 1, 1, 2]) + (1 if rng.random() < HCP[pid] / 26.0 else 0)
        row.append(max(1, PAR[h] + bump))
    gross[pid] = row

def net(pid, h): return gross[pid][h] - stroke_on(pid, h)

pts = [0.0, 0.0]
detail = []
for m in range(4):
    n = [SLOTS[m*4], SLOTS[m*4+1]]
    g = [SLOTS[m*4+2], SLOTS[m*4+3]]
    f = [0, 0]; b = [0, 0]
    for h in range(18):
        a, c = min(net(i, h) for i in n), min(net(i, h) for i in g)
        seg = f if h < 9 else b
        if a < c: seg[0] += 1
        elif c < a: seg[1] += 1
    won = [f[0] + b[0], f[1] + b[1]]
    mp = [0.0, 0.0]
    for arr, worth in ((f, 1), (b, 1), (won, 2)):
        if arr[0] > arr[1]: mp[0] += worth
        elif arr[1] > arr[0]: mp[1] += worth
        else: mp[0] += worth / 2.0; mp[1] += worth / 2.0
    pts[0] += mp[0]; pts[1] += mp[1]
    detail.append((m + 1, f, b, won, mp))

tot_net   = {p: sum(net(p, h) for h in range(18)) for p in IDS}
tot_gross = {p: sum(gross[p]) for p in IDS}
birdies   = {p: sum(1 for h in range(18) if gross[p][h] <= PAR[h] - 1) for p in IDS}

def side(t): return [p for p in IDS if TEAMS[p] == t]
agg_n = sum(sorted(tot_net[i] for i in side("n"))[:4])
agg_g = sum(sorted(tot_net[i] for i in side("g"))[:4])
bird_n = sum(birdies[i] for i in side("n"))
bird_g = sum(birdies[i] for i in side("g"))

def award(a, b, worth, low):
    if (a < b) if low else (a > b): return [worth, 0.0]
    if (b < a) if low else (b > a): return [0.0, worth]
    return [worth / 2.0, worth / 2.0]

def best_indiv(table, worth):
    lo = min(table.values())
    win = [i for i in IDS if table[i] == lo]
    n = sum(1 for i in win if TEAMS[i] == "n")
    g = len(win) - n
    p = [worth/2.0, worth/2.0] if n == g else ([worth, 0.0] if n > g else [0.0, worth])
    return lo, win, p

lo_net, wn, p_net = best_indiv(tot_net, 2)
lo_gr,  wg, p_gr  = best_indiv(tot_gross, 2)

bonuses = [
    ("Team aggregate", award(agg_n, agg_g, 4, True), "T1 %d / T2 %d" % (agg_n, agg_g)),
    ("Low net round",  p_net, "%s net %d" % (", ".join(NAME[i] for i in wn), lo_net)),
    ("Low gross round",p_gr,  "%s gross %d" % (", ".join(NAME[i] for i in wg), lo_gr)),
    ("Birdie count",   award(bird_n, bird_g, 2, False), "T1 %d / T2 %d" % (bird_n, bird_g)),
]
for _, bp, _ in bonuses:
    pts[0] += bp[0]; pts[1] += bp[1]

print("")
print("synthetic full round")
for no, f, b, won, mp in detail:
    print("  match %d  front %d-%d  back %d-%d  holes %d-%d  pts %s-%s"
          % (no, f[0], f[1], b[0], b[1], won[0], won[1], mp[0], mp[1]))
for label, bp, sub in bonuses:
    print("  %-16s %s-%s   (%s)" % (label, bp[0], bp[1], sub))
print("  TOTAL  Team 1 %s  Team 2 %s   (sum %s, must be 26)" % (pts[0], pts[1], pts[0] + pts[1]))
assert abs(pts[0] + pts[1] - 26) < 1e-9, pts

# ---- four teams: match points plus the low net round ---------------------
# Modelled from scratch rather than reusing the two-team path, so a mistake in
# the page's generalisation cannot be mirrored here.
FOUR = ["n", "g", "c", "d"]
four_team = {}
for i, pid in enumerate(IDS):
    four_team[pid] = FOUR[i // 4]
MU4 = [("n", "g"), ("c", "d"), ("n", "c"), ("g", "d")]

# every team meets two others, never itself
seen4 = {t: 0 for t in FOUR}
for a, b in MU4:
    assert a != b, "a team cannot play itself"
    seen4[a] += 1
    seen4[b] += 1
assert all(v == 2 for v in seen4.values()), seen4
print("  ok  four-team draw: each team in exactly 2 tee times, never itself")

four_pts = {t: 0.0 for t in FOUR}

# seat the draw the way the page does: two from each side of each pairing
taken, slots4 = set(), []
for a, b in MU4:
    for t in (a, b):
        pick = [p for p in IDS if four_team[p] == t and p not in taken][:2]
        assert len(pick) == 2
        for p in pick:
            taken.add(p)
            slots4.append(p)
assert len(slots4) == 16 and len(set(slots4)) == 16

for m, (ta, tb) in enumerate(MU4):
    A = slots4[m * 4:m * 4 + 2]
    B = slots4[m * 4 + 2:m * 4 + 4]
    assert all(four_team[p] == ta for p in A) and all(four_team[p] == tb for p in B)
    f, b_ = [0, 0], [0, 0]
    for h in range(18):
        a_net = min(net(p, h) for p in A)
        b_net = min(net(p, h) for p in B)
        seg = f if h < 9 else b_
        if a_net < b_net: seg[0] += 1
        elif b_net < a_net: seg[1] += 1
    won = [f[0] + b_[0], f[1] + b_[1]]
    mp = [0.0, 0.0]
    for seg in (f, b_):
        if seg[0] > seg[1]: mp[0] += 1
        elif seg[1] > seg[0]: mp[1] += 1
        else: mp[0] += 0.5; mp[1] += 0.5
    if won[0] > won[1]: mp[0] += 2
    elif won[1] > won[0]: mp[1] += 2
    else: mp[0] += 1; mp[1] += 1
    four_pts[ta] += mp[0]
    four_pts[tb] += mp[1]

match_total = sum(four_pts.values())
assert abs(match_total - 16) < 1e-9, four_pts

# the low net round pays 2, to the side holding the most of the tied low rounds
lo4 = min(tot_net.values())
win4 = [i for i in IDS if tot_net[i] == lo4]
cnt4 = {t: sum(1 for i in win4 if four_team[i] == t) for t in FOUR}
top4 = max(cnt4.values())
tied4 = [t for t in FOUR if cnt4[t] == top4]
for t in tied4:
    four_pts[t] += 2.0 / len(tied4)

print("")
print("four-team round (match points + low net round)")
for t in FOUR:
    print("  Team %d  %s" % (FOUR.index(t) + 1, four_pts[t]))
print("  Low net round    2 to %s   (%s net %d)"
      % (", ".join("Team %d" % (FOUR.index(t) + 1) for t in tied4),
         ", ".join(NAME[i] for i in win4), lo4))
print("  TOTAL  %s   (16 match + 2 feat, must be 18)" % sum(four_pts.values()))
assert abs(sum(four_pts.values()) - 18) < 1e-9, four_pts

io.open(os.path.join(HERE, "expected.json"), "w", encoding="utf-8").write(json.dumps({
    "ptsN": pts[0], "ptsG": pts[1],
    "four": {"teams": four_team, "matchups": [t for pair in MU4 for t in pair],
             "slots": slots4, "pts": four_pts,
             "gross": {i: gross[i] for i in IDS}},
    "aggN": agg_n, "aggG": agg_g, "birdN": bird_n, "birdG": bird_g,
    "loNet": lo_net, "loGross": lo_gr,
    "matches": [{"no": no, "f": f, "b": b, "won": won, "pts": mp} for no, f, b, won, mp in detail],
    "indiv": sorted([{"id": i, "gross": tot_gross[i], "net": tot_net[i],
                      "toPar": tot_net[i] - 72} for i in IDS],
                    key=lambda r: (r["toPar"], r["id"])),
}, indent=1, sort_keys=True))

# ---- emit test pages -----------------------------------------------------
M_STATE, M_SRC = "%%" + "STATE" + "%%", "%%" + "SRC" + "%%"
CLOSE, ESCAPED = "</" + "script>", "<\\/" + "script>"
tpl = io.open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
stored = tpl.replace(CLOSE, ESCAPED)
STUB = ('<script>window.claude={use:function(n){return Promise.resolve('
        'n==="artifact"?{publish:function(h){window.__pub=h;window.__pubs='
        '(window.__pubs||0)+1;return Promise.resolve({version:"t"});}}:null);}};' + CLOSE)

def emit(name, blob):
    out = tpl.replace(M_STATE, blob, 1).replace(M_SRC, stored, 1)
    out = out.replace('<div class="stick">', STUB + "\n" + '<div class="stick">', 1)
    io.open(os.path.join(HERE, name), "w", encoding="utf-8", newline="").write(out)

EMPTY = {p: [None]*18 for p in IDS}
OPEN  = {"name": "", "hcp": 12}
emit("test-full.html",  json.dumps({"v":4,"teams":TEAMS,"slots":SLOTS,"locked":False,"sub":OPEN,"gross":gross}, separators=(",", ":")))
emit("test-empty.html", json.dumps({"v":4,"teams":TEAMS,"slots":SLOTS,"locked":False,"sub":OPEN,"gross":EMPTY}, separators=(",", ":")))
emit("test-named.html", json.dumps({"v":4,"teams":TEAMS,"slots":SLOTS,"locked":False,
                                    "sub":{"name":"Gus Fletcher","hcp":8},"gross":EMPTY}, separators=(",", ":")))
emit("test-noteams.html", json.dumps({"v":4,"teams":{p:None for p in IDS},"slots":[None]*16,
                                      "locked":False,"sub":OPEN,"gross":EMPTY}, separators=(",", ":")))
# a v3 save with no `sub` key — the page must fall back to the roster default
emit("test-legacy.html", json.dumps({"v":3,"teams":TEAMS,"slots":SLOTS,"locked":False,"gross":gross}, separators=(",", ":")))
print("")
print("wrote test-full / -empty / -named / -noteams / -legacy, expected.json")
