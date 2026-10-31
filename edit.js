/* Live editing. Every editable piece of text has a data-loc. Edits are rows in Supabase, newest rev wins,
   and each page overlays them on the built text when it loads. Text only ever goes in through textContent. */
(function () {
  "use strict";

  const BASE = "https://duhsapgvvlpzrhtvnciu.supabase.co";
  const KEY = "sb_publishable_N19t8v31QEDJ_qIRKEjRig_rSDS5QoI";   // public by design; RLS does the protecting
  const SESSION = "manazil-session";
  const HELP_SEEN = "manazil-help-seen";
  const PAGE = document.body.dataset.editPage;                    // "*" on pages that show text from every chapter

  const targets = new Map();    // loc -> elements showing it
  const baseText = new Map();   // loc -> text as built, before any overlay
  const edits = new Map();      // loc -> rows, oldest first
  const comments = new Map();   // loc -> rows, oldest first
  const editors = new Map();    // user id -> display name

  /* ---- helpers ---- */

  function el(tag, props, ...kids) {
    const n = Object.assign(document.createElement(tag), props || {});
    n.append(...kids.filter((k) => k !== null && k !== undefined));
    return n;
  }

  function when(iso) {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function latest(loc) {
    const rows = edits.get(loc);
    return rows && rows.length ? rows[rows.length - 1] : null;
  }

  function current(loc) {
    const row = latest(loc);
    return row ? row.text : baseText.get(loc);
  }

  let toastTimer;
  function toast(message) {
    let t = document.getElementById("edit-toast");
    if (!t) {
      t = el("div", { id: "edit-toast", className: "edit-toast" });
      t.setAttribute("role", "status");
      document.body.append(t);
    }
    t.textContent = message;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 6000);
  }

  /* ---- session ---- */

  function session() {
    try { return JSON.parse(localStorage.getItem(SESSION)); } catch (err) { return null; }
  }

  function storeSession(s) {
    if (s) {
      localStorage.setItem(SESSION, JSON.stringify({
        access_token: s.access_token, refresh_token: s.refresh_token, expires_at: s.expires_at, user_id: s.user.id,
      }));
    } else {
      localStorage.removeItem(SESSION);
    }
  }

  async function authPost(path, body) {
    const r = await fetch(`${BASE}/auth/v1/${path}`, {
      method: "POST",
      headers: { apikey: KEY, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return { status: r.status, ok: r.ok, data: await r.json().catch(() => ({})) };
  }

  let refreshing = null;
  async function accessToken() {
    const s = session();
    if (!s) return null;
    if (s.expires_at - 60 > Date.now() / 1000) return s.access_token;
    if (!refreshing) {
      refreshing = authPost("token?grant_type=refresh_token", { refresh_token: s.refresh_token })
        .then((res) => {
          if (res.ok) {
            storeSession(res.data);
          } else if (res.status === 400 || res.status === 401) {
            storeSession(null);
            renderAccount();
          }
        })
        .finally(() => { refreshing = null; });
    }
    await refreshing;
    const after = session();
    return after && after.expires_at - 60 > Date.now() / 1000 ? after.access_token : null;
  }

  async function rest(path, options) {
    const opts = options || {};
    const headers = { apikey: KEY, "Content-Type": "application/json", ...(opts.headers || {}) };
    const token = await accessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(`${BASE}/rest/v1/${path}`, { ...opts, headers });
  }

  async function fetchAll(table, select, filter) {
    const rows = [];
    for (let offset = 0; ; offset += 1000) {
      const r = await rest(`${table}?select=${select}${filter}&order=id&limit=1000&offset=${offset}`);
      if (!r.ok) throw new Error(`${table}: HTTP ${r.status}`);
      const batch = await r.json();
      rows.push(...batch);
      if (batch.length < 1000) return rows;
    }
  }

  /* ---- showing edits ---- */

  function group(rows) {
    const out = new Map();
    for (const row of rows) {
      if (!out.has(row.loc)) out.set(row.loc, []);
      out.get(row.loc).push(row);
    }
    return out;
  }

  function byRev(rows) {
    return rows.sort((a, b) => a.rev - b.rev);
  }

  function show(loc) {
    const text = current(loc);
    for (const node of targets.get(loc) || []) {
      if (node.textContent !== text) node.textContent = text;
    }
    markStale(loc);
    for (const node of targets.get(loc) || []) node.classList.toggle("has-comment", (comments.get(loc) || []).length > 0);
  }

  /* An English passage whose Arabic was changed after it, unless the Arabic has gone back to the original. */
  function markStale(loc) {
    const stem = loc.replace(/\.(ar|en)$/, "");
    if (stem === loc) return;
    const ar = edits.get(`${stem}.ar`);
    const newestAr = latest(`${stem}.ar`);
    const newestEn = latest(`${stem}.en`);
    const stale = Boolean(newestAr) && newestAr.text !== ar[0].text &&
      (!newestEn || newestEn.created_at < newestAr.created_at);
    for (const node of targets.get(`${stem}.en`) || []) {
      node.classList.toggle("stale", stale);
      if (stale) node.title = "The Arabic changed after this translation was last edited";
      else node.removeAttribute("title");
    }
  }

  async function loadAll() {
    const filter = PAGE === "*" ? "" : `&page=eq.${encodeURIComponent(PAGE)}`;
    const [names, rows, notes] = await Promise.all([
      fetchEditors(),
      fetchAll("edits", "id,loc,rev,text,editor_id,created_at", filter),
      fetchAll("comments", "id,loc,text,editor_id,created_at", filter),
    ]);
    names.forEach((n) => editors.set(n.user_id, n.name));
    group(rows).forEach((list, loc) => edits.set(loc, byRev(list)));
    group(notes).forEach((list, loc) => comments.set(loc, list));
    new Set([...edits.keys(), ...comments.keys()]).forEach(show);
  }

  async function fetchEditors() {
    const r = await rest("editors?select=user_id,name");
    if (!r.ok) throw new Error(`editors: HTTP ${r.status}`);
    return r.json();
  }

  async function reloadLoc(loc) {
    const q = encodeURIComponent(loc);
    const [rows, notes] = await Promise.all([
      fetchAll("edits", "id,loc,rev,text,editor_id,created_at", `&loc=eq.${q}`),
      fetchAll("comments", "id,loc,text,editor_id,created_at", `&loc=eq.${q}`),
    ]);
    edits.set(loc, byRev(rows));
    comments.set(loc, notes);
    show(loc);
    const other = loc.replace(/\.(ar|en)$/, (m) => (m === ".ar" ? ".en" : ".ar"));
    if (other !== loc) markStale(other);
  }

  /* ---- account ---- */

  function renderAccount() {
    const box = document.getElementById("account");
    const s = session();
    document.body.classList.toggle("editing", Boolean(s));
    for (const nodes of targets.values()) {
      for (const node of nodes) {
        if (s) { node.tabIndex = 0; node.setAttribute("role", "button"); }
        else { node.removeAttribute("tabindex"); node.removeAttribute("role"); }
      }
    }
    if (!box) return;
    box.replaceChildren(s
      ? el("button", { type: "button", className: "link-button", textContent: editors.get(s.user_id) || "Account", onclick: openAccount })
      : el("button", { type: "button", className: "link-button", textContent: "Sign in", onclick: openSignIn }));
  }

  function dialog(title, ...body) {
    const d = el("dialog", { className: "edit-dialog" },
      el("h2", { textContent: title }), ...body);
    d.addEventListener("close", () => d.remove());
    document.body.append(d);
    d.showModal();
    return d;
  }

  function openSignIn() {
    const email = el("input", { type: "email", required: true, autocomplete: "username", id: "edit-email" });
    const password = el("input", { type: "password", required: true, autocomplete: "current-password", id: "edit-password" });
    const error = el("p", { className: "edit-error" });
    const submit = el("button", { type: "submit", className: "primary", textContent: "Sign in" });
    const d = dialog("Sign in to edit",
      el("form", {
        onsubmit: async (ev) => {
          ev.preventDefault();
          submit.disabled = true;
          error.textContent = "";
          try {
            const res = await authPost("token?grant_type=password", { email: email.value.trim(), password: password.value });
            if (!res.ok) {
              error.textContent = res.status === 400 ? "That email and password don't match." : "Sign-in failed. Please try again.";
              return;
            }
            storeSession(res.data);
            renderAccount();
            d.close();
            showHelpOnce();
          } catch (err) {
            error.textContent = "Couldn't reach the server. Please try again.";
          } finally {
            submit.disabled = false;
          }
        },
      },
      el("label", { htmlFor: "edit-email", textContent: "Email" }), email,
      el("label", { htmlFor: "edit-password", textContent: "Password" }), password,
      error,
      el("div", { className: "edit-actions" },
        el("button", { type: "button", className: "link-button", textContent: "Cancel", onclick: () => d.close() }),
        submit)));
  }

  function openHelp() {
    const d = dialog("How to edit",
      el("ul", { className: "edit-help" },
        el("li", { textContent: "Click any line of text, English or Arabic, to open it. Lines highlight as you point at them." }),
        el("li", { textContent: "Save publishes your change right away, for everyone, under your name." }),
        el("li", { textContent: "Earlier versions, under the box, brings back any previous wording, including the original." }),
        el("li", { textContent: "Comments are for what the box can't fix, such as a poet, a meter, or a verse to split or remove." }),
        el("li", null, "Not sure where to begin? ",
          el("a", { href: "review.html", textContent: "Uncertain passages" }), " lists where the translator wasn't sure.")),
      el("div", { className: "edit-actions" },
        el("button", { type: "button", className: "primary", textContent: "Got it", autofocus: true, onclick: () => d.close() })));
  }

  function showHelpOnce() {
    if (localStorage.getItem(HELP_SEEN)) return;
    localStorage.setItem(HELP_SEEN, "1");
    openHelp();
  }

  function openAccount() {
    const s = session();
    const password = el("input", { type: "password", required: true, minLength: 6, autocomplete: "new-password", id: "edit-new-password" });
    const error = el("p", { className: "edit-error" });
    const d = dialog(editors.get(s.user_id) || "Account",
      el("form", {
        onsubmit: async (ev) => {
          ev.preventDefault();
          error.textContent = "";
          try {
            const token = await accessToken();
            const r = await fetch(`${BASE}/auth/v1/user`, {
              method: "PUT",
              headers: { apikey: KEY, "Content-Type": "application/json", Authorization: `Bearer ${token}` },
              body: JSON.stringify({ password: password.value }),
            });
            const body = await r.json().catch(() => ({}));
            if (!r.ok) { error.textContent = body.msg || "Couldn't change the password."; return; }
            d.close();
            toast("Password changed.");
          } catch (err) {
            error.textContent = "Couldn't reach the server. Please try again.";
          }
        },
      },
      el("label", { htmlFor: "edit-new-password", textContent: "New password" }), password,
      error,
      el("div", { className: "edit-actions" },
        el("button", { type: "button", className: "link-button", textContent: "How to edit", onclick: () => { d.close(); openHelp(); } }),
        el("button", { type: "button", className: "link-button", textContent: "Sign out", onclick: () => { signOut(); d.close(); } }),
        el("button", { type: "button", className: "link-button", textContent: "Close", onclick: () => d.close() }),
        el("button", { type: "submit", className: "primary", textContent: "Change password" }))));
  }

  function signOut() {
    const s = session();
    storeSession(null);
    renderAccount();
    if (s) {
      fetch(`${BASE}/auth/v1/logout`, {
        method: "POST", headers: { apikey: KEY, Authorization: `Bearer ${s.access_token}` },
      }).catch(() => {});
    }
  }

  /* ---- the editor ---- */

  function describe(loc) {
    const lang = loc.endsWith(".ar") ? "Arabic" : "English";
    let m = loc.match(/\.v(\d+)\.h([12])\./);
    if (m) return `${lang}: line ${m[1]}, ${m[2] === "1" ? "first" : "second"} hemistich`;
    if (/\.n\d+$/.test(loc)) return "Translator's note";
    if (/\.i\d+\./.test(loc)) return `${lang}: gloss`;
    return `${lang}: prose`;
  }

  function pageLabel(href) {
    const m = href.match(/^chapter-(\d+)/);
    if (m) return `Chapter ${Number(m[1])}`;
    return href.startsWith("muqaddima") ? "Author's preface" : href;
  }

  async function openEditor(loc, node) {
    const holder = node.closest("[data-page]");
    const page = holder ? holder.dataset.page : PAGE;
    const arabic = loc.endsWith(".ar");

    const box = el("textarea", { rows: 4, value: current(loc) });
    box.setAttribute("aria-label", describe(loc));
    if (arabic) { box.lang = "ar"; box.dir = "rtl"; }
    const error = el("p", { className: "edit-error" });
    const save = el("button", { type: "button", className: "primary", textContent: "Save" });
    const historyList = el("ul", { className: "edit-history" });
    const commentList = el("ul", { className: "edit-comments" });
    const commentBox = el("textarea", { rows: 2 });
    commentBox.setAttribute("aria-label", "Add a comment");
    const commentButton = el("button", { type: "button", className: "link-button", textContent: "Add comment" });

    const alsoHolder = node.closest("[data-also]");
    const also = alsoHolder && el("p", { className: "edit-also" }, "This poem also appears at ",
      ...alsoHolder.dataset.also.split(" ").flatMap((href, i) => [
        i ? ", " : null,
        el("a", { href, target: "_blank", rel: "noopener", textContent: pageLabel(href) }),
      ]).filter(Boolean), ". A change here won't reach those copies.");

    const d = dialog(describe(loc), box, error,
      el("div", { className: "edit-actions" },
        el("button", { type: "button", className: "link-button", textContent: "Cancel", onclick: () => close() }),
        save),
      also,
      el("details", { className: "edit-section" }, el("summary", { textContent: "Comments" }), commentList, commentBox,
        el("div", { className: "edit-actions" }, commentButton)),
      el("details", { className: "edit-section" }, el("summary", { textContent: "Earlier versions" }), historyList));

    let opened = box.value;
    function dirty() { return box.value !== opened || commentBox.value.trim() !== ""; }
    function close() {
      if (!dirty() || window.confirm("Discard your unsaved text?")) d.close();
    }
    d.addEventListener("cancel", (ev) => { ev.preventDefault(); close(); });

    function renderSide() {
      const rows = edits.get(loc) || [];
      historyList.replaceChildren(...(rows.length ? rows.slice().reverse().map((row) => {
        const who = row.rev === 1 ? "Original" : `${editors.get(row.editor_id) || "Someone"}, ${when(row.created_at)}`;
        const text = el("span", { className: "edit-history-text", textContent: row.text });
        if (arabic) { text.lang = "ar"; text.dir = "rtl"; }
        return el("li", null, el("div", { className: "edit-history-who" }, who, " ",
          row === latest(loc) ? null : el("button", {
            type: "button", className: "link-button", textContent: "Use this text",
            onclick: () => { box.value = row.text; box.focus(); },
          })), text);
      }) : [el("li", { textContent: "No edits yet." })]));
      const notes = comments.get(loc) || [];
      commentList.replaceChildren(...notes.map((c) => el("li", null,
        el("div", { className: "edit-history-who", textContent: `${editors.get(c.editor_id) || "Someone"}, ${when(c.created_at)}` }),
        el("span", { textContent: c.text }))));
    }
    renderSide();

    function failMessage(status) {
      if (status === 401 || status === 403) return "You're not signed in as an editor. Your text is still in the box; sign in again in another tab, then save.";
      return `Couldn't save (error ${status}). Your text is still in the box.`;
    }

    try {
      await reloadLoc(loc);
      if (box.value === opened) box.value = current(loc);   // someone may have edited since this page loaded
      opened = box.value;
      renderSide();
    } catch (err) {
      error.textContent = "Couldn't check for recent changes. You can still try to save.";
    }

    save.onclick = async () => {
      const text = box.value;
      error.textContent = "";
      if (!text.trim()) { error.textContent = "The text can't be empty."; return; }
      if (text === current(loc)) { error.textContent = "Nothing has changed."; return; }
      const newest = latest(loc);
      // The first edit of a passage also records the built text as rev 1, so it stays restorable after a bake.
      const rows = newest ? [{ loc, page, rev: newest.rev + 1, text }]
        : [{ loc, page, rev: 1, text: baseText.get(loc) }, { loc, page, rev: 2, text }];
      save.disabled = true;
      try {
        const r = await rest("edits", { method: "POST", body: JSON.stringify(rows), headers: { Prefer: "return=minimal" } });
        if (r.status === 409) {
          await reloadLoc(loc);
          const other = latest(loc);
          opened = text;
          renderSide();
          error.textContent = `${editors.get(other.editor_id) || "Someone"} just changed this. Their version is under "Earlier versions" and on the page behind this box. Your text is still here; save again to replace theirs.`;
          return;
        }
        if (!r.ok) { error.textContent = failMessage(r.status); return; }
        await reloadLoc(loc);
        opened = box.value;
        d.close();
        toast("Saved. It's live now.");
      } catch (err) {
        error.textContent = "Couldn't reach the server. Your text is still in the box.";
      } finally {
        save.disabled = false;
      }
    };

    commentButton.onclick = async () => {
      const text = commentBox.value.trim();
      if (!text) return;
      commentButton.disabled = true;
      error.textContent = "";
      try {
        const r = await rest("comments", { method: "POST", body: JSON.stringify({ loc, page, text }), headers: { Prefer: "return=minimal" } });
        if (!r.ok) { error.textContent = failMessage(r.status); return; }
        commentBox.value = "";
        await reloadLoc(loc);
        renderSide();
      } catch (err) {
        error.textContent = "Couldn't reach the server. Your comment is still in the box.";
      } finally {
        commentButton.disabled = false;
      }
    };
  }

  /* ---- start ---- */

  function target(ev) {
    if (!document.body.classList.contains("editing") || !(ev.target instanceof Element)) return null;
    if (ev.target.closest("dialog")) return null;
    return ev.target.closest("[data-loc]");
  }

  document.querySelectorAll("[data-loc]").forEach((node) => {
    const loc = node.dataset.loc;
    if (!targets.has(loc)) { targets.set(loc, []); baseText.set(loc, node.textContent); }
    targets.get(loc).push(node);
  });

  document.addEventListener("click", (ev) => {
    const node = target(ev);
    if (node && !String(window.getSelection())) openEditor(node.dataset.loc, node);
  });
  document.addEventListener("keydown", (ev) => {
    const node = ev.key === "Enter" ? target(ev) : null;
    if (node) { ev.preventDefault(); openEditor(node.dataset.loc, node); }
  });

  const chapterMenu = document.querySelector(".bar details");
  document.addEventListener("click", (ev) => { if (chapterMenu && !chapterMenu.contains(ev.target)) chapterMenu.open = false; });
  document.addEventListener("keydown", (ev) => { if (chapterMenu && ev.key === "Escape") chapterMenu.open = false; });

  renderAccount();
  loadAll().catch((err) => console.warn("Edits not loaded:", err)).finally(() => {
    renderAccount();
    if (session()) showHelpOnce();   // for anyone already signed in when this was added
  });
})();
