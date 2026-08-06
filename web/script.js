(function () {
  "use strict";

  /* ----------------------------------------------------------
     Theme toggle. Defaults to the OS preference, remembers an
     explicit choice in localStorage, and keeps the two icon
     states in sync with the current root theme.
     ---------------------------------------------------------- */

  var root = document.documentElement;
  var toggle = document.getElementById("theme-toggle");
  var iconDark = document.getElementById("theme-icon-dark");
  var iconLight = document.getElementById("theme-icon-light");
  var STORAGE_KEY = "livro-theme";

  function systemPrefersDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function currentTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
    return systemPrefersDark() ? "dark" : "light";
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    var isDark = theme === "dark";
    iconDark.style.display = isDark ? "none" : "block";
    iconLight.style.display = isDark ? "block" : "none";
    toggle.setAttribute(
      "aria-label",
      isDark ? "Switch to light theme" : "Switch to dark theme"
    );
  }

  applyTheme(currentTheme());

  toggle.addEventListener("click", function () {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  });

  /* ----------------------------------------------------------
     Blog link. Points at a placeholder until the Medium piece
     is published, swap BLOG_URL below for the real one.
     ---------------------------------------------------------- */

  var BLOG_URL = "https://medium.com/@davidjrn247/how-i-built-a-whatsapp-finance-agent-on-zeroclaw-for-brazilian-freelancers-7d4e7afee3d5?sharedUserId=davidjrn247";
  var blogLink = document.getElementById("blog-link");
  if (blogLink) {
    blogLink.setAttribute("href", BLOG_URL);
    blogLink.setAttribute("target", "_blank");
  }
})();
