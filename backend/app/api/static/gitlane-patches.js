/**
 * GitLane — runtime patch (no rebuild needed).
 * Injects a "change repo" button into the frozen React bundle and adds
 * Ctrl+O / Cmd+O to jump to /picker. PLAN2 §3.3 option B.
 */
(function () {
  "use strict";

  function injectToolbarSafetyCss() {
    if (document.getElementById("gitlane-toolbar-safety")) return;
    var style = document.createElement("style");
    style.id = "gitlane-toolbar-safety";
    style.textContent = [
      ".top-toolbar{display:flex;align-items:center;gap:8px;}",
      ".header-selectors{flex:1 1 auto;min-width:0;}",
      ".selector-button{max-width:min(220px,32vw)!important;}",
      ".toolbar-search{width:clamp(110px,22vw,260px)!important;}",
      ".lang-toggle,.toolbar-btn{flex:0 0 auto!important;}",
      "@media (max-width:980px){.toolbar-count{display:none!important}}",
      "@media (max-width:760px){.toolbar-sep{display:none!important}.toolbar-search{width:clamp(96px,26vw,170px)!important}}",
    ].join("");
    document.head.appendChild(style);
  }

  function goPicker(e) {
    if (e) e.preventDefault();
    window.location.href = "/picker";
  }

  // Ctrl+O / Cmd+O opens the picker (unless typing in an input).
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "o") {
      var t = e.target;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      goPicker(e);
    }
  });

  // Inject the toolbar button once the React toolbar is present.
  function locale() {
    try {
      var saved = localStorage.getItem("gitlane.locale");
      if (saved === "fr" || saved === "en") return saved;
    } catch (e) { /* ignore */ }
    return (navigator.language || "").toLowerCase().indexOf("fr") === 0 ? "fr" : "en";
  }

  function injectButton() {
    var sep = document.querySelector(".toolbar-sep");
    if (!sep) return false;
    var fr = locale() === "fr";
    var btn = document.createElement("button");
    btn.className = "toolbar-btn";
    btn.title = fr ? "Changer de dépôt (Ctrl+O)" : "Change repository (Ctrl+O)";
    btn.textContent = fr ? "↩ Dépôt" : "↩ Repo";
    btn.addEventListener("click", goPicker);
    sep.parentNode.insertBefore(btn, sep);
    return true;
  }

  var tries = 0;
  var timer = setInterval(function () {
    injectToolbarSafetyCss();
    if (injectButton() || ++tries > 50) clearInterval(timer);
  }, 100);
})();
