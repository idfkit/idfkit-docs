window.MathJax = {
  tex: {
    tags: "all",
    useLabelIds: true,
    tagSide: "right",
  },
  startup: {
    pageReady: function () {
      return MathJax.startup.defaultPageReady().then(function () {
        // Signal that MathJax is done rendering so eq-tooltips.js can
        // attach handlers and scroll to hash targets.
        document.dispatchEvent(new Event("mathjax-done"));
      });
    },
  },
};

// Handle instant navigation (MkDocs Material / Zensical).
// document$ is an rxjs Observable that emits on each page change.
// On instant navigation the page content is replaced via XHR, so
// MathJax must re-typeset the new content.
(function () {
  var firstLoad = true;

  function hookInstantNav() {
    if (typeof document$ === "undefined") return false;
    document$.subscribe(function () {
      if (firstLoad) {
        // Initial page load is handled by startup.pageReady above
        firstLoad = false;
        return;
      }
      if (window.MathJax && MathJax.startup) {
        MathJax.startup.output.clearCache();
        MathJax.typesetClear();
        MathJax.texReset();
        MathJax.typesetPromise().then(function () {
          document.dispatchEvent(new Event("mathjax-done"));
        });
      }
    });
    return true;
  }

  // document$ may not be available yet — poll briefly until it is
  if (!hookInstantNav()) {
    var attempts = 0;
    var interval = setInterval(function () {
      attempts++;
      if (hookInstantNav() || attempts > 50) {
        clearInterval(interval);
      }
    }, 100);
  }
})();
