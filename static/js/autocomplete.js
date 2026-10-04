/* Ricerca a digitazione (autocomplete) per clienti, fornitori e articoli. */
(function () {
  "use strict";

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function closeAll() {
    document.querySelectorAll(".autocomplete-menu").forEach(function (menu) { menu.remove(); });
  }

  function selectFor(input) {
    const selector = input.dataset.target || "";
    if (!selector.startsWith("#")) return null;
    return document.getElementById(selector.slice(1));
  }

  function syncInputFromSelect(select) {
    const input = document.querySelector('[data-target="#' + select.id + '"]');
    if (!input) return;
    const option = select.selectedOptions[0];
    /* L'opzione vuota («---------») non è una selezione: il campo resta vuoto */
    input.value = option && option.value ? option.text : "";
  }

  function positionMenu(menu, input) {
    const rect = input.getBoundingClientRect();
    const height = menu.offsetHeight || 240;
    let top = rect.bottom + 4;
    if (top + height > window.innerHeight - 8) {
      top = Math.max(8, rect.top - height - 4);
    }
    menu.style.top = top + "px";
    menu.style.left = rect.left + "px";
    menu.style.width = Math.max(rect.width, 260) + "px";
  }

  function renderMenu(input, results) {
    closeAll();
    const wrap = input.closest(".autocomplete-wrap") || input.parentElement;
    const menu = document.createElement("div");
    menu.className = "autocomplete-menu";
    menu.style.position = "fixed";

    results.forEach(function (item) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "autocomplete-item";
      const label = document.createElement("span");
      label.className = "ac-label";
      label.textContent = item.label;
      const extra = document.createElement("span");
      extra.className = "ac-extra";
      extra.textContent = item.extra || "";
      button.appendChild(label);
      button.appendChild(extra);
      button.addEventListener("click", function () {
        const select = selectFor(input);
        if (select) {
          let option = Array.prototype.find.call(select.options, function (o) { return o.value === String(item.id); });
          if (!option) {
            option = new Option(item.label, item.id, true, true);
            select.add(option);
          }
          select.value = option.value;
          select.dispatchEvent(new Event("change", { bubbles: true }));
        }
        input.value = item.label;
        input.classList.remove("is-invalid");
        menu.remove();
      });
      menu.appendChild(button);
    });

    if (!results.length) {
      const empty = document.createElement("div");
      empty.className = "autocomplete-empty";
      empty.textContent = "Nessun risultato";
      menu.appendChild(empty);
    }

    const query = input.value.trim();
    const createButton = document.createElement("button");
    createButton.type = "button";
    createButton.className = "autocomplete-item autocomplete-create";
    createButton.innerHTML = "<span><i class='bi bi-plus-lg'></i> " +
      (query ? "Crea «" + escapeHtml(query) + "»" : "Crea nuovo") + "</span>";
    createButton.addEventListener("click", function () {
      const trigger = wrap.querySelector("[data-quick-contact], [data-quick-product]");
      menu.remove();
      if (!trigger) return;
      trigger.click();
      const modalNameId = trigger.hasAttribute("data-quick-contact") ? "qc-name" : "qp-name";
      const nameInput = document.getElementById(modalNameId);
      if (nameInput && query) {
        nameInput.value = query;
        nameInput.focus();
      }
    });
    menu.appendChild(createButton);

    document.body.appendChild(menu);
    menu._acInput = input;
    positionMenu(menu, input);
  }

  function fetchSuggestions(input) {
    const url = input.dataset.autocomplete;
    if (!url) return;
    const params = new URLSearchParams();
    params.set("q", input.value.trim());
    if (input.dataset.kind) params.set("kind", input.dataset.kind);
    const select = selectFor(input);
    if (select && select.dataset.context) params.set("context", select.dataset.context);

    fetch(url + "?" + params.toString())
      .then(function (response) { return response.ok ? response.json() : { results: [] }; })
      .then(function (data) { renderMenu(input, data.results || []); })
      .catch(function () { /* rete non disponibile: nessun suggerimento */ });
  }

  /* Sincronizza il testo mostrato con la selezione del campo (anche per la creazione rapida) */
  document.querySelectorAll("select[data-autocomplete-target]").forEach(syncInputFromSelect);

  document.addEventListener("change", function (event) {
    const select = event.target && event.target.closest ? event.target.closest("select[data-autocomplete-target]") : null;
    if (select) syncInputFromSelect(select);
  });

  document.addEventListener("input", function (event) {
    const input = event.target.closest ? event.target.closest("[data-autocomplete]") : null;
    if (!input) return;
    /* Se si svuota il campo, si azzera anche la selezione nascosta */
    if (input.value.trim() === "") {
      const select = selectFor(input);
      if (select) select.value = "";
    }
    clearTimeout(input._acTimer);
    input._acTimer = setTimeout(function () { fetchSuggestions(input); }, 180);
  });

  document.addEventListener("focusin", function (event) {
    const input = event.target.closest ? event.target.closest("[data-autocomplete]") : null;
    if (input) fetchSuggestions(input);
  });

  document.addEventListener("click", function (event) {
    const target = event.target;
    if (!target || !target.closest) return;
    /* La tendina sta fuori dal campo: un click sulla sua barra di scorrimento
       non deve chiuderla. */
    if (target.closest(".autocomplete-wrap") || target.closest(".autocomplete-menu")) return;
    closeAll();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    const input = event.target.closest ? event.target.closest("[data-autocomplete]") : null;
    if (input) closeAll();
  });

  /* Lo scorrimento della pagina sposta il campo: la tendina lo segue invece di
     chiudersi. Lo scorrimento DENTRO la tendina (per cercare fra i risultati)
     non la chiude di certo. */
  function repositionMenus() {
    document.querySelectorAll(".autocomplete-menu").forEach(function (menu) {
      const input = menu._acInput;
      if (!input) return;
      const rect = input.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        menu.remove(); // il campo è uscito dallo schermo
        return;
      }
      positionMenu(menu, input);
    });
  }

  let scrollFrame = null;
  document.addEventListener(
    "scroll",
    function (event) {
      const target = event.target;
      if (target && target.closest && target.closest(".autocomplete-menu")) return;
      if (scrollFrame) return;
      scrollFrame = requestAnimationFrame(function () {
        scrollFrame = null;
        repositionMenus();
      });
    },
    true
  );
  window.addEventListener("resize", function () { closeAll(); });
})();
