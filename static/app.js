/* EduLearn SPA — hash-router; student + admin + public. */
const $app = document.getElementById('app');
const TOK = 'edulearn_tok', USR = 'edulearn_usr';

/* Storage that can never throw.
   Phones block localStorage inside a third-party frame (which is exactly how the app is
   previewed in a chat panel), and a blocked write used to abort the whole login. We probe
   once, then fall back to memory so signing in and progress still work for the session. */
const MEMSTORE = Object.create(null);
const PERSIST = (function(){
  try{
    const probe='__edulearn_probe__';
    window.localStorage.setItem(probe,'1');
    window.localStorage.removeItem(probe);
    return window.localStorage;
  }catch(e){ return null; }
})();
function storageWorks(){ return !!PERSIST; }
function lsGet(k){
  try{ if(PERSIST){ const v=PERSIST.getItem(k); if(v!==null && v!==undefined) return v; } }catch(e){}
  return (k in MEMSTORE) ? MEMSTORE[k] : null;
}
function lsSet(k,v){
  MEMSTORE[k]=String(v);                 // always keep a copy for this session
  try{ if(PERSIST) PERSIST.setItem(k,v); }catch(e){}
  return !!PERSIST;
}
function lsDel(k){
  try{ if(PERSIST) PERSIST.removeItem(k); }catch(e){}
  delete MEMSTORE[k];
}

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function jwtok(){return lsGet(TOK)||'';}
function store(ok){if(ok){lsDel(TOK);}}
async function api(path,opts={}){
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  if(opts.body && typeof opts.body!=='string') opts.body=JSON.stringify(opts.body);
  const t=jwtok();
  if(t) opts.headers['Authorization']='Bearer '+t;
  const r=await fetch(path,opts);
  let d={};try{d=await r.json();}catch(e){}
  if(!r.ok){ const err=d.error||('Request failed ('+r.status+')'); throw new Error(err);}
  return d;
}
function money(x){return Number(x||0).toLocaleString();}
function pct(a,b){return b?Math.round(a/b*100):0;}
function timeAgo(ts){const s=Math.floor((Date.now()/1000-(ts||0)));if(!ts)return'';if(s<60)return'just now';const m=s/60;if(m<60)return Math.floor(m)+'m';const h=m/60;if(h<24)return Math.floor(h)+'h';return Math.floor(h/24)+'d';}
function fmtDate(ts){if(!ts)return'';return new Date(ts*1000).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});}
function statusPill(st){
  const map={'Not Started':['pill-not','◌ Not started'],'In Progress':['pill-prog','▸ In progress'],
  'Quiz Failed':['pill-fail','✕ Failed'],'Review Required':['pill-rev','↻ Review'],'Completed':['pill-done','✓ Done'],
  'Units Complete':['pill-prog','✓ Units done'],'Exam Passed':['pill-done','Certified']};
  const m=map[st]||['pill-not',st];return `<span class="pill ${m[0]}">${m[1]}</span>`;
}

function topbar(user){
  return `<header class="topbar"><div class="wrap">
    <div class="brand"><div class="logo">EL</div>EduLearn</div>
    <nav class="navlinks">
      <a href="#/">Home</a>
      ${user?`<a href="#/dashboard">Dashboard</a><a href="#/ask">Ask</a><a href="#/certs">Certificates</a>
      <a href="#/verify">Verify</a><button class="navbtn" onclick="goLogout()">Log out</button>`
      :`<a href="#/verify">Verify a certificate</a><a class="btn btn-primary" href="#/register">Start Learning</a>`}
    </nav></div></header>`;
}
function goLogout(){lsDel(TOK);location.hash='#/';}
function currentUser(){try{return JSON.parse(lsGet(USR)||'null');}catch(e){return null;}}

const LETTERS=['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z'];

/* ============================ LANDING ============================ */
async function viewLanding(){
  let meta={grades:{},stats:{}};try{meta=await api('/api/meta');}catch(e){}
  const gs=[9,10,11,12];
  const subjShort={chem:'Chemistry',bio:'Biology',phys:'Physics',engl:'English',math:'Mathematics',agri:'Agriculture'};
  const st=meta.stats||{};
  const nums=(n)=>String(n||0).replace(/\B(?=(\d{3})+(?!\d))/g,',');
  const gradeBlocks = gs.map(g=>{
    const list=meta.grades[g]||[];
    const names=list.length?list.map(s=>`<span class="chip chip-dark">${subjShort[s.code]||s.name}</span>`).join(''):'<span class="muted" style="font-size:13px">Coming soon</span>';
    return `<div class="card click gradepick" onclick="goGrade(${g})">
      <div class="gradepick-head"><span class="gradepick-num">${g}</span><div>
        <h3 style="margin:0">Grade ${g}</h3>
        <div class="muted" style="font-size:12.5px">${list.length?list.length+(list.length===1?' subject':' subjects'):'Not available yet'}</div></div></div>
      <div style="margin-top:14px;display:flex;gap:6px;flex-wrap:wrap">${names}</div>
    </div>`;
  }).join('');

  $app.innerHTML = `
  ${topbar()}
  <section class="hero"><div class="wrap">
    <div class="herogrid">
      <div>
        <div class="eyebrow">Ethiopian secondary school · Grade 9–11</div>
        <h1>Study every lesson from your own textbooks — and prove it with a certificate.</h1>
        <p class="lede">EduLearn turns the MoE curriculum into a guided course: read a lesson, answer its
        questions, revise with flashcards, and sit a final examination when you are ready.</p>
        <div class="cta-row">
          <button class="btn btn-primary btn-lg" onclick="location.hash='#/register'">Create your free account</button>
          <button class="btn btn-outline btn-lg" onclick="scrollToId('how')">See how it works</button>
        </div>
        <div class="hero-note">No fees · Works on any phone · Your progress is saved as you go</div>
      </div>
      <div class="herocard">
        <div class="herocard-top"><b>Subject progress</b><span class="chip chip-dark">Biology · Grade 9</span></div>
        <div class="herocard-row"><span>Unit 1 — Introduction to Biology</span><span class="ok-tick">Done</span></div>
        <div class="herocard-row"><span>Unit 2 — Classification of Organisms</span><span class="ok-tick">Done</span></div>
        <div class="herocard-row active"><span>Unit 3 — Cells</span><span class="muted">Lesson 4 of 10</span></div>
        <div class="pbar" style="margin:12px 0 6px"><div class="pfill blue" style="width:64%"></div></div>
        <div class="muted" style="font-size:12.5px">64% complete · 4 assessments passed</div>
      </div>
    </div>
  </div></section>

  <div class="truststrip"><div class="wrap">
    <div class="trustitem"><b>${nums(st.subjects)}</b><span>subjects</span></div>
    <div class="trustitem"><b>${nums(st.lessons)}</b><span>lessons</span></div>
    <div class="trustitem"><b>${nums(st.questions)}</b><span>practice questions</span></div>
    <div class="trustitem"><b>${nums(st.flashcards)}</b><span>flashcards</span></div>
  </div></div>

  <section class="block"><div class="wrap">
    <h2 class="sec">Built on the Ethiopian curriculum</h2>
    <p class="sub">Every lesson comes from the Ministry of Education textbooks, kept whole — not summarised, not rewritten.</p>
    <div class="grid g3">
      <div class="card"><h3>Your textbook content</h3><p>Lesson titles follow the official units and sub-units, so what you study here matches what you are examined on in school.</p></div>
      <div class="card"><h3>10 questions per lesson</h3><p>Each lesson ends with its own assessment. Score 80% to pass, and see why every wrong answer was wrong.</p></div>
      <div class="card"><h3>Everything is saved</h3><p>Your progress, scores and certificates stay on your account, so you can continue on any phone.</p></div>
    </div>
  </div></section>

  <section class="block alt" id="how"><div class="wrap">
    <h2 class="sec">How it works</h2>
    <p class="sub">Four steps from your first lesson to a certificate you can show.</p>
    <div class="steps4">
      <div class="step4"><div class="step-num">1</div><b>Register</b><p>Your name, grade, school and phone number. It takes one minute.</p></div>
      <div class="step4"><div class="step-num">2</div><b>Choose a subject</b><p>Biology, Chemistry, Physics, Mathematics or English — unit by unit.</p></div>
      <div class="step4"><div class="step-num">3</div><b>Learn and practise</b><p>Read the lesson, take its questions, revise with flashcards, and repeat until you pass.</p></div>
      <div class="step4"><div class="step-num">4</div><b>Sit the final exam</b><p>Finish every unit to unlock a 125-question examination. Score 100 or more to earn your certificate.</p></div>
    </div>
  </div></section>

  <section class="block"><div class="wrap">
    <h2 class="sec">Choose your grade</h2>
    <p class="sub">Open a grade to see the subjects available to you.</p>
    <div class="grid g4">${gradeBlocks}</div>
  </div></section>

  <section class="block alt"><div class="wrap">
    <div class="certband">
      <div>
        <h2 class="sec" style="margin-bottom:8px">Finish with a certificate that can be verified</h2>
        <p class="sub" style="margin-bottom:0">Pass the final examination and you receive a certificate carrying your name,
        the subject, your score and a unique ID. Anyone — a school, a parent, an employer — can check it is genuine
        using that ID, without needing an account.</p>
        <div class="cta-row" style="margin-top:22px">
          <button class="btn btn-primary btn-lg" onclick="location.hash='#/register'">Start now</button>
          <button class="btn btn-ghost btn-lg" onclick="location.hash='#/verify'">Verify a certificate</button>
        </div>
      </div>
      <div class="certmini">
        <div class="certmini-in"><div class="certmini-seal">EL</div>
          <div class="certmini-title">Certificate of Completion</div>
          <div class="certmini-name">Student Name</div>
          <div class="certmini-sub">Biology · Grade 9</div>
          <div class="certmini-foot"><span>Score 108 / 125</span><span>ID CERT-2026-95834</span></div>
        </div>
      </div>
    </div>
  </div></section>

  <section class="block"><div class="wrap">
    <h2 class="sec">Questions students ask</h2>
    <p class="sub">Straight answers before you sign up.</p>
    <div class="faq">
      <details><summary>Does it cost anything?</summary><p>No. The lessons, assessments, flashcards and certificates are free to use.</p></details>
      <details><summary>Do I need a computer?</summary><p>No. The platform is built for a phone, and everything works on a normal mobile connection.</p></details>
      <details><summary>What happens if I fail a lesson?</summary><p>Nothing is lost. You see an explanation for every question you missed and can retake it as many times as you need. Only your best score counts.</p></details>
      <details><summary>Is this your own material, or the real textbook?</summary><p>The lessons are the Ministry of Education textbook content, organised lesson by lesson to match the official units.</p></details>
      <details><summary>Which grades are available?</summary><p>Grades 9, 10 and 11 are complete. Grade 12 is being added; you can register but its subjects are not published yet.</p></details>
    </div>
  </div></section>

  <div class="footer"><div class="wrap footer-grid">
    <div>
      <div class="brand" style="color:#fff"><div class="logo">EL</div>EduLearn</div>
      <p class="muted" style="color:#8fa3c8;margin-top:10px;max-width:340px">Interactive digital learning for Ethiopian
      secondary school students. Built on the MoE curriculum.</p>
    </div>
    <div><b style="color:#fff;font-size:13px">Learn</b>
      <div class="footer-links"><a href="#/register">Create account</a><a href="#/login">Sign in</a>
      <a onclick="scrollToId('how')">How it works</a></div></div>
    <div><b style="color:#fff;font-size:13px">Subjects</b>
      <div class="footer-links"><a onclick="goGrade(9)">Grade 9</a><a onclick="goGrade(10)">Grade 10</a>
      <a onclick="goGrade(11)">Grade 11</a></div></div>
    <div><b style="color:#fff;font-size:13px">Certificates</b>
      <div class="footer-links"><a href="#/verify">Verify a certificate</a>
      <a onclick="location.hash='#/register'">Get certified</a></div></div>
  </div>
  <div class="wrap" style="margin-top:22px;padding-top:16px;border-top:1px solid rgba(255,255,255,.12);font-size:12.5px;color:#8fa3c8">
    © ${new Date().getFullYear()} EduLearn · Learn → practise → certify
  </div></div>`;
  window.scrollTo(0,0);
}
function scrollToId(id){document.getElementById(id)?.scrollIntoView({behavior:'smooth'});}
function goGrade(g){ location.hash = currentUser()? '#/dashboard':'#/register'; }

/* ============================ AUTH ============================ */
function viewAuth(mode){
  const isReg = mode==='register';
  const already = currentUser();
  $app.innerHTML = `${topbar()}
  <div class="wrap" style="min-height:70vh">
    <div class="authcard fadein">
      <div style="text-align:center;margin-bottom:4px">
      <h2 style="margin:6px 0 2px">${isReg?'Create your student account':'Welcome back'}</h2>
      <p class="muted">${isReg?'Your registered name will appear on your certificate.':'Log in to continue learning.'}</p></div>
      <div id="authform"></div>
      <div class="err" id="autherr"></div>
      <div class="center mt8"><a href="#/${isReg?'login':'register'}">${isReg?'Already registered? Log in':'New student? Register'}</a></div>
      <div class="center muted" style="font-size:12px;margin-top:14px">🔒 Each student's progress & records are private to their account.</div>
    </div>
  </div>`;
  const f=document.getElementById('authform');
  if(isReg){
    f.innerHTML=`<div class="field"><label>Full Name</label><input class="input" id="fname" placeholder="e.g. Yared Tesfaye"></div>
      <div class="row2"><div class="field"><label>Grade</label><select class="input" id="fgrade"><option>9</option><option>10</option><option>11</option><option>12</option></select></div>
      <div class="field"><label>Age</label><input class="input" id="fage" type="number" min="9" max="99" placeholder="16"></div></div>
      <div class="field"><label>Phone Number</label><input class="input" id="fphone" placeholder="+2519XXXXXXXX"></div>
      <div class="field"><label>School</label><input class="input" id="fschool" placeholder="Your school name"></div>
      <div class="field"><label>Create a Password</label><input class="input" id="fpass" type="password" placeholder="Min 6 characters"></div>
      <button class="btn btn-primary" style="width:100%" onclick="doReg()">Create account &amp; start learning</button>`;
  }else{
    f.innerHTML=`<div class="field"><label>Phone Number</label><input class="input" id="fphone" placeholder="+2519XXXXXXXX"></div>
      <div class="field"><label>Password</label><input class="input" id="fpass" type="password"></div>
      <button class="btn btn-primary" style="width:100%" onclick="doLogin()">Log in</button>`;
  }
  window.scrollTo(0,0);
}
async function doReg(){
  const body={full_name:$app.querySelector('#fname').value,grade:+$app.querySelector('#fgrade').value,
    age:+($app.querySelector('#fage').value||0),phone:$app.querySelector('#fphone').value,
    school:$app.querySelector('#fschool').value,password:$app.querySelector('#fpass').value};
  try{const d=await api('/api/register',{method:'POST',body});onAuth(d);}
  catch(e){document.getElementById('autherr').textContent=e.message;}
}
async function doLogin(){
  const body={phone:$app.querySelector('#fphone').value,password:$app.querySelector('#fpass').value};
  try{const d=await api('/api/login',{method:'POST',body});onAuth(d);}
  catch(e){document.getElementById('autherr').textContent=e.message;}
}
function onAuth(d){
  try{lsSet(TOK,d.token);lsSet(USR,JSON.stringify(d.user));}catch(e){}
  location.hash='#/dashboard';
}

/* ============================ STUDENT APP ============================ */
function guard(){ if(!currentUser()){location.hash='#/login';return false;} return true; }

let _warnedNoStorage=false;
function storageNotice(){
  if(storageWorks()||_warnedNoStorage) return '';
  _warnedNoStorage=true;
  return `<p class="muted" style="font-size:13px">This window blocks saved data, so progress is kept
    only while you use the app.</p>`;
}
async function viewDashboard(){
  if(!guard())return;
  const d=await api('/api/dashboard'); const u=d.user; saveUser(u);
  const recent = d.recent.map(a=>`
    <div class="card" style="padding:12px 16px"><div style="display:flex;align-items:center;gap:10px">
      <span class="pill ${a.passed?'pill-done':'pill-fail'}">${a.correct}/${a.total}</span>
      <div style="flex:1"><div style="font-weight:600">${esc(a.label)}</div><div class="muted" style="font-size:12px">${a.percent}% · ${timeAgo(a.submitted_at)}</div></div></div></div>`).join('')||'<p class="muted">No assessments yet — start a lesson!</p>';
  const certs=d.certificates.map(c=>certCard(c)).join('')||'';
  const notifs=d.notifications.map(notifCard).join('');
  const subjects=d.subjects.length?d.subjects.map(s=>`
    <div class="card click" onclick="location.hash='#/subject/${s.id}'">
      <div style="display:flex;align-items:center;gap:10px">
        <div class="ic icon">${icon(s.code)}</div>
        <div style="flex:1"><div style="font-weight:700">${esc(s.name)}</div><div class="muted" style="font-size:12px">Grade ${u.grade}</div></div>
        ${statusPill(s.status)}</div>
      <div style="margin-top:10px"><div class="pbar"><div class="pfill blue" style="width:${s.pct}%"></div></div>
      <div class="muted" style="font-size:12px;margin-top:4px">${s.lessons_done}/${s.lessons_total} lessons · ${s.pct}%</div></div>
    </div>`).join(''):`<p class="muted">Subjects for Grade ${u.grade} are being added. Your account is ready.</p>`;

  $app.innerHTML = `${topbar(u)}
  <div class="wrap" style="padding-top:22px;padding-bottom:40px">
    <div class="crumb"><a href="#/">Home</a> › <b>Dashboard</b></div>
    ${storageNotice()}
    <div class="card" style="background:linear-gradient(135deg,#0f3d6b,#1b6aa8);color:#fff;border:none;margin-bottom:20px">
      <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
        <div style="width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,.18);display:grid;place-items:center;font-size:22px;font-weight:600;font-family:Georgia,serif;color:#fff;border:1px solid rgba(255,255,255,.4)">${initials(u.full_name)}</div>
        <div style="flex:1;min-width:220px"><div style="font-size:22px;font-weight:800">${esc(u.full_name)}</div>
        <div style="color:#cfe3f7">Grade ${u.grade} · ${esc(u.school||'—')}</div></div>
        <div style="text-align:center"><div style="font-size:30px;font-weight:800">${d.overall.pct}%</div><div style="color:#cfe3f7">overall progress</div></div>
      </div>
      <div class="pbar" style="background:rgba(255,255,255,.25);margin-top:14px"><div class="pfill" style="width:${d.overall.pct}%"></div></div>
      <div class="muted" style="color:#cfe3f7;font-size:12px;margin-top:4px">${d.overall.done}/${d.overall.total} lessons completed</div>
    </div>

    ${d.continue?`<button class="btn btn-amber" style="font-size:16px;width:100%;margin-bottom:20px" onclick="location.hash='#/lesson/${d.continue.id}'">
      ▶ Continue Learning — ${esc(d.continue.utitle)} › ${esc(d.continue.title)}</button>`:''}

    <div class="grid" style="grid-template-columns:2fr 1.4fr;align-items:start" id="dashGrid">
      <div>
        <h2 class="sec" style="font-size:22px">My subjects — Grade ${u.grade}</h2>
        <div class="grid" style="grid-template-columns:1fr 1fr">${subjects}</div>
        <h2 class="sec mt24" style="font-size:22px">Recent results</h2><div class="grid" style="gap:8px">${recent}</div>
      </div>
      <div>
        <div class="card" style="margin-bottom:16px"><h3 style="margin-top:0">Notifications ${d.notifications.filter(n=>!n.read).length?`<span class="pill pill-done">${d.notifications.filter(n=>!n.read).length} new</span>`:''}</h3>
          <a href="#/notifications" style="font-size:13px">View all</a>${notifs||'<p class="muted">No notifications.</p>'}</div>
        ${certs?`<div class="card"><h3 style="margin-top:0">Certificates of completion</h3>${certs}</div>`:''}
      </div>
    </div>
  </div>`;
  window.scrollTo(0,0);
}
function saveUser(u){lsSet(USR,JSON.stringify(u));}
function icon(code){return {chem:'Ch',bio:'Bi',phys:'Ph',engl:'En',math:'Ma',agri:'Ag'}[code]||'Su';}
function initials(name){const p=String(name||'').trim().split(/\s+/).filter(Boolean);return (p.length?p[0][0]:'?')+(p.length>1?p[p.length-1][0]:'');}


function notifCard(n){
  return `<div class="notif ${n.read?'':'unread'}" ${!n.read?`onclick="readNotif(${n.id},this)"`:''}>
    <div style="flex:1"><b>${esc(n.title)}</b><div style="font-size:13.5px">${esc(n.body)}</div>
    <div class="muted" style="font-size:11.5px">${timeAgo(n.created_at)}</div></div>${n.read?'':'<div class="dot">new</div>'}</div>`;
}
async function readNotif(id,el){el.classList.remove('unread');el.querySelector('.dot')?.remove();el.onclick=null;try{await api('/api/notifications/'+id+'/read',{method:'POST'});}catch(e){}}

function certCard(c){
  return `<div class="card click" style="padding:14px;margin-top:10px;border:1.5px solid var(--amber)" onclick="location.hash='#/cert/${c.cert_id}'">
    <div style="display:flex;gap:10px;align-items:center">
    <div><div style="font-weight:800;color:var(--brand)">${esc(c.sname||'')}</div>
    <div style="font-size:12px" class="muted">${c.cert_id} · ${fmtDate(c.issued_at)}</div></div></div></div>`;
}

async function viewNotifications(){
  if(!guard())return;const u=currentUser();
  const d=await api('/api/notifications');
  $app.innerHTML=`${topbar(u)}<div class="wrap" style="max-width:720px;padding-top:24px">
    <h2 class="sec">Notifications</h2>${d.notifications.map(notifCard).join('')||'<p class="muted">Nothing here yet.</p>'}</div>`;
}

/* ============================ SUBJECT ============================ */
async function viewSubject(id){
  if(!guard())return;const u=currentUser();
  const d=await api('/api/subject/'+id);
  const s=d.subject;
  const unlocked=d.progress && d.progress.final_unlocked;
  const examBtn=`<button class="btn ${unlocked?'btn-green':'btn-ghost'}" ${unlocked?'':'disabled'} style="margin-top:14px" onclick="location.hash='#/exam/${id}'">
    ${unlocked?'Take the 125-question final examination':'Final examination unlocks when all units are complete'}</button>`;
  const notesBtn=`<button class="btn btn-ghost" style="margin-top:14px" onclick="downloadNotes(${id},'${esc(d.subject.name)}')">⬇ Download the notes</button>`;
  const units=d.units.map(un=>{
    const uDone=un.done, uTot=un.total;
    const lessons=un.lessons.map(l=>{
      const st=l.status;
      const mark= st==='Completed'?'✓':st==='Quiz Failed'?'!':st==='Review Required'?'↻':st==='In Progress'?'▸':(l.number);
      const cls= st==='Completed'?'done':st==='Quiz Failed'?'fail':st==='In Progress'||st==='Review Required'?'cur':'';
      return `<div class="lesson" onclick="location.hash='#/lesson/${l.id}'">
        <div class="st ${cls}">${mark}</div>
        <div class="nm">Lesson ${l.number}. ${esc(l.title)}</div>
        ${l.best?`<span class="tl">best ${l.best}</span>`:''}${statusPill(st)}</div>`;
    }).join('');
    return `<div class="unit"><div class="head">
      <span class="pill ${un.completed?'pill-done':'pill-prog'}">${uDone}/${uTot}</span>
      <div class="tt">${esc(un.title)}</div>
      <div style="width:160px"><div class="pbar"><div class="pfill" style="width:${pct(uDone,uTot)}%"></div></div></div>
      <button class="btn btn-ghost btn-sm" onclick="downloadUnit(${un.id})">⬇ Unit PDF</button>
    </div><div class="lessons">${lessons}</div></div>`;
  }).join('');
  $app.innerHTML=`${topbar(u)}<div class="wrap" style="padding-top:20px;padding-bottom:50px">
    <div class="crumb"><a href="#/">Home</a> › <a href="#/dashboard">Dashboard</a> › <b>${esc(s.name)}</b></div>
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><div style="font-size:44px">${icon(s.code)}</div>
      <div style="flex:1"><h1 style="margin:0">Grade ${u.grade} ${esc(s.name)}</h1>
      <div class="muted">${esc(s.name)} lesson-by-lesson with quizzes, flashcards, and certification.</div></div>${statusPill(d.progress?d.progress.status:'Not Started')}</div>
    <div class="card mt16" style="padding:14px 18px"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <div style="font-weight:700">Subject progress</div><div style="flex:1;max-width:300px"><div class="pbar"><div class="pfill blue" style="width:${d.progress?pct(d.progress.lessons_done,d.progress.lessons_total):0}%"></div></div></div>
      <span class="muted">${d.progress?d.progress.lessons_done+'/'+d.progress.lessons_total+' lessons · '+d.progress.units_done+'/'+d.progress.units_total+' units':''}</span></div>
      ${notesBtn}
      ${examBtn}</div>
    <div class="unitlist mt24">${units}</div>
    <div class="card mt16"><b>Option B — Get the whole subject as a study pack</b>
      <p class="muted" style="margin:6px 0 0">Interactive lesson-by-lesson is the recommended learning path. You can also download each complete Unit as a clean PDF (button above) for offline revision.</p></div>
  </div>`;window.scrollTo(0,0);
}
async function downloadUnit(uid){const a=document.createElement('a');a.href='/api/unit/'+uid+'/pdf';a.download='';document.body.appendChild(a);a.click();a.remove();}

/* ============================ LESSON ============================ */
const LS_TAB='learn_tab';
async function viewLesson(id,tab){
  if(!guard())return;const u=currentUser();
  const d=await api('/api/lesson/'+id);
  const l=d.lesson;
  const qcount=d.quiz_count;
  const state=d.progress?d.progress.status:'Not Started';
  let active=tab||lsGet(LS_TAB)||'learn';
  // lock quiz until reviewed? Always allow but show state
  renderLesson(d,u,id,active,qcount,state);
}
async function renderLesson(d,u,id,active,qcount,state){
  const l=d.lesson;
  const tabs=[
    ['learn','Learn',`<h2 class="sec" style="font-size:20px">${esc(l.title)}</h2>
      <div class="lessonContent">${l.content_html}</div>
      <div class="card mt16"><b>Summary</b>
        <p class="muted">Read the lesson above, then use the flashcards to memorise key terms, and take the lesson assessment to check your understanding.</p></div>`],
    ['flash','Flashcards','<div id="fcholder" class="mt16">Loading flashcards…</div>'],
    ['quiz', qcount?`Assessment (${qcount} Q)`:'Assessment (pending)', qcount?`<div id="quizhost"></div>`:`<div class="card"><h3>Assessment pending</h3><p class="muted">High-quality assessment questions for this lesson are being prepared. Your teacher can add them from the admin panel.</p></div>`],
  ];
  const tabHtml=tabs.map(([k,lab])=>`<button class="subtab ${active===k?'on':''}" onclick="lessonTab(${id},'${k}')">${lab}</button>`).join('');
  $app.innerHTML=`${topbar(u)}
  <div class="wrap" style="padding-top:14px;padding-bottom:60px;max-width:920px">
    <div class="crumb"><a href="#/">Home</a> › <a href="#/dashboard">Dashboard</a> › <a href="#/subject/${l.subject_id}">${esc(l.subject)}</a> › <b>${esc(l.unit_title)}</b></div>
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <div style="flex:1;min-width:200px"><span class="muted" style="font-size:12px">UNIT ${l.unit_number} · LESSON ${l.number} OF ${d.unit.total}</span>
      <h1 style="margin:2px 0 0;font-size:26px">${esc(l.title)}</h1></div>${statusPill(state)}</div>
    <div class="pbar" style="margin:8px 0 14px"><div class="pfill blue" style="width:${Math.round((l.number-1)/d.unit.total*100)}%"></div></div>
    ${active==='learn'?`<div class="subtab on" style="display:none"></div>`:''}
    ${tabHtml}
    <div id="tabbody" class="mt8">${tabs.find(t=>t[0]===active)[2]}</div>
    <div style="display:flex;justify-content:space-between;margin-top:22px">
      ${d.prev?`<button class="btn btn-ghost" onclick="location.hash='#/lesson/${d.prev.id}'">← Previous</button>`:'<span></span>'}
      ${d.next?`<button class="btn btn-primary" onclick="location.hash='#/lesson/${d.next.id}'">Next lesson →</button>`:`<button class="btn btn-primary" onclick="location.hash='#/subject/${l.subject_id}'">Unit complete — view subject →</button>`}
    </div>
  </div>`;
  window.scrollTo(0,0);
  if(active==='flash')loadFlash(id);
  if(active==='quiz')loadQuiz(id);
}
function lessonTab(id,tab){lsSet(LS_TAB,tab);location.hash='#/lesson/'+id+'/'+tab;}

async function loadFlash(id){
  const host=document.getElementById('fcholder');let d;
  try{d=await api('/api/flashcards/'+id);}catch(e){host.innerHTML='<p class="muted">Could not load.</p>';return;}
  const f=d.flashcards;
  if(!f.length){host.innerHTML=`<div class="card"><b>Flashcards</b><p class="muted">Flashcards for this lesson are being prepared. Add them from the admin panel.</p></div>`;return;}
  let i=0;
  host.innerHTML=`<div style="max-width:560px;margin:0 auto">
    <div style="text-align:center" class="mb8"><span class="muted">Card <span id="fi">1</span> / ${f.length}</span> — tap card to flip</div>
    <div class="fcard-wrap" onclick="flipCard()"><div class="fcard" id="fc"><div class="face" id="fcf">${esc(f[0].front)}</div>
    <div class="face back" id="fcb">${esc(f[0].back)}</div></div></div>
    <div style="display:flex;justify-content:space-between;margin-top:18px">
      <button class="btn btn-ghost" onclick="fcPrev()">← Prev</button>
      <button class="btn btn-primary" onclick="fcNext()">Next →</button></div></div>`;
  window.__fc={f,i,show:false};
}
function fcCur(){const c=window.__fc;return c?c.f[c.i]:null;}
function flipCard(){const c=window.__fc;if(!c)return;const el=document.getElementById('fc');el.classList.toggle('flip');c.show=!c.show;}
function fcNext(){const c=window.__fc;if(!c)return;c.i=Math.min(c.i+1,c.f.length-1);c.show=false;renderFc();}
function fcPrev(){const c=window.__fc;if(!c)return;c.i=Math.max(c.i-1,0);c.show=false;renderFc();}
function renderFc(){const c=window.__fc;const el=document.getElementById('fc'),el2=el;el2.classList.remove('flip');
  document.getElementById('fcf').textContent=c.f[c.i].front;document.getElementById('fcb').textContent=c.f[c.i].back;
  document.getElementById('fi').textContent=c.i+1;}

async function loadQuiz(id){
  const host=document.getElementById('quizhost');
  host.innerHTML='<p class="muted">Loading assessment…</p>';
  let d;try{d=await api('/api/lesson/'+id+'/quiz');}catch(e){host.innerHTML='<p class="muted">Could not load assessment.</p>';return;}
  const qs=d.questions;
  if(!qs.length){host.innerHTML=`<div class="card"><b>Assessment</b><p class="muted">No approved questions yet. The teacher can add questions from the admin panel.</p></div>`;return;}
  window.__quiz={qs,sel:{},step:0,id};
  renderQuiz();
}
function renderQuiz(){
  const w=window.__quiz;const q=w.qs[w.step];const host=document.getElementById('quizhost');
  const sel=w.sel[q.id];
  const letter=LETTERS;
  const options=q.choices.map((c,idx)=>`<div class="opt ${sel===idx?'sel':''}" onclick="chooseQ(${q.id},${idx},this)">
    <span class="k">${letter[idx]}</span><div>${esc(c)}</div></div>`).join('');
  host.innerHTML=`<div class="qcard">
    <div style="display:flex;gap:8px;align-items:center"><span class="pill pill-prog">Question ${w.step+1} of ${w.qs.length}</span>
    <span class="muted" style="font-size:12px">${q.concept||''} · ${q.difficulty}</span></div>
    <h3 style="margin:10px 0 8px">${esc(q.prompt)}</h3>
    <div style="font-size:12px" class="muted">${q.qtype==='tf'?'True / False':''}</div>${options}
    <div class="err" id="qz_err"></div>
    <div style="display:flex;justify-content:space-between;margin-top:16px">
      <button class="btn btn-ghost" ${w.step===0?'disabled':''} onclick="quizNav(-1)">← Back</button>
      ${w.step===w.qs.length-1?`<button class="btn btn-primary" onclick="submitQuiz()">Submit assessment ✓</button>`
      :`<button class="btn btn-primary" onclick="quizNav(1)">Next →</button>`}
    </div></div>`;
}
function chooseQ(qid,idx){const w=window.__quiz;w.sel[qid]=idx;renderQuiz();}
function quizNav(d){const w=window.__quiz;if(w.step===0&&d<0)return;w.step=Math.max(0,Math.min(w.qs.length-1,w.step+d));renderQuiz();}
async function submitQuiz(){
  const w=window.__quiz;const id=w.id;
  const un={};for(const q of w.qs){un[q.id]=w.sel[q.id]==null?-1:w.sel[q.id];}
  let res;
  try{res=await api(`/api/lesson/${id}/submit`,{method:'POST',body:{answers:un}});}catch(e){alert(e.message);return;}
  showQuizResult(res);
}
function showQuizResult(res){
  const host=document.getElementById('quizhost');
  const wrongs=res.detail.filter(x=>!x.correct);
  if(res.passed){
    host.innerHTML=`<div class="center fadein" style="padding:20px 0">
      <h2>Lesson completed</h2>
      <p>You scored <b>${res.correct} / ${res.total}</b> (${res.percent}%), which meets the passing standard of 80%. This lesson is now recorded as complete.</p>
      <button class="btn btn-green mt16" onclick="location.reload()">Back to lesson</button></div>`;
  }else{
    const review=wrongs.map(x=>{
      const letter=LETTERS[x.chosen]??'—';
      const corrL=LETTERS[x.correct_index];
      return `<div class="qcard"><div style="font-weight:700">${esc(x.prompt)}</div>
        <div class="reviewbox err"><b>Your answer:</b> ${x.chosen>=0?letter+' — '+esc((x.choices||[])[x.chosen]):'Not answered'}</div>
        <div class="reviewbox"><b>Correct answer (${corrL}):</b> ${esc((x.choices||[])[x.correct_index])}<br><br><b>Why:</b> ${esc(x.explanation||'This was the concept covered in the lesson.')}</div></div>`;
    }).join('');
    const concepts=[...new Set(wrongs.map(x=>x.concept).filter(Boolean))];
    host.innerHTML=`<div class="center fadein"><h2>Lesson not yet passed</h2>
      <p>Score: <b>${res.correct} / ${res.total}</b> (${res.percent}%). The passing standard for this lesson is <b>80%</b>. You may retake the assessment until you pass.</p>
      ${concepts.length?`<p><b>Topics to review:</b> ${concepts.map(esc).join(' · ')}</p>`:''}
      <button class="btn btn-primary mt8" onclick="loadQuiz(${window.__quiz.id})">Retake the assessment</button></div>
      <h3 class="mt16">Assessment review — learn from your mistakes</h3>${review}`;
  }
}

/* ============================ FINAL EXAM ============================ */
async function viewExam(sid){
  if(!guard())return;const u=currentUser();
  try{await api('/api/subject/'+sid+'/exam');}catch(e){alert(e.message);location.hash='#/subject/'+sid;return;}
  // fetch questions
  const qd=await api(`/api/subject/${sid}/exam/questions`,{method:'POST',body:{}});
  const qs=qd.questions;
  window.__exam={qs,sel:{},step:0,sid,session:qd.session_id,needed:qd.needed};
  renderExam(u,sid,qs,qd.count);
}
function renderExam(u,sid,qs,count){
  const q=qs[window.__exam.step];const sel=window.__exam.sel[q.id];const letter=LETTERS;
  const options=q.choices.map((c,idx)=>`<div class="opt ${sel===idx?'sel':''}" onclick="examChoose(${q.id},${idx})"><span class="k">${letter[idx]}</span><div>${esc(c)}</div></div>`).join('');
  const answered=Object.keys(window.__exam.sel).length;
  $app.innerHTML=`${topbar(u)}<div class="wrap" style="max-width:820px;padding-top:16px;padding-bottom:60px">
    <div class="crumb"><a href="#/subject/${sid}">← Back to subject</a></div>
    <div class="card"><h2 style="margin:0 0 4px">Final Examination — Grade ${u.grade}</h2>
    <div class="muted">Comprehensive subject examination. Pass mark to certify: <b>${passMark()} / ${qs.length}</b>.</div>
    <div class="pbar mt8"><div class="pfill" style="width:${pct(answered,qs.length)}%"></div></div>
    <div style="display:flex;gap:14px;margin-top:6px"><span class="muted" style="font-size:13px">${answered} of ${qs.length} answered</span>
    <span style="font-size:13px" class="muted">Question ${window.__exam.step+1} of ${qs.length}</span></div></div>
    <div class="qcard"><h3>${esc(q.prompt)}</h3>${options}
      <div style="display:flex;justify-content:space-between;margin-top:16px">
        <button class="btn btn-ghost" ${window.__exam.step===0?'disabled':''} onclick="examNav(-1)">← Back</button>
        ${window.__exam.step===qs.length-1?`<button class="btn btn-primary" onclick="examSubmit()">Submit final examination ✓</button>`:`<button class="btn btn-primary" onclick="examNav(1)">Next →</button>`}
      </div></div></div>`;
  window.scrollTo(0,0);
}
function passMark(){const w=window.__exam;if(!w)return 100;const n=w.qs.length;return n>=125?100:Math.max(1,Math.round(n*0.8));}
function examChoose(qid,idx){window.__exam.sel[qid]=idx;renderExam(currentUser(),window.__exam.sid,window.__exam.qs,window.__exam.qs.length);}
function examNav(d){const w=window.__exam;w.step=Math.max(0,Math.min(w.qs.length-1,w.step+d));renderExam(currentUser(),w.sid,w.qs,w.qs.length);}
async function examSubmit(){
  const w=window.__exam;const un={};for(const q of w.qs)un[q.id]=w.sel[q.id]==null?-1:w.sel[q.id];
  let res;try{res=await api(`/api/subject/${w.sid}/exam/submit`,{method:'POST',body:{answers:un,session_id:w.session}});}catch(e){alert(e.message);return;}
  if(res.passed_cert){
    $app.innerHTML=`${topbar(currentUser())}<div class="wrap" style="max-width:700px;text-align:center;padding:30px 0">
      <h1>Subject completed</h1>
      <p>You scored <b>${res.correct}/${res.total}</b> (${res.percent}%) on the final examination, meeting the pass standard of ${res.needed}/${res.total}. Your certificate of completion is now issued.</p>
      <button class="btn btn-green mt8" onclick="location.hash='#/cert/${res.cert_id}'">View your certificate</button></div>`;
  }else{
    $app.innerHTML=`${topbar(currentUser())}<div class="wrap" style="max-width:700px;text-align:center;padding:30px 0">
      <h1>Certificate not issued</h1>
      <p>Your score was <b>${res.correct}/${res.total}</b> (${res.percent}%). To be certified you must score at least <b>${res.needed}/${res.total}</b> on the final examination.</p>
      <p class="muted">Review your subject lessons, revise with the flashcards, and attempt the final examination again.</p>
      <button class="btn btn-primary mt8" onclick="location.hash='#/subject/${w.sid}'">Review subject lessons</button></div>`;
  }
}

/* ============================ CERTIFICATES ============================ */
async function viewCerts(){
  if(!guard())return;const u=currentUser();
  const d=await api('/api/certificates');
  $app.innerHTML=`${topbar(u)}<div class="wrap" style="max-width:820px;padding-top:20px">
    <h2 class="sec">My certificates</h2>
    ${d.certificates.length?d.certificates.map(certCard).join(''):'<p class="muted">Complete a subject (all lessons + final exam at 100/125+) to earn your first certificate.</p>'}</div>`;
}
async function viewCert(id){
  const u=currentUser();
  const c=await api('/api/certificate/'+id);
  if(!c.valid){$app.innerHTML=`<div class="wrap">${topbar(u)}<p>Certificate not found.</p></div>`;return;}
  renderCertDoc(c.certificate,u);
}
function renderCertDoc(c,u){
  const date=fmtDate(c.issued_at);
  $app.innerHTML=`${topbar(u)}
  <div class="wrap" style="padding:18px 0"><div class="noprint" style="text-align:right;margin-bottom:8px">
    <button class="btn btn-primary" onclick="window.print()">Print / Save as PDF</button>
    <a class="btn btn-ghost" href="#/verify">Verify ID</a></div>
    <div class="cert-wrap fadein" id="certdoc">
      <div class="gold">★★★★★★★★★★</div>
      <div class="gold" style="margin-top:6px">— CERTIFICATE OF COMPLETION —</div>
      <h2>EduLearn</h2>
      <div class="muted">This certificate proudly certifies that</div>
      <div class="who">${esc(c.full_name)}</div>
      <div class="muted" style="max-width:520px;margin:0 auto">has successfully completed the <b>${esc(c.sname||'')}</b> subject, fulfilling all required lessons, unit assessments and the comprehensive final examination, and has thereby met the certification standard.</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:26px 0 8px;border-top:1px solid #eee;padding-top:18px">
        <div><b>Grade</b><br>Grade ${c.grade}</div>
        <div><b>Completion date</b><br>${date}</div>
        <div><b>Final score</b><br>${c.exam_score}/${c.exam_total}</div>
        <div><b>Certificate ID</b><br>${c.cert_id}</div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:30px">
        <div style="text-align:left"><div style="font-size:16px;font-family:Georgia,serif">_____</div><div class="muted" style="font-size:12px">Authorized signature</div></div>
        <div class="muted" style="font-size:11px">Verify at: <b>EduLearn · Certificate Verification</b></div>
        <div style="text-align:right"><div class="gold">★ EduLearn ★</div><div class="muted" style="font-size:12px">Digital Learning Platform</div></div>
      </div>
    </div>
  </div>`;
}
async function viewVerify(){
  $app.innerHTML=`${topbar()}<div class="wrap" style="max-width:560px;padding-top:30px"><div class="card">
    <h2>Verify a certificate</h2><p class="muted">Enter the unique Certificate ID shown on the certificate.</p>
    <input class="input" id="cid" placeholder="CERT-2026-00001"><button class="btn btn-primary mt8" style="width:100%" onclick="doVerify()">Verify</button>
    <div id="vr" class="mt8"></div></div></div>`;
}
async function doVerify(){
  const id=document.getElementById('cid').value.trim();const vr=document.getElementById('vr');
  const d=await api('/api/certificate/'+encodeURIComponent(id));
  if(d.valid){const c=d.certificate;
    vr.innerHTML=`<div class="card" style="border:2px solid var(--accent);background:#f2faf6"><b>✓ Valid certificate</b>
    <p class="muted" style="margin:6px 0">This certificate is authentic and was issued to <b>${esc(c.full_name)}</b> for completing <b>${esc(c.sname)}</b> (Grade ${c.grade}) on ${fmtDate(c.issued_at)} with a final score of ${c.exam_score}/${c.exam_total}.</p></div>`;
  }else{vr.innerHTML=`<div class="card" style="border:2px solid var(--danger)"><b>✕ Not found</b><p class="muted">No certificate matches this ID. Please double-check the ID.</p></div>`;}
}



/* download the original notes file for a subject */
async function downloadNotes(sid,sname){
  try{
    const d=await api('/api/notes?subject_id='+sid);
    const f=(d.files||[])[0];
    if(!f){alert('No notes file found for '+sname+'.');return;}
    const a=document.createElement('a');
    a.href='/api/notes/'+encodeURIComponent(f.name);
    a.download=f.name;document.body.appendChild(a);a.click();a.remove();
  }catch(e){alert(e.message||'Could not download the notes.');}
}

/* ============================ ASK (grounded tutor) ============================ */
async function viewAsk(){
  if(!guard())return;
  const u=currentUser();
  $app.innerHTML=`${topbar(u)}<div class="wrap">
    <div class="card" style="margin-top:18px">
      <h3 style="margin-top:0">Ask your notes</h3>
      <p class="muted" style="margin-top:0">Answers come only from your notes, with the lesson they came from.
      If something is not in your notes, the tutor says so instead of guessing.</p>
      <div class="field">
        <textarea class="input" id="askq" rows="2" placeholder="e.g. what is the difference between mitosis and meiosis?"></textarea>
      </div>
      <button class="btn btn-primary" onclick="askSend()">Ask</button>
      <span class="ok" id="askres"></span>
    </div>
    <div id="askout"></div>
  </div>`;
  const el=document.getElementById('askq');
  if(el)el.focus();
}

async function askSend(){
  const box=document.getElementById('askq');
  const q=(box?.value||'').trim();
  const out=document.getElementById('askout');
  const res=document.getElementById('askres');
  if(q.length<3){if(res)res.textContent='Type a question first.';return;}
  if(res)res.textContent='Searching your notes…';
  const u=currentUser()||{};
  try{
    const d=await api('/api/chat',{method:'POST',body:{question:q,grade:u.grade}});
    if(res)res.textContent='';
    if(d.not_covered){
      out.innerHTML=`<div class="card" style="border-left:6px solid var(--amber)">
        <b>Not covered in your notes</b>
        <p class="muted" style="margin:6px 0">I couldn't find this in your notes. Try asking it a different way,
        or check the lesson list for the topic.</p></div>`+out.innerHTML;
      return;
    }
    const cites=(d.sources||[]).map(s=>`<div class="lesson" style="margin-top:6px" onclick="location.hash='#/lesson/${s.lesson_id}'">
        <b>${esc(s.lesson)}</b><div class="muted" style="font-size:13px">${esc(s.unit)} · ${esc(s.subject)} · Grade ${s.grade} · tap to open</div></div>`).join('');
    out.innerHTML=`<div class="card" style="margin-top:14px">
        <div class="muted" style="font-size:13px;margin-bottom:6px">You asked: ${esc(q)}</div>
        <div style="white-space:pre-wrap;line-height:1.6">${esc(d.answer||'')}</div>
        <h4 style="margin-bottom:4px">Where this came from</h4>${cites}</div>`+out.innerHTML;
  }catch(e){
    if(res)res.textContent=e.message||'Something went wrong.';
  }
}

/* ============================ ROUTER ============================ */
async function route(){
  const h=location.hash||'#/';
  const parts=h.slice(2).split('/').filter(Boolean); // parts after '#/'
  try{
    if(h==='#/'||parts.length===0){return viewLanding();}
    if(parts[0]==='register')return viewAuth('register');
    if(parts[0]==='login')return viewAuth('login');
    if(parts[0]==='verify')return viewVerify();
    if(parts[0]==='dashboard')return viewDashboard();
    if(parts[0]==='notifications')return viewNotifications();
    if(parts[0]==='certs')return viewCerts();
    if(parts[0]==='ask')return viewAsk();
    if(parts[0]==='subject')return viewSubject(+parts[1]);
    if(parts[0]==='lesson')return viewLesson(+parts[1],parts[2]);
    if(parts[0]==='exam')return viewExam(+parts[1]);
    if(parts[0]==='cert')return viewCert(parts[1]);
    if(parts[0]==='admin' && parts[1]==='student')return admStudentDetail(+parts[2]);
    if(parts[0]==='admin' && parts[1]==='qedit')return admLessonQuestions(+parts[2]);
    if(parts[0]==='admin')return viewAdmin(parts[1]);
    if(parts[0]==='adminreg')return viewAdminLogin();
    return viewLanding();
  }catch(e){ showRouteError(e); }
}
function showRouteError(e){
  if(String(e.message).toLowerCase().includes('not authent')){location.hash='#/login';return;}
  $app.innerHTML=`${topbar()}<div class="wrap"><div class="card" style="margin-top:40px;border-left:6px solid var(--danger)"><b>Something went wrong</b>
  <p class="muted">${esc(e.message)}</p><button class="btn btn-primary" onclick="location.reload()">Reload</button></div></div>`;
}

/* ============================ ADMIN ============================ */
const ADMIN_TOK='edulearn_admin_tok';
async function viewAdminLogin(){
  $app.innerHTML=`${topbar()}<div class="wrap" style="max-width:460px;padding-top:40px"><div class="card">
    <h2>Administrator access</h2><p class="muted">Answer the security verification questions to continue. Incorrect answers will deny access.</p>
    <div class="field"><label>Administrator name</label><input class="input" id="q_name"></div>
    <div class="field"><label>Favorite color</label><input class="input" id="q_color"></div>
    <div class="field"><label>Number</label><input class="input" id="q_number"></div>
    <button class="btn btn-primary" style="width:100%" onclick="doAdminVerify()">Verify &amp; access admin</button>
    <div class="err" id="admerr"></div></div></div>`;
}
async function doAdminVerify(){
  const b={q_name:$app.querySelector('#q_name').value,q_color:$app.querySelector('#q_color').value,q_number:$app.querySelector('#q_number').value};
  try{const d=await api('/api/admin/verify',{method:'POST',body:b});
    lsSet(ADMIN_TOK,d.token);location.hash='#/admin/overview';}
  catch(e){document.getElementById('admerr').textContent=e.message;}
}
async function admApi(path,opts={}){
  opts.headers=Object.assign({'Content-Type':'application/json'},opts.headers||{});
  if(opts.body&&typeof opts.body!=='string')opts.body=JSON.stringify(opts.body);
  const t=lsGet(ADMIN_TOK)||'';
  opts.headers['Authorization']='Bearer '+t;
  const r=await fetch(path,opts);let d={};try{d=await r.json();}catch(e){}
  if(!r.ok)throw new Error(d.error||('err '+(r.status)));
  return d;
}
let ADM_SECTIONS=[['overview','Overview'],['students','Students'],['tree','Content'],['questions','Question bank'],['notifications','Notifications'],['certs','Certificates']];
async function viewAdmin(sect){
  if(!lsGet(ADMIN_TOK)){location.hash='#/adminreg';return;}
  sect=sect||'overview';
  const aside=ADM_SECTIONS.map(([k,l])=>`<button class="${k===sect?'on':''}" onclick="location.hash='#/admin/${k}'">${l}</button>`).join('');
  $app.innerHTML=`${topbar()}<div class="wrap" style="padding-top:18px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px"><h1 style="margin:0;font-size:24px">Admin Panel</h1>
      <span class="pill pill-done">Authorized</span><button class="btn btn-ghost btn-sm" style="margin-left:auto" onclick="logoutAdmin()">Log out</button></div>
    <div class="admingrid"><div class="aside">${aside}</div><div id="admb" class="fadein">Loading…</div></div></div>`;
  await admRenderSection(sect);
}
function logoutAdmin(){lsDel(ADMIN_TOK);location.hash='#/';}
async function admRenderSection(sect){
  const b=document.getElementById('admb');if(!b)return;
  if(sect==='overview')return admOverview(b);
  if(sect==='students')return admStudents(b);
  if(sect==='tree')return admTree(b);
  if(sect==='questions')return admQuestions(b);
  if(sect==='notifications')return admNotify(b);
  if(sect==='certs')return admCerts(b);
}
async function admOverview(b){
  const d=await admApi('/api/admin/overview');
  const top=d.top.map((t,i)=>`<tr><td>${i+1}. ${esc(t.name)}</td><td>${t.n} learners</td></tr>`).join('');
  const gd=d.grade_dist.map(g=>`<tr><td>Grade ${g.grade}</td><td>${g.n}</td></tr>`).join('');
  b.innerHTML=`<div class="statrow">
    <div class="stat"><div class="n">${d.total_students}</div><div class="l">Registered students</div></div>
    <div class="stat"><div class="n">${d.learning_now}</div><div class="l">Currently learning</div></div>
    <div class="stat"><div class="n">${d.completed_subjects}</div><div class="l">Subjects completed</div></div>
    <div class="stat"><div class="n">${d.certificates}</div><div class="l">Certificates issued</div></div>
    <div class="stat"><div class="n">${d.avg_quiz}%</div><div class="l">Avg lesson quiz</div></div>
    <div class="stat"><div class="n">${d.avg_exam}%</div><div class="l">Avg final exam</div></div>
  </div>
  <div class="grid" style="grid-template-columns:1fr 1fr;margin-top:20px">
    <div class="card"><h3 style="margin-top:0">Most studied subjects</h3><div class="tablewrap"><table class="data">${top||'<tr><td>No data yet</td></tr>'}</table></div></div>
    <div class="card"><h3 style="margin-top:0">Grade distribution</h3><div class="tablewrap"><table class="data">${gd||'<tr><td>No students yet</td></tr>'}</table></div></div>
  </div>`;
}
async function admStudents(b){
  b.innerHTML=`<div class="card" style="margin-bottom:12px"><h3 style="margin-top:0">Students</h3>
    <input class="input" style="max-width:320px" id="sq" placeholder="Search by name or phone"><button class="btn btn-primary btn-sm" onclick="searchStudents()">Search</button></div>
    <div class="tablewrap"><table class="data" id="stbl"><thead><tr><th>Name</th><th>Grade</th><th>Phone</th><th>School</th><th>Joined</th></tr></thead><tbody id="stbody"></tbody></table></div>`;
  await loadStudents();
}
async function loadStudents(q){
  const tb=document.getElementById('stbody');
  const d=await admApi('/api/admin/students?q='+encodeURIComponent(q||''));
  tb.innerHTML=d.students.map(s=>`<tr onclick="location.hash='#/admin/student/${s.id}'" style="cursor:pointer">
    <td><b>${esc(s.full_name)}</b></td><td>${s.grade}</td><td>${esc(s.phone)}</td><td>${esc(s.school||'—')}</td>
    <td class="muted">${fmtDate(s.created_at)}</td></tr>`).join('')||'<tr><td colspan="5">No students</td></tr>';
}
function searchStudents(){loadStudents(document.getElementById('sq').value);}
async function admStudentDetail(uid){
  const d=await admApi('/api/admin/student/'+uid);const s=d.student;
  $app.innerHTML=`${topbar()}<div class="wrap" style="padding-top:16px">
   <button class="btn btn-ghost btn-sm" onclick="location.hash='#/admin/students'">← Back to students</button>
   <div class="card mt8"><h2 style="margin:0">${esc(s.full_name)}</h2>
     <div class="muted">Grade ${s.grade} · ${esc(s.phone)} · ${esc(s.school||'—')} · ${s.age?('Age '+s.age):''} · Joined ${fmtDate(s.created_at)}</div></div>
   <div class="grid" style="grid-template-columns:1fr 1fr;margin-top:16px">
     <div class="card"><h3 style="margin-top:0">Subject progress</h3>
       ${d.subjects.map(o=>`<div style="margin:8px 0"><b>${esc(o.subject)}</b> — ${o.sp?o.sp.status+' · '+o.sp.lessons_done+'/'+o.sp.lessons_total+' lessons':'not started'}</div>`).join('')||'<p class="muted">No subjects started.</p>'}</div>
     <div class="card"><h3 style="margin-top:0">Certificates</h3>${d.certificates.map(c=>`<div>${esc(c.sname||'')} · ${c.cert_id} · ${fmtDate(c.issued_at)}</div>`).join('')||'<p class="muted">None yet.</p>'}</div>
   </div>
   <div class="card mt16"><h3 style="margin-top:0">Recent attempts</h3><div class="tablewrap"><table class="data">
   <tr><th>Scope</th><th>Score</th><th>%</th><th>Passed</th><th>When</th></tr>
   ${d.attempts.map(a=>`<tr><td>${a.scope}</td><td>${a.correct}/${a.total}</td><td>${a.percent}</td><td>${a.passed?'Yes':'No'}</td><td>${timeAgo(a.submitted_at)}</td></tr>`).join('')||'<tr><td colspan="5">No attempts</td></tr>'}
   </table></div></div></div>`;
}
async function admTree(b){
  const d=await admApi('/api/admin/tree');
  b.innerHTML=`<div class="card"><h3 style="margin-top:0">Content — Grade › Subject › Units › Lessons</h3>
    <div style="display:flex;flex-wrap:wrap;gap:10px">${d.tree.map(s=>`<button class="btn btn-ghost btn-sm" onclick="admSubTree(${s.id})">G${s.grade} ${esc(s.name)}</button>`).join('')}</div>
    <div id="subtree" class="mt16"></div></div>`;
  window.__admTree=d.tree;
}
function admSubTree(sid){
  const d=window.__admTree.find(s=>s.id===sid);const el=document.getElementById('subtree');
  el.innerHTML=`<h4>${esc(d.name)}</h4>${d.units.map(un=>`<div style="margin:8px 0"><b>${esc(un.title)}</b>
    <div class="muted" style="font-size:12px;margin-top:4px">${un.lessons.map(l=>`<a href="#/admin/qedit/${l.id}">${esc(l.title)}</a>`).join(' · ')}</div></div>`).join('')||'no units'}`;
}
async function admLessonQuestions(lid){
  if(!lsGet(ADMIN_TOK)){location.hash='#/adminreg';return;}
  const d=await admApi('/api/admin/questions?lesson_id='+lid);
  $app.innerHTML=`${topbar()}<div class="wrap" style="padding-top:16px">
   <button class="btn btn-ghost btn-sm" onclick="location.hash='#/admin/tree'">← Content</button>
   <h2>Quizzes — Lesson ${lid}</h2>
   <div class="gap8 mb8"><button class="btn btn-ghost btn-sm" onclick="admAddManual(${lid})">＋ Add question</button>
   <button class="btn btn-primary btn-sm" onclick="admGenLesson(${lid})">Regenerate from lesson</button></div>
   <div id="ql2">${d.questions.map(q=>`<div class="card" style="margin:8px 0">
     <div class="gap8"><span class="pill pill-prog">${q.status}</span><span class="pill pill-not">${q.qtype}</span>
     <span class="muted">#${q.id}</span></div><div style="font-weight:600">${esc(q.prompt)}</div>
     <div class="muted" style="font-size:12px">Answer: ${esc(q.answer)}</div>
     <div class="gap8 mt8"><button class="btn btn-ghost btn-sm" onclick="admEditQ(${q.id})">Edit</button>
     ${q.status!=='Approved'?`<button class="btn btn-green btn-sm" onclick="admApprove(${q.id})">✓ Approve</button>`:''}
     ${q.status!=='Rejected'?`<button class="btn btn-danger btn-sm" onclick="admReject(${q.id})">Reject</button>`:''}
     <button class="btn btn-danger btn-sm" onclick="admDeleteQ(${q.id})">Delete</button></div></div>`).join('')||'<p class="muted">No questions yet.</p>'}</div></div>`;
}
async function admGenLesson(lid){await admApi('/api/admin/generate/lesson/'+lid,{method:'POST'});admLessonQuestions(lid);}
function admAddManual(lid){
  const b=document.createElement('div');b.className='card';b.style.cssText='position:fixed;inset:0;background:rgba(15,30,50,.6);z-index:100;display:flex;align-items:center;justify-content:center';
  b.innerHTML=`<div style="background:#fff;max-width:620px;width:100%;border-radius:14px;padding:20px">
   <h3>Add question</h3>
   <div class="field"><label>Prompt</label><textarea class="input" id="nq_prompt" rows="2"></textarea></div>
   <div class="field"><label>Choices (one per line; first correct default)</label><textarea class="input" id="nq_ch" rows="4"></textarea></div>
   <div class="row2"><div class="field"><label>Correct choice #</label><input class="input" type="number" id="nq_ai" value="0"></div>
   <div class="field"><label>Difficulty</label><select class="input" id="nq_diff"><option>Easy</option><option selected>Medium</option><option>Hard</option></select></div></div>
   <div class="field"><label>Explanation</label><textarea class="input" id="nq_exp" rows="2"></textarea></div>
   <div class="field"><label>Concept</label><input class="input" id="nq_con"></div>
   <div class="gap8"><button class="btn btn-primary" onclick="admSaveManual(${lid})">Save</button>
   <button class="btn btn-ghost" onclick="this.closest('.card').remove()">Cancel</button></div></div>`;
  document.body.appendChild(b);
}
async function admSaveManual(lid){
  const choices=document.getElementById('nq_ch').value.split('\n').map(s=>s.trim()).filter(Boolean);
  const ai=+document.getElementById('nq_ai').value;
  const subj=dbgSubjectForLesson(lid);
  const body={lesson_id:lid,qtype:'mcq',prompt:document.getElementById('nq_prompt').value,choices:choices,
    answer:choices[ai]||'',answer_index:ai,difficulty:document.getElementById('nq_diff').value,
    explanation:document.getElementById('nq_exp').value,concept:document.getElementById('nq_con').value,
    status:'Needs Review',subject_id:subj};
  await admApi('/api/admin/question',{method:'POST',body});
  document.querySelector('.card').remove();admLessonQuestions(lid);
}
function dbgSubjectForLesson(lid){return null;}
async function admQuestions(b){
  b.innerHTML=`<div class="card"><h3 style="margin-top:0">Question bank review</h3><p class="muted">Filter by status. Generated items arrive as “AI Generated” → review → approve.</p>
   <div class="gap8"><label>Status</label><select class="input" style="max-width:220px" id="fstatus">
     <option value="">All</option><option>AI Generated</option><option>Needs Review</option><option>Approved</option><option>Rejected</option></select>
   <button class="btn btn-primary btn-sm" onclick="loadAdminQs()">Filter</button>
   <button class="btn btn-ghost btn-sm" onclick="admAddQ()">＋ Add question</button></div></div>
   <div id="qlist" class="mt16"></div>`;
  await loadAdminQs();
}
async function loadAdminQs(){
  const st=document.getElementById('fstatus')?.value||'';const ql=document.getElementById('qlist');
  ql.innerHTML='Loading…';
  const d=await admApi('/api/admin/questions?status='+encodeURIComponent(st));
  window.__qs=d.questions;
  ql.innerHTML=`<p>${d.questions.length} questions</p>`+d.questions.map((q,i)=>`
    <div class="card" style="margin:10px 0">
      <div class="gap8"><span class="pill pill-prog">${q.status}</span><span class="pill pill-not">${q.qtype}</span>
      <span class="muted" style="font-size:12px">#${q.id} · ${q.difficulty} · ${esc(q.concept||'')}</span></div>
      <div style="font-weight:600;margin:6px 0">${esc(q.prompt)}</div>
      <div class="muted" style="font-size:12px">Answers: ${q.answer} ${q.lesson_id?('· lesson '+q.lesson_id):''}</div>
      <div class="gap8 mt8">
        <button class="btn btn-ghost btn-sm" onclick="admEditQ(${q.id})">Edit</button>
        ${q.status!=='Approved'?`<button class="btn btn-green btn-sm" onclick="admApprove(${q.id})">✓ Approve</button>`:''}
        ${q.status!=='Rejected'?`<button class="btn btn-danger btn-sm" onclick="admReject(${q.id})">Reject</button>`:''}
        <button class="btn btn-ghost btn-sm" onclick="admDeleteQ(${q.id})">Delete</button>
      </div></div>`).join('')||'<p class="muted">No questions match.</p>';
}
async function admApprove(id){await admApi('/api/admin/question/'+id,{method:'PUT',body:{status:'Approved'}});loadAdminQs();}
async function admReject(id){await admApi('/api/admin/question/'+id,{method:'PUT',body:{status:'Rejected'}});loadAdminQs();}
async function admDeleteQ(id){await admApi('/api/admin/question/'+id,{method:'DELETE'});loadAdminQs();}
function admEditQ(id){const q=window.__qs.find(x=>x.id===id);
  const choices=q.choices?q.choices.map(c=>`<div class="field"><label>Choice</label><input class="input" value="${esc(c)}"></div>`).join(''):'';
  const box=document.createElement('div');box.className='card';box.style.cssText='position:fixed;inset:0;background:rgba(15,30,50,.6);z-index:100;display:flex;align-items:center;justify-content:center;padding:20px';
  box.innerHTML=`<div style="background:#fff;max-width:640px;width:100%;border-radius:14px;padding:20px;max-height:90vh;overflow:auto">
   <h3 style="margin-top:0">Edit question #${q.id}</h3>
   <div class="field"><label>Prompt</label><textarea class="input" rows="2" id="q_prompt">${esc(q.prompt)}</textarea></div>
   <div class="row2"><div class="field"><label>Type</label><input class="input" id="q_type" value="${esc(q.qtype)}"></div>
   <div class="field"><label>Difficulty</label><input class="input" id="q_diff" value="${esc(q.difficulty)}"></div></div>
   <div class="field"><label>Correct answer (index of correct choice)</label><input class="input" id="q_ai" type="number" value="${q.answer_index}"></div>
   <div class="field"><label>Explanation (why correct)</label><textarea class="input" rows="2" id="q_exp">${esc(q.explanation||'')}</textarea></div>
   <div class="field"><label>Concept</label><input class="input" id="q_con" value="${esc(q.concept||'')}"></div>
   <div id="chocs">${choices}</div>
   <div class="gap8"><button class="btn btn-primary" onclick="admSaveQ(${q.id})">Save</button>
   <button class="btn btn-ghost" onclick="this.closest('.card').remove()">Cancel</button></div></div>`;
  document.body.appendChild(box);
}
async function admSaveQ(id){
  const b=document.querySelector('#chocs');const choices=[...b.querySelectorAll('input')].map(i=>i.value);
  const body={prompt:document.getElementById('q_prompt').value,qtype:document.getElementById('q_type').value,
    difficulty:document.getElementById('q_diff').value,answer_index:+document.getElementById('q_ai').value,
    answer:choices[+document.getElementById('q_ai').value]||'',
    explanation:document.getElementById('q_exp').value,concept:document.getElementById('q_con').value,
    choices:choices,status:'Needs Review'};
  await admApi('/api/admin/question/'+id,{method:'PUT',body});[...document.querySelectorAll('.card')].forEach(c=>c.remove());loadAdminQs();
}
function admAddQ(){
  alert('To add a question, pick its lesson in the Content tree then use “Regenerate” or edit an existing AI-generated item. (Adding by hand: use the API.)');
}
async function admNotify(b){
  b.innerHTML=`<div class="card"><h3 style="margin-top:0">Send notification / announcement</h3>
    <div class="field"><label>Audience</label><select class="input" id="naud" onchange="naudChange()">
      <option value="all">All students</option><option value="grade">Specific grade</option><option value="subject">Students in a subject</option><option value="one">One student (ID)</option></select></div>
    <div class="field hide" id="nvrow"><label>Value</label><input class="input" id="nval" placeholder="e.g. grade 11, subject id, or student id"></div>
    <div class="field"><label>Title</label><input class="input" id="ntitle"></div>
    <div class="field"><label>Message</label><textarea class="input" id="nbody" rows="2"></textarea></div>
    <button class="btn btn-primary" onclick="sendNotif()">Send</button><div class="ok" id="nres"></div></div>
    <h3 class="mt24">Recent notifications</h3><div class="tablewrap"><table class="data"><tr><th>Title</th><th>Audience</th><th>Recipients</th><th>When</th></tr>
    <tbody id="nlist"></tbody></table></div>`;
  const d=await admApi('/api/admin/notifications');
  document.getElementById('nlist').innerHTML=d.notifications.map(n=>`<tr><td><b>${esc(n.title)}</b><br><span class="muted">${esc(n.body)}</span></td>
    <td>${n.audience}${n.audience_value?' '+esc(n.audience_value):''}</td><td>${n.recipients}</td><td>${timeAgo(n.created_at)}</td></tr>`).join('')||'';
}
function naudChange(){const v=document.getElementById('naud').value;document.getElementById('nvrow').classList.toggle('hide',v==='all');}
async function sendNotif(){
  const body={audience:document.getElementById('naud').value,audience_value:document.getElementById('nval')?.value||'',
    title:document.getElementById('ntitle').value,body:document.getElementById('nbody').value};
  try{const d=await admApi('/api/admin/notify',{method:'POST',body});
    document.getElementById('nres').textContent='Sent to '+d.recipients+' students.';}catch(e){document.getElementById('nres').textContent=e.message;}
}
async function admCerts(b){
  const d=await admApi('/api/admin/certificates');
  b.innerHTML=`<div class="card"><h3 style="margin-top:0">Certificate records</h3>
   <div class="tablewrap"><table class="data"><tr><th>Cert ID</th><th>Name</th><th>Subject</th><th>Grade</th><th>Score</th><th>Issued</th></tr>
   ${d.certificates.map(c=>`<tr><td><b>${esc(c.cert_id)}</b></td><td>${esc(c.full_name)}</td><td>${esc(c.sname)}</td>
     <td>${c.grade}</td><td>${c.exam_score}/${c.exam_total}</td><td>${fmtDate(c.issued_at)}</td></tr>`).join('')||'<tr><td colspan="6">No certificates yet</td></tr>'}</table></div></div>`;
}

/* route admin subpages */
async function viewAdmin2(parts){
  // handle admin/student/:id and admin/qedit
}

window.onhashchange = route;
document.addEventListener('DOMContentLoaded', ()=>route());
// expose functions
Object.assign(window,{goLogout,doReg,doLogin,lessonTab,loadFlash,flipCard,fcNext,fcPrev,
  chooseQ,quizNav,submitQuiz,examChoose,examNav,examSubmit,doVerify,readNotif,
  doAdminVerify,downloadUnit,searchStudents,loadAdminQs,admApprove,admReject,admDeleteQ,
  admEditQ,admSaveQ,admAddQ,admTree:admTree,admSubTree,sendNotif,naudChange,logoutAdmin,askSend,viewAsk,downloadNotes});
