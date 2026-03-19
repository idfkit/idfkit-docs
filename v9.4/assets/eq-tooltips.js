/**
 * Equation hover tooltips and scroll/highlight for EnergyPlus documentation.
 *
 * Handles:
 * 1. Same-page \eqref{} links (rendered by MathJax) — clones the target equation
 * 2. Cross-page .eq-ref elements — typesets data-equation LaTeX on demand
 * 3. Post-MathJax scroll to hash targets (equation anchors)
 * 4. Flash highlight on the target equation when navigating to it
 */
(function () {
  "use strict";

  var tooltip = null;
  var hideTimeout = null;

  function createTooltip() {
    if (tooltip) return tooltip;
    tooltip = document.createElement("div");
    tooltip.className = "eq-tooltip";
    document.body.appendChild(tooltip);
    return tooltip;
  }

  function showTooltip(el, html) {
    var tip = createTooltip();
    tip.innerHTML = html;
    tip.classList.remove("below");
    tip.classList.add("visible");

    // Position above the element
    var rect = el.getBoundingClientRect();
    var tipRect = tip.getBoundingClientRect();
    var top = rect.top + window.scrollY - tipRect.height - 10;
    var left = rect.left + window.scrollX + rect.width / 2 - tipRect.width / 2;

    // Boundary checks
    if (top < window.scrollY) {
      top = rect.bottom + window.scrollY + 10;
      tip.classList.add("below");
    }
    if (left < 4) left = 4;
    if (left + tipRect.width > window.innerWidth - 4) {
      left = window.innerWidth - tipRect.width - 4;
    }

    tip.style.top = top + "px";
    tip.style.left = left + "px";
  }

  function hideTooltip() {
    if (tooltip) {
      tooltip.classList.remove("visible");
      tooltip.innerHTML = "";
    }
  }

  function scheduleHide() {
    hideTimeout = setTimeout(hideTooltip, 100);
  }

  function cancelHide() {
    if (hideTimeout) {
      clearTimeout(hideTimeout);
      hideTimeout = null;
    }
  }

  /**
   * Scroll to the URL hash target after MathJax has rendered.
   * The browser's native hash-scroll fires before MathJax creates the
   * equation anchor elements, so we re-trigger it here.
   *
   * MathJax creates IDs like "mjx-eqn-eq:label" (dash prefix, literal colons).
   * The URL hash may be percent-encoded: "#mjx-eqn-eq%3Alabel".
   */
  function scrollToHash() {
    var hash = window.location.hash;
    if (!hash) return;

    // Try the raw hash first, then the decoded version
    var rawId = hash.substring(1);
    var decodedId = decodeURIComponent(rawId);
    var target = document.getElementById(rawId) || document.getElementById(decodedId);

    if (!target) {
      // MathJax may use a slightly different format — scan for matching IDs
      var allEqnIds = document.querySelectorAll('[id^="mjx-eqn"]');
      allEqnIds.forEach(function (el) {
        if (!target && (el.id === rawId || el.id === decodedId)) {
          target = el;
        }
      });
    }

    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  // Track which elements already have handlers to avoid duplicate listeners
  var handledElements = new WeakSet();

  function attachSamePageHandlers() {
    // MathJax renders \eqref{label} as <a href="#mjx-eqn-..."> links.
    var eqrefs = document.querySelectorAll('a[href^="#mjx-eqn"]');
    eqrefs.forEach(function (link) {
      if (handledElements.has(link)) return;
      handledElements.add(link);

      var rawId = link.getAttribute("href").substring(1);
      var decodedId = decodeURIComponent(rawId);

      function findTarget() {
        return (
          document.getElementById(rawId) ||
          document.getElementById(decodedId)
        );
      }

      // Tooltip on hover
      link.addEventListener("mouseenter", function () {
        cancelHide();
        var target = findTarget();
        if (!target) return;

        var container =
          target.closest("mjx-container") ||
          target.closest(".MathJax") ||
          target.closest(".MathJax_Display");
        if (!container) {
          var parent = target.parentElement;
          if (parent) {
            container = parent.querySelector("mjx-container");
          }
        }
        if (container) {
          showTooltip(link, container.outerHTML);
        }
      });

      link.addEventListener("mouseleave", scheduleHide);

    });
  }

  function attachCrossPageHandlers() {
    var refs = document.querySelectorAll("a.eq-ref[data-equation]");
    refs.forEach(function (el) {
      if (handledElements.has(el)) return;
      handledElements.add(el);

      el.addEventListener("mouseenter", function () {
        cancelHide();
        var latex = el.getAttribute("data-equation");
        if (!latex) return;

        var temp = document.createElement("div");
        temp.style.visibility = "hidden";
        temp.style.position = "absolute";
        temp.innerHTML = "$$\\notag " + latex + "$$";
        document.body.appendChild(temp);

        if (window.MathJax && MathJax.typesetPromise) {
          MathJax.typesetPromise([temp]).then(function () {
            var html = temp.innerHTML;
            document.body.removeChild(temp);
            showTooltip(el, html);
          });
        } else {
          document.body.removeChild(temp);
        }
      });

      el.addEventListener("mouseleave", scheduleHide);
    });
  }

  function init() {
    attachSamePageHandlers();
    attachCrossPageHandlers();
    scrollToHash();
  }

  // Wait for MathJax to finish rendering via the custom event
  // dispatched by mathjax-config.js (both on initial load and
  // after instant navigation re-renders).
  document.addEventListener("mathjax-done", init);
})();
