"""Derive the standalone website from template.html.

The artifact build keeps its state inside the page and republishes the whole
document. A real site can't work that way, so this swaps that layer for a
Firebase Realtime Database: per-hole writes (no whole-document conflicts) and a
live listener so every phone updates within a fraction of a second.
"""
import io, os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "template.html")
OUT  = os.path.join(HERE, "..", "index.html")
CFG  = os.path.join(HERE, "firebase-config.json")

s = io.open(SRC, encoding="utf-8").read()

def cut(a, b, label):
    """remove the region from the start of a to the start of b"""
    global s
    i = s.index(a); j = s.index(b)
    assert i < j, label
    s = s[:i] + s[j:]

def sub(a, b, label, count=1):
    global s
    assert s.count(a) >= 1, "MISSING: " + label
    s = s.replace(a, b, count)


# PANEL GUARD: the tab marked aria-selected must have a panel that is NOT hidden,
# or the page opens blank (this shipped once).
import re as _re
_sel = _re.search(r'id="tab-([a-z]+)"[^>]*aria-selected="true"', s)
assert _sel, "no tab is marked selected"
_pid = 'id="p-%s"' % _sel.group(1)
_panel = _re.search(r'<div class="panel" ' + _re.escape(_pid) + r'[^>]*>', s)
assert _panel and 'hidden' not in _panel.group(0),     "the selected tab's panel (%s) must not be hidden" % _pid

# ---------------------------------------------------------------- head/meta
sub('<title>8/29 Golf</title>',
    '<title>8/29 Golf</title>\n'
    '<meta name="description" content="Live net better-ball scoring for a 16-player one-round match.">\n'
    '<meta name="theme-color" content="#FFFFFF">\n'
    '<link rel="icon" href="data:image/svg+xml,'
    '%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E'
    '%3Ctext y=%2726%27 font-size=%2726%27%3E%E2%9B%B3%3C/text%3E%3C/svg%3E">',
    "head meta")

# the page no longer carries its own state, and no longer copies its own source
cut('<script id="state" type="application/json">%%STATE%%</script>\n', '\n<div class="stick">', "state block")
cut('<script id="src" type="text/plain">%%SRC%%</script>\n', '<script>\n(function(){', "src block")

# ---------------------------------------------------------------- live badge
sub('<span id="leadNote">No scores in yet.</span>',
    '<span id="leadNote">Connecting…</span>', "lead note")

# ---------------------------------------------------------------- state init
old_state_start = s.index('var state=(function(){')
old_state_end   = s.index('function teamOf(pid){')
sub(s[old_state_start:old_state_end], '''var DEFAULT_STATE={
  teams:DEFAULT_TEAMS,
  slots:DEFAULT_SLOTS,
  locked:false,
  roster:{},
  gross:{}
};
function blankGross(){
  var g={};
  P.forEach(function(p){
    var row=[];
    for(var h=0;h<18;h++) row.push(null);
    g[p.id]=row;
  });
  return g;
}
var state={v:7,mode:DEFAULT_MODE,matchups:defaultMatchupsFor(DEFAULT_MODE),teams:{},slots:[],locked:false,roster:{},gross:blankGross()};
P.forEach(function(p){ state.teams[p.id]=DEFAULT_TEAMS[p.id]||null; });
for(var _i=0;_i<NSLOT;_i++) state.slots.push(DEFAULT_SLOTS[_i]||null);

/* Names and handicaps are editable, so the built-in roster is only a default.
   Whatever is stored wins, per player, and strokes are recomputed from it. */
var BASE={};
P.forEach(function(p){ BASE[p.id]={name:p.name,hcp:p.hcp}; });
function applyRoster(){
  P.forEach(function(p){
    var o=state.roster[p.id]||{};
    p.name=(typeof o.name==="string"&&o.name.trim())?o.name.trim().slice(0,28):BASE[p.id].name;
    p.hcp=(typeof o.hcp==="number"&&isFinite(o.hcp))?Math.max(0,Math.min(40,Math.round(o.hcp))):BASE[p.id].hcp;
  });
  applyHcp();
}
applyRoster();

/* Fold a Realtime Database snapshot into local state. Firebase drops null
   entries and turns sparse arrays into objects, so both shapes are handled. */
function applyRemote(raw){
  raw=raw||{};
  state.mode=(raw.mode===4)?4:2;
  var allow=SIDES[state.mode];
  var rawMu=raw.matchups;
  var flatMu=Array.isArray(rawMu)?rawMu:(rawMu&&typeof rawMu==="object"
    ?[0,1,2,3,4,5,6,7].map(function(i){ return rawMu[String(i)]; }):null);
  var mu=flatMu?unflatten(flatMu,state.mode):null;
  state.matchups=matchupsValid(mu,state.mode)?mu:defaultMatchups(state.mode);
  var t=raw.teams||{};
  P.forEach(function(p){
    var v=t[p.id];
    state.teams[p.id]=(allow.indexOf(v)>=0)?v:null;
  });
  var sl=raw.slots||{};
  for(var i=0;i<NSLOT;i++){
    var id=Array.isArray(sl)?sl[i]:sl[String(i)];
    state.slots[i]=(typeof id==="string"&&BY[id])?id:null;
  }
  state.slots=reconcile(state.slots,state.teams,state.matchups);
  state.locked=raw.locked===true;
  var rr=raw.roster||{};
  state.roster={};
  P.forEach(function(p){
    var o=rr[p.id];
    if(o&&typeof o==="object") state.roster[p.id]={name:o.name,hcp:o.hcp};
  });

  var g=raw.gross||{};
  P.forEach(function(p){
    var row=g[p.id]||{}, out=[];
    for(var h=0;h<18;h++){
      var v=Array.isArray(row)?row[h]:row[String(h)];
      out.push((typeof v==="number"&&isFinite(v)&&v>0)?Math.round(v):null);
    }
    state.gross[p.id]=out;
  });
  applyRoster();
}

''', "state initialiser")

# ---------------------------------------------------------------- sync layer
old_pub_start = s.index('/* ---------- publish ---------- */')
old_pub_end   = s.index('/* ---------- wiring ---------- */')
sub(s[old_pub_start:old_pub_end], '''/* ---------- live sync ---------- */
var FB=null, online=false, everSynced=false;

function setConn(state2){
  /* "Live" is the quiet state: the badge shows nothing when connected. */
  setStatus(state2==="Live"?"":state2);
}

function commit(patch,msgId){
  if(!FB){
    msg(msgId,"Not connected \\u2014 these scores are only on this phone. Reload when you have signal.","err");
    return;
  }
  saving=true;
  refreshSaveBar(); refreshHoleMeta(); renderRoster(); renderTeams(); renderTeeSetup();
  msg(msgId,"Saving\\u2026","");

  /* One flat multi-path update. Two groups posting different holes touch
     different paths, so they cannot overwrite each other. */
  var up={};
  if(patch.wipe){
    /* one path, so a reset cannot land half-applied on anybody's phone */
    up["gross"]=null;
  }
  if(patch.cells){
    patch.cells.forEach(function(c){ up["gross/"+c.pid+"/"+c.hole]=c.val; });
  }
  if(patch.teams){
    P.forEach(function(p){ up["teams/"+p.id]=patch.teams[p.id]||null; });
  }
  if(patch.slots){
    for(var i=0;i<NSLOT;i++) up["slots/"+i]=patch.slots[i]||null;
  }
  if(typeof patch.locked==="boolean") up["locked"]=patch.locked;
  if(patch.mode) up["mode"]=patch.mode;
  if(patch.matchups){
    for(var mi=0;mi<8;mi++) up["matchups/"+mi]=patch.matchups[mi];
  }
  if(patch.roster){
    P.forEach(function(p){
      var o=patch.roster[p.id];
      if(!o) return;
      up["roster/"+p.id+"/name"]=o.name;
      up["roster/"+p.id+"/hcp"]=o.hcp;
    });
  }

  FB.update(up).then(function(){
    saving=false; snapshotSaved();
    repaintAll(); refreshSaveBar(); renderHole(true); renderRoster(); renderTeams(); renderTeeSetup();
    msg(msgId,"Saved. Every phone is updating.","ok");
  },function(err){
    saving=false;
    refreshSaveBar(); refreshHoleMeta(); renderRoster(); renderTeams(); renderTeeSetup();
    msg(msgId,"Could not save \\u2014 "+((err&&err.message)||"unknown error")+
      ". Your entries are still on screen; try again.","err");
  });
}

/* A remote change must not discard what this phone has typed but not posted. */
function onRemote(raw){
  var mine=editList();
  var teamsDirty=teamDraftDirty(), slotsDirty=slotDraftDirty();
  applyRemote(raw);
  snapshotSaved();
  mine.forEach(function(c){
    if(state.gross[c.pid]) state.gross[c.pid][c.hole]=c.val;
  });
  if(!teamsDirty) P.forEach(function(p){ teamDraft[p.id]=state.teams[p.id]; });
  if(!slotsDirty){
    slotDraft=state.slots.slice();
    /* the pairing draft has to follow the server too, or it keeps whatever the
       page happened to load with */
    muDraft=state.matchups.map(function(p){ return p.slice(); });
  }
  everSynced=true;
  render();
}

function resyncDrafts(){
  P.forEach(function(p){ teamDraft[p.id]=state.teams[p.id]; });
  slotDraft=state.slots.slice();
}

''', "publish -> sync")

# ---------------------------------------------------------------- boot
old_boot = s[s.index('if(typeof claude!=="undefined"'):s.index('})();\n</script>')]
sub(old_boot, '''/* ---------- boot ---------- */
window.__shootout={
  onRemote:onRemote,
  attach:function(api){
    FB=api;
    setConn("Live");
  },
  conn:function(up){
    online=up;
    setConn(up?(everSynced?"Live":"Live"):"Offline");
    if(!up) setConn("Offline");
  },
  seed:function(){ return {mode:DEFAULT_MODE,matchups:flatten(defaultMatchupsFor(DEFAULT_MODE)),
                           teams:DEFAULT_STATE.teams,slots:DEFAULT_STATE.slots,
                           locked:false}; },
  fail:function(m){
    setConn("Offline");
    msg("holeMsg","Could not reach the scoreboard \\u2014 "+m,"err");
  }
};
''', "boot block")

# ---------------------------------------------------------------- firebase glue
cfg = None
if os.path.exists(CFG):
    cfg = json.load(io.open(CFG, encoding="utf-8"))

cfg_js = json.dumps(cfg, indent=2) if cfg else "null"

glue = '''
<script type="module">
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import { getDatabase, ref, onValue, update, get }
  from "https://www.gstatic.com/firebasejs/10.12.5/firebase-database.js";

const CONFIG = %s;
const ROOM = "shootout";
const S = window.__shootout;

if (!CONFIG) {
  S.fail("this copy of the site has no database configured yet.");
} else {
  try {
    const app = initializeApp(CONFIG);
    const db  = getDatabase(app);
    const room = ref(db, ROOM);

    // seed the room once, the first time anybody opens it
    const snap = await get(room);
    if (!snap.exists()) await update(room, S.seed());

    S.attach({ update: (paths) => update(room, paths) });
    onValue(ref(db, ".info/connected"), (s) => S.conn(s.val() === true));
    onValue(room, (s) => S.onRemote(s.val()), (e) => S.fail(e.message));
  } catch (e) {
    S.fail(e.message);
  }
}
</script>
''' % cfg_js

sub('</body>\n</html>', glue + '</body>\n</html>', "firebase glue")

# ---------------------------------------------------------------- checks
assert '%%STATE%%' not in s and '%%SRC%%' not in s, "template markers must be gone"
assert 'claude.use' not in s, "artifact API must be gone"
assert 'sessionStorage' not in s, "pending-replay machinery must be gone"
assert 'buildPage' not in s, "self-publish must be gone"
assert s.count('</' + 'script>') == 2, "expected two scripts, got %d" % s.count('</' + 'script>')


# HIDDEN GUARD: `hidden` must be unconditional, or a later class rule with a
# display value silently reveals dialogs and badges (has happened twice).
assert '[hidden]{display:none !important}' in s,     "the global [hidden] rule must carry !important"

d = 0
css = s[s.index('<style>') + 7:s.index('</style>')]
for ch in css:
    if ch == '{': d += 1
    elif ch == '}': d -= 1
assert d == 0, "unbalanced CSS braces: %d" % d

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, "w", encoding="utf-8", newline="").write(s)
print("wrote %s  (%.1f KB)" % (OUT, len(s.encode("utf-8")) / 1024.0))
print("firebase config: %s" % ("embedded" if cfg else "NOT SET (drop firebase-config.json next to this script)"))
