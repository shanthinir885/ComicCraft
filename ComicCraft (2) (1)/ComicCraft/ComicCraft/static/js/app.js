/**
 * ComicCraft front-end controller.
 * Vanilla JS only: navigation, selection groups, validation, progress UI,
 * toasts, comic reader controls and lightbox zoom.
 */
(function () {
  "use strict";

  var REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------- utils */
  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }
  function $$(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  /* --------------------------------------------------------------- toasts */
  function toast(message, variant) {
    var stack = $("#toastStack");
    if (!stack) return;
    var node = document.createElement("div");
    node.className = "toast toast--" + (variant || "info");
    node.textContent = message;
    stack.appendChild(node);
    window.setTimeout(function () {
      node.style.opacity = "0";
      window.setTimeout(function () {
        if (node.parentNode) node.parentNode.removeChild(node);
      }, 300);
    }, 4600);
  }
  window.comicCraftToast = toast;

  /* ----------------------------------------------------------- navigation */
  function initNavigation() {
    var toggle = $("#navToggle");
    var menu = $("#navMenu");
    if (!toggle || !menu) return;

    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
    });

    $$(".nav__link, .btn--nav", menu).forEach(function (link) {
      link.addEventListener("click", function () {
        menu.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && menu.classList.contains("is-open")) {
        menu.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  /* ------------------------------------------------- selection chip groups */
  function initSelectionGroups() {
    $$("[data-group]").forEach(function (group) {
      var name = group.getAttribute("data-group");
      var hidden = document.getElementById(name);
      var options = $$('[role="radio"]', group);
      if (!hidden || !options.length) return;

      function select(option) {
        options.forEach(function (item) {
          item.setAttribute("aria-checked", String(item === option));
          item.tabIndex = item === option ? 0 : -1;
        });
        var value = option.getAttribute("data-value");
        if (value === "__custom__") {
          var custom = $("#custom_setting");
          if (custom) {
            custom.hidden = false;
            custom.focus();
            hidden.value = custom.value.trim();
          }
        } else {
          var customInput = $("#custom_setting");
          if (customInput && name === "setting") customInput.hidden = true;
          hidden.value = value;
        }
        clearFieldError(group.closest(".field"));
      }

      options.forEach(function (option, index) {
        option.tabIndex = index === 0 ? 0 : -1;
        option.addEventListener("click", function () {
          select(option);
        });
        option.addEventListener("keydown", function (event) {
          var next = null;
          if (event.key === "ArrowRight" || event.key === "ArrowDown") next = options[(index + 1) % options.length];
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = options[(index - 1 + options.length) % options.length];
          if (next) {
            event.preventDefault();
            next.focus();
            select(next);
          }
        });
      });
    });

    var custom = $("#custom_setting");
    if (custom) {
      custom.addEventListener("input", function () {
        var hidden = $("#setting");
        if (hidden) hidden.value = custom.value.trim();
      });
    }
  }

  /* ------------------------------------------------------ character count */
  function initCounter() {
    var textarea = $("#story_prompt");
    var counter = $("#promptCounter");
    if (!textarea || !counter) return;

    var max = parseInt(textarea.getAttribute("maxlength"), 10) || 1000;
    function update() {
      counter.textContent = textarea.value.length + " / " + max;
      counter.classList.toggle("is-limit", textarea.value.length > max * 0.9);
    }
    textarea.addEventListener("input", function () {
      update();
      clearFieldError(textarea.closest(".field"));
    });
    update();
  }

  /* ---------------------------------------------------------- validation */
  function setFieldError(field, errorId, message) {
    if (field) field.classList.add("has-error");
    var node = document.getElementById(errorId);
    if (node) node.textContent = message;
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove("has-error");
    var node = $(".field__error", field);
    if (node) node.textContent = "";
  }

  function validateForm(form) {
    var errors = 0;
    $$(".field", form).forEach(clearFieldError);

    var prompt = $("#story_prompt", form);
    if (!prompt.value.trim() || prompt.value.trim().length < 10) {
      setFieldError(prompt.closest(".field"), "promptError", "Tell us a little more — at least 10 characters.");
      errors += 1;
    }

    var character = $("#character_name", form);
    if (!character.value.trim()) {
      setFieldError(character.closest(".field"), "characterError", "Your hero needs a name.");
      errors += 1;
    }

    var groups = [
      { id: "setting", errorId: "settingError", message: "Pick a setting for your story." },
      { id: "tone", errorId: "toneError", message: "Choose the tone of your comic." },
      { id: "art_style", errorId: "styleError", message: "Choose an art style." }
    ];

    groups.forEach(function (group) {
      var input = document.getElementById(group.id);
      if (!input || !input.value.trim()) {
        setFieldError(input ? input.closest(".field") : null, group.errorId, group.message);
        errors += 1;
      }
    });

    if (errors > 0) {
      var firstError = $(".field.has-error", form);
      if (firstError) {
        firstError.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "center" });
        var focusable = $("textarea, input:not([type=hidden]), button", firstError);
        if (focusable) focusable.focus({ preventScroll: true });
      }
      toast("Please complete the highlighted fields.", "error");
    }

    return errors === 0;
  }

  /* ------------------------------------------------------- loading states */
  var LOADING_MESSAGES = [
    "Writing your story...",
    "Designing your scenes...",
    "Creating your characters...",
    "Illustrating your panels...",
    "Assembling your comic..."
  ];
  var STEP_TIMINGS = [0, 4000, 11000, 20000, 48000];
  var timers = [];

  function startLoading() {
    var overlay = $("#loadingOverlay");
    if (!overlay) return;

    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";

    var steps = $$(".progress-step");
    var message = $("#loadingMessage");

    function activate(index) {
      steps.forEach(function (step, position) {
        step.classList.toggle("is-done", position < index);
        step.classList.toggle("is-active", position === index);
      });
      if (message && LOADING_MESSAGES[index]) message.textContent = LOADING_MESSAGES[index];
    }

    activate(0);
    STEP_TIMINGS.forEach(function (delay, index) {
      if (index === 0) return;
      timers.push(window.setTimeout(function () { activate(index); }, delay));
    });
  }

  function stopLoading() {
    timers.forEach(window.clearTimeout);
    timers = [];
    var overlay = $("#loadingOverlay");
    if (overlay) {
      overlay.hidden = true;
      overlay.setAttribute("aria-hidden", "true");
    }
    document.body.style.overflow = "";
  }

  /* -------------------------------------------------------- comic form UI */
  function initComicForm() {
    var form = $("#comicForm");
    if (!form) return;

    var button = $("#generateBtn");
    var label = button ? $(".btn__label", button) : null;
    var submitting = false;

    form.addEventListener("submit", function (event) {
      if (submitting) {
        event.preventDefault();
        return;
      }
      if (!validateForm(form)) {
        event.preventDefault();
        return;
      }
      submitting = true;
      if (button) {
        button.classList.add("is-busy");
        button.disabled = true;
      }
      if (label) label.textContent = "Creating Your Comic...";
      toast("Comic generation started", "info");
      startLoading();
    });

    window.addEventListener("pageshow", function () {
      submitting = false;
      stopLoading();
      if (button) {
        button.classList.remove("is-busy");
        button.disabled = false;
      }
      if (label) label.textContent = "Generate My Comic";
    });

    if ($("#serverError")) {
      toast("Something went wrong. Please try again.", "error");
    }
  }

  /* ------------------------------------------------------- reader controls */
  function initReader() {
    var grid = $("#comicGrid");
    if (!grid) return;

    var panels = $$(".panel", grid);
    var pager = $("#pager");
    var status = $("#pagerStatus");
    var prev = $("#prevPanel");
    var next = $("#nextPanel");
    var current = 0;

    function render() {
      panels.forEach(function (panel, index) {
        panel.classList.toggle("is-active", index === current);
      });
      if (status) status.textContent = "Panel " + (current + 1) + " / " + panels.length;
      if (prev) prev.disabled = current === 0;
      if (next) next.disabled = current === panels.length - 1;
    }

    function setView(view) {
      var single = view === "single";
      grid.classList.toggle("is-single", single);
      if (pager) pager.hidden = !single;
      $$(".view-switch__btn").forEach(function (button) {
        var active = button.getAttribute("data-view") === view;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      if (single) render();
    }

    $$(".view-switch__btn").forEach(function (button) {
      button.addEventListener("click", function () {
        setView(button.getAttribute("data-view"));
      });
    });

    if (prev) prev.addEventListener("click", function () {
      current = Math.max(0, current - 1);
      render();
      panels[current].scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "start" });
    });

    if (next) next.addEventListener("click", function () {
      current = Math.min(panels.length - 1, current + 1);
      render();
      panels[current].scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "start" });
    });

    document.addEventListener("keydown", function (event) {
      if (!grid.classList.contains("is-single")) return;
      if (event.key === "ArrowRight" && next) next.click();
      if (event.key === "ArrowLeft" && prev) prev.click();
    });

    render();
    toast("Comic generated successfully", "success");

    var download = $("#downloadBtn");
    if (download) {
      download.addEventListener("click", function () {
        toast("PDF exported successfully", "success");
        var section = $(".reader");
        var pdfUrl = section ? section.getAttribute("data-pdf-url") : "";
        var title = section ? section.getAttribute("data-title") : "";
        window.setTimeout(function () {
          window.location.href =
            "/export-success?pdf_url=" + encodeURIComponent(pdfUrl) + "&title=" + encodeURIComponent(title);
        }, 1400);
      });
    }
  }

  /* ------------------------------------------------------------- lightbox */
  function initLightbox() {
    var lightbox = $("#lightbox");
    if (!lightbox) return;

    var image = $("#lightboxImg");
    var close = $("#lightboxClose");
    var lastTrigger = null;

    $$(".panel__zoom").forEach(function (button) {
      button.addEventListener("click", function () {
        lastTrigger = button;
        image.src = button.getAttribute("data-zoom-src");
        image.alt = button.getAttribute("data-zoom-alt") || "Comic panel";
        lightbox.hidden = false;
        close.focus();
      });
    });

    function hide() {
      lightbox.hidden = true;
      image.src = "";
      if (lastTrigger) lastTrigger.focus();
    }

    close.addEventListener("click", hide);
    lightbox.addEventListener("click", function (event) {
      if (event.target === lightbox) hide();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !lightbox.hidden) hide();
    });
  }

  /* ------------------------------------------------------------ bootstrap */
  document.addEventListener("DOMContentLoaded", function () {
    initNavigation();
    initSelectionGroups();
    initCounter();
    initComicForm();
    initReader();
    initLightbox();
  });
})();
