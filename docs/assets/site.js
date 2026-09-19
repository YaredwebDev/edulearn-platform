/* EduLearn static edition - tabs, quiz engine, progress (localStorage) */
const EL = (() => {
  const KEY = 'edulearn_static_v1';
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = (d) => { try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) {} };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const data = () => { const el = document.getElementById('lesson-data'); return el ? JSON.parse(el.textContent) : null; };

  function toggleTheme() {
    const dark = document.documentElement.dataset.theme === 'dark';
    document.documentElement.dataset.theme = dark ? '' : 'dark';
    document.cookie = 'el_theme=' + (dark ? 'light' : 'dark') + ';path=/;max-age=31536000';
  }

  /* ---------------- subject + index progress ---------------- */
  function refreshProgress() {
    const done = load();
    document.querySelectorAll('[data-prog],[data-subprog],[data-unitpill],[data-subbar],[data-subprog],[data-unitbar],[data-mark],[data-pill]').forEach(el => {});
    // subject page rows
    document.querySelectorAll('[data-lesson]').forEach(row => {
      const id = row.dataset.lesson, rec = done[id];
      const mark = row.querySelector('[data-mark]'), pill = row.querySelector('[data-pill]');
      if (rec && mark) { mark.classList.add('done'); mark.textContent = '✓'; }
      if (rec && pill) { pill.className = 'pill pill-done'; pill.textContent = (rec.p ? '✓ ' + rec.p + '%' : '✓ Done'); }
    });
    // unit bars
    document.querySelectorAll('[data-unit]').forEach(u => {
      const total = +u.dataset.count || 0;
      let d = 0; u.querySelectorAll('[data-lesson]').forEach(r => { if (done[r.dataset.lesson]) d++; });
      const bar = document.querySelector('[data-unitbar="' + u.dataset.unit + '"]');
      if (bar) bar.style.width = (total ? Math.round(d / total * 100) : 0) + '%';
      const pill = document.querySelector('[data-unitpill="' + u.dataset.unit + '"]');
      if (pill) { pill.textContent = d + '/' + total; if (d === total && total) { pill.className = 'pill pill-done'; } }
    });
    // subject summary
    const sbar = document.querySelector('[data-subbar]');
    if (sbar) {
      const rows = [...document.querySelectorAll('[data-lesson]')];
      const d = rows.filter(r => done[r.dataset.lesson]).length;
      sbar.style.width = (rows.length ? Math.round(d / rows.length * 100) : 0) + '%';
      const lab = document.querySelector('[data-subprog]');
      if (lab) lab.textContent = d + ' / ' + rows.length + ' lessons completed';
    }
    // index cards
    document.querySelectorAll('a.card[data-subj]').forEach(card => {});
  }

  /* ---------------- lesson page ---------------- */
  function initLesson() {
    const d = data(); if (!d) return;
    const done = load(), rec = done[d.id];
    const pill = document.getElementById('statuspill');
    if (rec && pill) { pill.className = 'pill pill-done'; pill.textContent = '✓ Passed ' + (rec.p || '') + '%'; }
    // tabs
    document.querySelectorAll('.subtab[data-tab]').forEach(b => b.onclick = () => showTab(b.dataset.tab));
    // flashcards
    let i = 0, show = false;
    const fc = document.getElementById('fc');
    if (d.cards && d.cards.length) {
      window.__fc = () => ({ i, cards: d.cards });
    }
    EL_state = { i: 0 };
    // quiz
    const qstate = { step: 0, sel: {}, submitted: false };
    function renderQuiz() {
      const host = document.getElementById('quizhost'); if (!host) return;
      if (!d.quiz.length) { host.innerHTML = "<div class='card'><b>Assessment</b><p class='muted'>No questions for this lesson yet.</p></div>"; return; }
      if (qstate.submitted) { renderResult(); return; }
      const q = d.quiz[qstate.step], sel = qstate.sel[qstate.step];
      const opts = q.c.map((c, j) => `<div class="opt ${sel === j ? 'sel' : ''}" onclick="EL.pick(${j})">
        <span class="k">${LETTERS[j]}</span><div>${esc(c)}</div></div>`).join('');
      const answered = Object.keys(qstate.sel).length;
      host.innerHTML = `<div class="card"><div style="display:flex;gap:8px;align-items:center">
          <span class="pill pill-prog">Question ${qstate.step + 1} of ${d.quiz.length}</span>
          <span class="muted" style="font-size:12px">${esc(q.k)} · ${esc(q.d)}</span></div>
          <div class="pbar mt8"><div class="pfill" style="width:${Math.round(answered / d.quiz.length * 100)}%"></div></div></div>
        <div class="qcard"><h3 style="margin:6px 0 10px">${esc(q.q)}</h3>${opts}
        <div style="display:flex;justify-content:space-between;margin-top:16px;gap:8px">
          <button class="btn btn-ghost" ${qstate.step === 0 ? 'disabled' : ''} onclick="EL.nav(-1)">← Back</button>
          ${qstate.step === d.quiz.length - 1 ? '<button class="btn btn-primary" onclick="EL.submit()">Submit assessment ✓</button>'
            : '<button class="btn btn-primary" onclick="EL.nav(1)">Next →</button>'}
        </div></div>`;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    function renderResult() {
      const host = document.getElementById('quizhost');
      let right = 0; d.quiz.forEach((q, j) => { if (qstate.sel[j] === q.a) right++; });
      const pct = Math.round(right / d.quiz.length * 100), passed = pct >= 80;
      const review = d.quiz.map((q, j) => {
        const ok = qstate.sel[j] === q.a;
        return `<div class="qcard"><div style="font-weight:700;margin-bottom:6px">${ok ? '✅' : '❌'} ${esc(q.q)}</div>
          <div class="reviewbox ${ok ? '' : 'err'}"><b>Your answer:</b> ${qstate.sel[j] == null ? 'Not answered' : esc(q.c[qstate.sel[j]])}</div>
          <div class="reviewbox"><b>Correct answer (${'ABCDEFGH'[q.a]}):</b> ${esc(q.c[q.a])}<br><br><b>Why:</b> ${esc(q.why || 'Covered in the lesson above.')}</div></div>`;
      }).join('');
      host.innerHTML = `<div class="center fadein" style="padding:10px 0">
          <h2>${passed ? 'Lesson completed 🎉' : 'Not passed yet'}</h2>
          <p>You scored <b>${right} / ${d.quiz.length}</b> (${pct}%). The pass mark is <b>80%</b>.</p>
          ${passed ? '<p class="muted">This lesson is now marked complete in this browser.</p>' : '<p class="muted">Review the explanations below, re-read the lesson, then retake.</p>'}
          <button class="btn btn-primary mt8" onclick="EL.retake()">Retake the assessment</button>
        </div><h3 class="mt16">Assessment review</h3>${review}`;
      const best = done[d.id] && done[d.id].p ? done[d.id].p : 0;
      if (passed) { done[d.id] = { p: Math.max(best, pct) }; save(done); }
      if (pill) { pill.className = passed ? 'pill pill-done' : 'pill pill-rev'; pill.textContent = passed ? '✓ Passed ' + pct + '%' : '↻ Review'; }
    }
    window.EL_pick = (j) => { qstate.sel[qstate.step] = j; renderQuiz(); };
    window.EL_nav = (dd) => { qstate.step = Math.max(0, Math.min(d.quiz.length - 1, qstate.step + dd)); renderQuiz(); };
    window.EL_submit = () => { qstate.submitted = true; renderResult(); };
    window.EL_retake = () => { qstate.submitted = false; qstate.sel = {}; qstate.step = 0; renderQuiz(); };
    showTab('learn');
    renderQuiz();
  }

  function showTab(k) {
    document.querySelectorAll('.tabpanel').forEach(p => p.classList.add('hide'));
    const p = document.getElementById('panel-' + k); if (p) p.classList.remove('hide');
    document.querySelectorAll('.subtab[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === k));
  }

  const api = {
    toggleTheme,
    showTab: (k) => showTab(k),
    pick: (j) => window.EL_pick && window.EL_pick(j),
    nav: (d) => window.EL_nav && window.EL_nav(d),
    submit: () => window.EL_submit && window.EL_submit(),
    retake: () => window.EL_retake && window.EL_retake(),
    flip: () => { const c = document.getElementById('fc'); if (c) c.classList.toggle('flip'); },
    fcPrev: () => fcStep(-1),
    fcNext: () => fcStep(1),
  };
  let fidx = 0, fcards = [];
  function fcStep(d) {
    if (!fcards.length) return;
    fidx = Math.max(0, Math.min(fcards.length - 1, fidx + d));
    const c = document.getElementById('fc'); if (c) c.classList.remove('flip');
    document.getElementById('fcf').textContent = fcards[fidx].front;
    document.getElementById('fcb').textContent = fcards[fidx].back;
    const n = document.getElementById('fci'); if (n) n.textContent = (fidx + 1) + ' / ' + fcards.length;
  }
  const LETTERS = 'ABCDEFGH';
  document.addEventListener('DOMContentLoaded', () => {
    const d = data();
    if (d) { fcards = d.cards || []; initLesson(); } else { refreshProgress(); }
  });
  return api;
})();
