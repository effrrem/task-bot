(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
  ];
  const MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
  ];
  const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const params = {};
  if (tg?.initData) {
    for (const [k, v] of new URLSearchParams(tg.initData)) params[k] = v;
  }
  const initData = tg?.initData || "";

  // --- Apply Telegram theme ---
  const root = document.documentElement;
  const tp = tg?.themeParams || {};
  const dark = tg?.colorScheme === "dark";
  root.setAttribute("data-theme", dark ? "dark" : "light");
  const map = {
    "--bg": tp.bg_color,
    "--bg-soft": tp.secondary_bg_color,
    "--card": tp.section_bg_color,
    "--text": tp.text_color,
    "--muted": tp.hint_color || tp.subtitle_text_color,
    "--border": dark ? "rgba(255,255,255,0.09)" : "rgba(0,0,0,0.06)",
  };
  for (const [prop, val] of Object.entries(map)) {
    if (val) root.style.setProperty(prop, val);
  }
  const accent = tp.link_color || (dark ? "#8ab4f8" : "#0088cc");
  root.style.setProperty("--accent", accent);
  root.style.setProperty("--accent-soft", accent + "38");

  // --- State ---
  let tasks = [];
  let tasksByKey = new Map();
  let year = 0;
  let month = 0; // 0-based
  let selected = { y: 0, m: 0, d: 0 };

  const keyOf = (y, m, d) => `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

  const toLocalParts = (dt) => ({ y: dt.getFullYear(), m: dt.getMonth(), d: dt.getDate() });

  // --- Load tasks ---
  async function loadTasks() {
    try {
      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData }),
      });
      if (!res.ok) throw new Error("status " + res.status);
      tasks = await res.json();
      tasksByKey = new Map();
      for (const t of tasks) {
        const { y, m, d } = toLocalParts(new Date(t.deadline));
        const k = keyOf(y, m, d);
        if (!tasksByKey.has(k)) tasksByKey.set(k, []);
        tasksByKey.get(k).push(t);
      }
      document.getElementById("appFooter").style.display = tasks.length ? "" : "none";
      return true;
    } catch (err) {
      showError("Не удалось загрузить задачи. Проверь интернет.");
      return false;
    }
  }

  function showError(msg) {
    let el = document.getElementById("errToast");
    if (!el) {
      el = document.createElement("div");
      el.id = "errToast";
      el.className = "status-error";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = "block";
    setTimeout(() => { el.style.display = "none"; }, 4000);
  }

  // --- Calendar rendering ---
  function renderWeekRow() {
    const row = $("weekRow");
    row.innerHTML = "";
    WD.forEach((w, i) => {
      const s = document.createElement("span");
      if (i >= 5) s.className = "wkend";
      s.textContent = w;
      row.appendChild(s);
    });
  }

  function buildDayCounts(list) {
    const counts = { danger: 0, accent: 0, done: 0, overdue: 0 };
    const now = Date.now();
    for (const t of list) {
      if (t.done) { counts.done++; continue; }
      if (new Date(t.deadline).getTime() < now) { counts.danger++; counts.overdue++; }
      else counts.accent++;
    }
    return counts;
  }

  function renderCalendar() {
    const grid = $("calendar");
    grid.innerHTML = "";
    const first = new Date(year, month, 1);
    let offset = (first.getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const prevDays = new Date(year, month, 0).getDate();
    const today = toLocalParts(new Date());

    for (let i = 0; i < 42; i++) {
      const cell = document.createElement("div");
      cell.className = "day";
      const dayNum = i - offset + 1;
      let cy = year, cm = month, cd = dayNum;
      let muted = false;

      if (dayNum < 1) {
        cy = month === 0 ? year - 1 : year;
        cm = month === 0 ? 11 : month - 1;
        cd = prevDays + dayNum;
        muted = true;
      } else if (dayNum > daysInMonth) {
        cy = month === 11 ? year + 1 : year;
        cm = month === 11 ? 0 : month + 1;
        cd = dayNum - daysInMonth;
        muted = true;
      }

      const dow = (i % 7);
      if (dow >= 5) cell.classList.add("wkend");
      if (muted) cell.classList.add("muted");

      const isToday = cd === today.d && cm === today.m && cy === today.y;
      const isSelected = cd === selected.d && cm === selected.m && cy === selected.y;
      if (isToday) cell.classList.add("today");
      if (isSelected) cell.classList.add("selected");

      const n = document.createElement("span");
      n.className = "n";
      n.textContent = cd;
      cell.appendChild(n);

      const k = keyOf(cy, cm, cd);
      const list = tasksByKey.get(k) || [];
      if (list.length) {
        const c = buildDayCounts(list);
        const dots = document.createElement("div");
        dots.className = "dots";
        const order = c.danger ? ["danger"] : [];
        if (c.accent) order.push("accent");
        if (c.done) order.push("done");
        order.slice(0, 3).forEach((o) => {
          const i2 = document.createElement("i");
          i2.className = "c-" + o;
          dots.appendChild(i2);
        });
        const shown = Math.min(order.length, 3);
        if (list.length > shown) {
          const plus = document.createElement("span");
          plus.className = "plus";
          plus.textContent = "+" + (list.length - shown);
          dots.appendChild(plus);
        }
        cell.appendChild(dots);
      }

      cell.addEventListener("click", () => selectDate(cy, cm, cd));
      grid.appendChild(cell);
    }
  }

  function selectDate(y, m, d, force = false) {
    if (!force && y === selected.y && m === selected.m && d === selected.d) return;
    if (y !== year || m !== month) {
      year = y;
      month = m;
      renderCalendar();
    }
    selected = { y, m, d };
    renderCalendar();
    renderTasks();
  }

  function today() {
    const t = toLocalParts(new Date());
    year = t.y;
    month = t.m;
    selected = { y: t.y, m: t.m, d: t.d };
    renderCalendar();
    renderTasks();
  }
  const STATUS = {
    late: { label: "Просрочена", cls: "late" },
    soon: { label: "В работе", cls: "soon" },
    done: { label: "Выполнена", cls: "done" },
  };

  function statusOf(t) {
    if (t.done) return STATUS.done;
    return new Date(t.deadline).getTime() < Date.now() ? STATUS.late : STATUS.soon;
  }

  function renderTasks() {
    const title = $("tasksTitle");
    title.textContent = `Задачи · ${selected.d} ${MONTHS_GEN[selected.m]}`;

    const k = keyOf(selected.y, selected.m, selected.d);
    const list = (tasksByKey.get(k) || []).slice().sort(
      (a, b) => new Date(a.deadline) - new Date(b.deadline)
    );

    const box = $("tasksList");
    box.innerHTML = "";
    if (!list.length) {
      const isFuture = new Date(selected.y, selected.m, selected.d).setHours(23, 59) >= Date.now();
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.innerHTML = isFuture
        ? '<span class="emoji">🍃</span>Свободный день — задач нет'
        : '<span class="emoji">✨</span>В этот день ничего не запланировано';
      box.appendChild(empty);
      return;
    }

    list.forEach((t, idx) => {
      const dt = new Date(t.deadline);
      const st = statusOf(t);
      const row = document.createElement("div");
      row.className = "task-row";
      row.style.animationDelay = `${idx * 35}ms`;

      const time = document.createElement("div");
      time.className = "task-time";
      time.textContent = `${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}`;

      const main = document.createElement("div");
      main.className = "task-main";
      const txt = document.createElement("div");
      txt.className = "task-text" + (t.done ? " done-text" : "");
      txt.textContent = t.text;
      main.appendChild(txt);

      const badge = document.createElement("div");
      badge.className = "task-status " + st.cls;
      badge.textContent = st.label;

      row.append(time, main, badge);
      box.appendChild(row);
    });
  }

  // --- Header ops ---
  function renderHeader() {
    $("monthLabel").innerHTML =
      `${MONTHS[month]} <span class="cal-title-year">${year}</span>`;
  }

  function shift(delta) {
    const d = new Date(year, month + delta, 1);
    year = d.getFullYear();
    month = d.getMonth();
    const last = new Date(year, month + 1, 0).getDate();
    const sd = Math.min(selected.d, last);
    selected = { y: year, m: month, d: sd };
    renderHeader();
    renderCalendar();
    renderTasks();
  }

  // --- Init ---
  async function init() {
    renderWeekRow();
    const ok = await loadTasks();
    const t = toLocalParts(new Date());
    year = t.y;
    month = t.m;
    selected = { y: t.y, m: t.m, d: t.d };
    renderHeader();
    renderCalendar();
    renderTasks();
    if (!ok && tg) {
      tg.MainButton?.show?.();
      tg.MainButton?.setParams?.({ text: "Открыть в Telegram", visible: true });
    }
  }

  $("prevBtn").addEventListener("click", () => shift(-1));
  $("nextBtn").addEventListener("click", () => shift(1));
  $("todayBtn").addEventListener("click", today);

  init();
})();