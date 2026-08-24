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
    "stephen":"Stephen Wheatcroft","cain":"Cain Cody","towner":"Towner Webster",
    "p16":"TBD",
}
HCP = {"lee":2,"kallan":3,"alec":4,"camden":7,"johng":9,
       "will":12,"brett":12,"sam":12,"josh":12,"brady":12,"zach":12,"rob":12,
       "stephen":15,"cain":15,"towner":15,"p16":12}
IDS = list(HCP.keys())

SLOTS = ["alec","towner","lee","cain",
         "camden","rob","kallan","stephen",
         "johng","p16","will","brett",
         "sam","josh","brady","zach"]
TEAMS = {pid: ("n" if i % 4 < 2 else "g") for i, pid in enumerate(SLOTS)}

print("setup")
assert sum(PAR) == 72
assert sorted(SI) == list(range(1, 19)), "stroke indexes must be 1..18 exactly once"
print("  ok  par 72, stroke indexes 1-18 unique")

assert len(IDS) == 16 and sorted(SLOTS) == sorted(IDS)
assert "harrison" not in IDS and "collin" not in IDS
assert HCP["rob"] == 12
print("  ok  16 seats; Rob Wallace at 12 replaces Harrison; Collin removed")

n_h = sum(HCP[p] for p in IDS if TEAMS[p] == "n")
g_h = sum(HCP[p] for p in IDS if TEAMS[p] == "g")
assert sum(1 for t in TEAMS.values() if t == "n") == 8
assert sum(1 for t in TEAMS.values() if t == "g") == 8
print("  ok  sides 8 v 8, handicap %d v %d (gap %d)" % (n_h, g_h, abs(n_h - g_h)))

for i, pid in enumerate(SLOTS):
    assert TEAMS[pid] == ("n" if i % 4 < 2 else "g"), (i, pid)
print("  ok  every tee-time seat holds a player from its own side")

# strokes are the adjusted handicap, applied straight down the stroke index
def stroke_on(pid, h):
    return 1 if SI[h] <= HCP[pid] else 0

for pid in IDS:
    assert sum(stroke_on(pid, h) for h in range(18)) == min(HCP[pid], 18), pid
print("  ok  each player's stroke count equals their handicap")

# the par-3 situation CHANGED with the new handicaps: 15s now stroke on hole 15
par3 = [h for h in range(18) if PAR[h] == 3]
who = sorted({NAME[p] for p in IDS for h in par3 if stroke_on(p, h)})
holes = sorted({h + 1 for p in IDS for h in par3 if stroke_on(p, h)})
print("  ok  par-3 strokes now exist: holes %s, for %s" % (holes, ", ".join(who)))
assert holes == [15], holes
assert all(HCP[p] >= 15 for p in IDS for h in par3 if stroke_on(p, h))

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

io.open(os.path.join(HERE, "expected.json"), "w", encoding="utf-8").write(json.dumps({
    "ptsN": pts[0], "ptsG": pts[1],
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
    out = out.replace('<header class="board">', STUB + "\n" + '<header class="board">', 1)
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
