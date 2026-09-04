/**
 * GitLane — retired runtime patch (kept as a no-op).
 *
 * The repo-switch button ("Repo" / "Depot") and the Ctrl+O shortcut now
 * live in the React bundle itself (TopToolbar + App keyboard shortcuts),
 * so this file intentionally does nothing. It is kept (instead of deleted)
 * so previously built/cached index.html files that still reference
 * /static/gitlane-patches.js keep loading without a 404.
 */
(function () {
  "use strict";
  /* no-op */
})();
