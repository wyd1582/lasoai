(function () {
  var KEY = "laso_persona";
  var names = { breeder: "育种", ai: "AI", board: "董事会" };
  function set(p) {
    if (p) document.body.setAttribute("data-persona", p); else document.body.removeAttribute("data-persona");
    document.querySelectorAll("[data-persona-btn]").forEach(function (b) {
      b.setAttribute("aria-pressed", String((b.getAttribute("data-persona-btn") || "") === (p || "")));
    });
    try { if (p) localStorage.setItem(KEY, p); else localStorage.removeItem(KEY); } catch (e) {}
  }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  set(names[saved] ? saved : null);
  document.querySelectorAll("[data-persona-btn]").forEach(function (b) {
    b.addEventListener("click", function () {
      var p = b.getAttribute("data-persona-btn") || null;
      set(document.body.getAttribute("data-persona") === p ? null : p);
    });
  });
  // dashboard link: disabled until ABL_APP_URL is configured at build time
  var link = document.getElementById("app-link");
  if (link && (link.getAttribute("href") === "#" || !link.getAttribute("href"))) link.setAttribute("aria-disabled", "true");
})();
