// Per-device lesson progress, stored in localStorage (no accounts).
(function () {
  const KEY = "oak-explorer:done";

  function load() {
    try {
      return new Set(JSON.parse(localStorage.getItem(KEY) || "[]").map(String));
    } catch (e) {
      return new Set();
    }
  }

  function save(done) {
    try {
      localStorage.setItem(KEY, JSON.stringify([...done]));
    } catch (e) {
      /* storage unavailable: progress just won't persist */
    }
  }

  function countDone(done, ids) {
    return ids.filter((id) => done.has(id)).length;
  }

  function idsOf(el) {
    return (el.dataset.lessons || "").split(",").filter(Boolean);
  }

  function refresh() {
    const done = load();

    document.querySelectorAll("[data-done-toggle]").forEach((box) => {
      box.checked = done.has(box.dataset.doneToggle);
    });

    document.querySelectorAll("[data-lesson-id]").forEach((li) => {
      li.classList.toggle("is-done", done.has(li.dataset.lessonId));
    });

    document.querySelectorAll(".unit-row[data-lessons]").forEach((row) => {
      const ids = idsOf(row);
      const pct = ids.length ? (100 * countDone(done, ids)) / ids.length : 0;
      row.querySelector(".meter span").style.width = pct + "%";
      row.classList.toggle("is-done", ids.length > 0 && pct === 100);
    });

    document.querySelectorAll("[data-unit-progress]").forEach((el) => {
      const ids = idsOf(el);
      const n = countDone(done, ids);
      el.textContent = n ? `${n} of ${ids.length} lessons done` : "";
    });

    const summary = document.querySelector("[data-progress-summary]");
    if (summary) {
      summary.hidden = done.size === 0;
      summary.querySelector("[data-done-count]").textContent = done.size;
    }
  }

  document.addEventListener("change", (e) => {
    const id = e.target.dataset && e.target.dataset.doneToggle;
    if (!id) return;
    const done = load();
    e.target.checked ? done.add(id) : done.delete(id);
    save(done);
    refresh();
  });

  document.addEventListener("DOMContentLoaded", refresh);
})();
