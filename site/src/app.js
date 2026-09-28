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
  // language: the header switch stores a preference; a page in the other language redirects to its twin
  var LKEY = "laso_lang";
  var here = document.body.getAttribute("data-lang") || "zh";
  document.querySelectorAll("[data-lang-switch]").forEach(function (a) {
    a.addEventListener("click", function () { try { localStorage.setItem(LKEY, a.getAttribute("data-lang-switch")); } catch (e) {} });
  });
  try {
    var want = localStorage.getItem(LKEY);
    if (want && want !== here && !sessionStorage.getItem("laso_lang_redirected")) {
      var twin = document.querySelector("[data-lang-switch='" + want + "']");
      if (twin) { sessionStorage.setItem("laso_lang_redirected", "1"); location.replace(twin.getAttribute("href")); return; }
    }
    sessionStorage.removeItem("laso_lang_redirected");
  } catch (e) {}
  // dashboard link: disabled until ABL_APP_URL is configured at build time
  var link = document.getElementById("app-link");
  if (link && (link.getAttribute("href") === "#" || !link.getAttribute("href"))) link.setAttribute("aria-disabled", "true");
})();
