import io, sys

f = 'template.html'
s = io.open(f, encoding='utf-8').read()

def sub(a, b, label, n=1):
    global s
    assert a in s, "MISSING: " + label
    s = s.replace(a, b, n)

# ---- 1. state carries a roster of overrides, not a single spare seat ----
sub('''  var sub=raw.sub&&typeof raw.sub==="object"?raw.sub:{};
  var sname=typeof sub.name==="string"?sub.name.trim().slice(0,28):"";
  var shcp=(typeof sub.hcp==="number"&&isFinite(sub.hcp))?Math.max(0,Math.min(40,Math.round(sub.hcp))):BY[SUB_ID].hcp;

  return {v:4, teams:teams, slots:reconcile(slots,teams), locked:raw.locked===true,
          sub:{name:sname,hcp:shcp}, gross:gross};
})();

/* push the open seat's saved name and handicap onto the roster entry, so every
   display and every stroke calculation picks them up with no special-casing */
function applySub(){
  BY[SUB_ID].name=state.sub.name||"TBD";
  BY[SUB_ID].hcp=state.sub.hcp;
  applyHcp();
}
applySub();
function subNamed(){ return !!state.sub.name; }''',
'''  var rr=raw.roster&&typeof raw.roster==="object"?raw.roster:{};
  var roster={};
  P.forEach(function(p){
    var o=rr[p.id];
    if(o&&typeof o==="object") roster[p.id]={name:o.name,hcp:o.hcp};
  });
  /* an older save carried only the spare seat, under `sub` */
  if(!raw.roster&&raw.sub&&typeof raw.sub==="object") roster.p16={name:raw.sub.name,hcp:raw.sub.hcp};

  return {v:5, teams:teams, slots:reconcile(slots,teams), locked:raw.locked===true,
          roster:roster, gross:gross};
})();

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
applyRoster();''', "state + applyRoster")

# ---- 2. markup: editable roster replaces the sixteenth-player box ----
start = s.index('    <div class="card">\n      <div class="card-h"><h2>The sixteenth player</h2>')
end   = s.index('    <div class="card">\n      <div class="card-h"><h2>The two sides</h2>')
sub(s[start:end], '''    <div class="card">
      <div class="card-h"><h2>Players</h2><span class="tag" id="rosterTag"></span></div>
      <div class="card-b flush"><div class="rlist" id="rosterList"></div></div>
      <div class="savebar static">
        <span class="cnt" id="rosterMsg"></span>
        <button class="btn ghost sm" id="revertRosterBtn">Revert</button>
        <button class="btn sm" id="saveRosterBtn">Save players</button>
      </div>
      <div class="msg" id="rosterHint">Type over any name or handicap. Above 18 gives a second stroke on the lowest-index holes.</div>
    </div>

''', "roster card markup")

# ---- 3. renderSub becomes renderRoster ----
sub('''function renderSub(){
  var editable=!state.locked&&!readOnly&&!saving;
  var nm=byId("subName"), hc=byId("subHcp");
  if(document.activeElement!==nm) nm.value=state.sub.name;
  if(document.activeElement!==hc) hc.value=String(state.sub.hcp);
  nm.disabled=!editable; hc.disabled=!editable;
  byId("saveSubBtn").disabled=!editable;
  var tag=byId("subTag");
  tag.textContent=subNamed()?(state.sub.name+" · "+state.sub.hcp):"open · playing off "+state.sub.hcp;
  tag.className="tag"+(subNamed()?"":" bad");
}''',
'''var rosterDraft={};
function seedRosterDraft(){
  rosterDraft={};
  P.forEach(function(p){ rosterDraft[p.id]={name:p.name,hcp:p.hcp}; });
}
seedRosterDraft();
function rosterDirty(){
  return P.some(function(p){
    var d=rosterDraft[p.id];
    return !d||d.name!==p.name||d.hcp!==p.hcp;
  });
}
function rosterBadCount(){
  return P.filter(function(p){
    var h=rosterDraft[p.id]&&rosterDraft[p.id].hcp;
    return !(typeof h==="number"&&isFinite(h)&&h>=0&&h<=40);
  }).length;
}
function markRoster(){
  var dirty=rosterDirty(), editable=!state.locked&&!readOnly&&!saving, bad=rosterBadCount();
  byId("saveRosterBtn").disabled=!editable||!dirty||bad>0;
  byId("revertRosterBtn").disabled=!editable||!dirty;
  byId("rosterTag").textContent=P.length+" players";
  var m=byId("rosterMsg");
  if(readOnly) m.textContent="View only on this device.";
  else if(state.locked) m.textContent="Locked.";
  else if(bad) m.textContent="Handicaps must be 0 to 40.";
  else if(dirty) m.textContent="Unsaved on this device.";
  else m.textContent="Everyone is seeing this roster.";
}
function renderRoster(){
  var editable=!state.locked&&!readOnly&&!saving;
  var list=byId("rosterList");
  var focus=document.activeElement;
  var keep=(focus&&focus.getAttribute)?focus.getAttribute("data-rid"):null;
  list.textContent="";
  P.slice().sort(function(a,b){ return a.hcp-b.hcp||a.name.localeCompare(b.name); })
   .forEach(function(p){
    var d=rosterDraft[p.id]||{name:p.name,hcp:p.hcp};
    var row=el("div","rrow"+((d.name!==p.name||d.hcp!==p.hcp)?" changed":""));
    var nm=document.createElement("input");
    nm.type="text"; nm.maxLength=28; nm.value=d.name; nm.autocomplete="off";
    nm.setAttribute("data-rid",p.id+":name");
    nm.setAttribute("aria-label","Name for "+p.name);
    nm.disabled=!editable;
    nm.addEventListener("input",function(){ rosterDraft[p.id].name=nm.value; row.className="rrow changed"; markRoster(); });
    var hc=document.createElement("input");
    hc.type="number"; hc.className="rhcp"; hc.min="0"; hc.max="40"; hc.step="1";
    hc.inputMode="numeric"; hc.value=String(d.hcp);
    hc.setAttribute("data-rid",p.id+":hcp");
    hc.setAttribute("aria-label","Handicap for "+p.name);
    hc.disabled=!editable;
    hc.addEventListener("input",function(){
      var v=parseInt(hc.value,10);
      rosterDraft[p.id].hcp=isFinite(v)?v:hc.value;
      row.className="rrow changed";
      markRoster();
    });
    row.appendChild(nm); row.appendChild(hc);
    list.appendChild(row);
  });
  if(keep){
    var back=list.querySelector('[data-rid="'+keep+'"]');
    if(back) back.focus();
  }
  markRoster();
}''', "renderSub -> renderRoster")

# ---- 4. every call site ----
s = s.replace('renderSub()', 'renderRoster()')

# ---- 5. replay understands a roster patch ----
sub('''  if(patch.sub&&(state.sub.name!==patch.sub.name||state.sub.hcp!==patch.sub.hcp)){
    state.sub={name:patch.sub.name,hcp:patch.sub.hcp};
    applySub();
    need=true;
  }''',
'''  if(patch.roster){
    var touched=false;
    P.forEach(function(p){
      var o=patch.roster[p.id];
      if(!o) return;
      var cur=state.roster[p.id]||{};
      if(cur.name!==o.name||cur.hcp!==o.hcp){
        state.roster[p.id]={name:o.name,hcp:o.hcp};
        touched=true;
      }
    });
    if(touched){ applyRoster(); seedRosterDraft(); need=true; }
  }''', "replay roster")

# ---- 6. save handler ----
start = s.index('byId("saveSubBtn").addEventListener("click",function(){')
anchor = s.index('commit({sub:{name:nm,hcp:hv}},"subMsg");')
end = s.index('});', anchor) + 4
sub(s[start:end], '''byId("saveRosterBtn").addEventListener("click",function(){
  if(saving||readOnly||state.locked||!rosterDirty()) return;
  if(rosterBadCount()){ msg("rosterHint","Handicaps must be whole numbers from 0 to 40.","err"); return; }
  var out={};
  P.forEach(function(p){
    var d=rosterDraft[p.id];
    out[p.id]={name:String(d.name||"").trim().slice(0,28)||BASE[p.id].name,
               hcp:Math.max(0,Math.min(40,Math.round(d.hcp)))};
  });
  state.roster=out;
  applyRoster();
  seedRosterDraft();
  render();
  commit({roster:out},"rosterHint");
});
byId("revertRosterBtn").addEventListener("click",function(){
  seedRosterDraft(); renderRoster();
  msg("rosterHint","Reverted to the saved roster.","");
});
''', "save handler")

# ---- 7. css ----
sub('.subrow{display:flex; gap:9px; align-items:flex-end; flex-wrap:wrap}',
'''.rlist{display:grid}
.rrow{display:grid; grid-template-columns:1fr 78px; gap:8px; align-items:center; padding:7px 14px; border-bottom:1px solid var(--line-2)}
.rrow:last-child{border-bottom:0}
.rrow input{height:42px; border:1px solid var(--line); border-radius:5px; background:var(--card); color:var(--ink); font-family:inherit; font-size:16px; padding:0 9px; min-width:0}
.rrow .rhcp{font-family:var(--mono); text-align:center; padding:0}
.rrow input:disabled{opacity:.6; cursor:default}
.rrow.changed input{border-color:var(--dirty); background:var(--dirty-bg)}
.rrow input::-webkit-outer-spin-button,.rrow input::-webkit-inner-spin-button{-webkit-appearance:none; margin:0}''', "roster css")

io.open(f, 'w', encoding='utf-8', newline='').write(s)

print("roster is now fully editable")
for dead in ['applySub', 'subNamed', 'SUB_ID', 'state.sub', 'subName', 'subHcp',
             'subTag', 'saveSubBtn', 'subMsg', 'renderSub']:
    n = s.count(dead)
    flag = "" if n == 0 else "  <-- still referenced"
    print("  %-12s %d%s" % (dead, n, flag))
