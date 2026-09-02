/**
 * GitLane — runtime patch (no rebuild needed).
 * Injects a "change repo" button into the frozen React bundle and adds
 * Ctrl+O / Cmd+O to jump to /picker. PLAN2 §3.3 option B.
 */
(function () {
  "use strict";

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
    if (injectButton() || ++tries > 50) clearInterval(timer);
  }, 100);
})();
