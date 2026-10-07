/* Creazione rapida di clienti/fornitori e articoli dai documenti. */
(function () {
  "use strict";

  function csrfToken(form) {
    const input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function clearErrors(form) {
    form.querySelectorAll("[data-error-for]").forEach(function (el) { el.textContent = ""; });
    const generic = form.querySelector(".quick-generic-error");
    if (generic) { generic.textContent = ""; generic.classList.add("d-none"); }
  }

  function showErrors(form, errors) {
    let hasGeneric = false;
    Object.keys(errors || {}).forEach(function (field) {
      const target = form.querySelector('[data-error-for="' + field + '"]');
      const messages = errors[field] || [];
      if (target) {
        target.textContent = messages.join(" ");
      } else {
        hasGeneric = true;
      }
    });
    const generic = form.querySelector(".quick-generic-error");
    if (generic && hasGeneric) {
      generic.textContent = "Controlla i dati inseriti.";
      generic.classList.remove("d-none");
    }
  }

  function submitJson(form, extraData) {
    const data = new FormData(form);
    if (extraData) {
      Object.keys(extraData).forEach(function (key) { data.set(key, extraData[key]); });
    }
    return fetch(form.action, {
      method: "POST",
      body: data,
      headers: { "X-CSRFToken": csrfToken(form) },
    }).then(function (response) {
      return response.json().then(function (json) {
        return { ok: response.ok, json: json };
      });
    });
  }

  /* --------------------------------------------------------- contatti */
  const contactModalEl = document.getElementById("quick-contact-modal");
  if (contactModalEl) {
    const contactForm = contactModalEl.querySelector("form");
    const contactModal = function () { return bootstrap.Modal.getOrCreateInstance(contactModalEl); };

    document.querySelectorAll("[data-quick-contact]").forEach(function (button) {
      button.addEventListener("click", function () {
        clearErrors(contactForm);
        contactForm.reset();
        contactForm.dataset.kind = button.dataset.kind || "customer";
        contactForm.dataset.target = button.dataset.target;
        const title = contactModalEl.querySelector(".quick-contact-title");
        if (title) {
          title.textContent = contactForm.dataset.kind === "supplier" ? "Nuovo fornitore" : "Nuovo cliente";
        }
        contactModal().show();
        window.setTimeout(function () {
          const nameInput = contactForm.querySelector('input[name="name"]');
          if (nameInput) nameInput.focus();
        }, 250);
      });
    });

    contactForm.addEventListener("submit", function (event) {
      event.preventDefault();
      clearErrors(contactForm);
      submitJson(contactForm, { kind: contactForm.dataset.kind }).then(function (result) {
        if (!result.ok) { showErrors(contactForm, result.json.errors); return; }
        const select = document.querySelector(contactForm.dataset.target);
        if (select) {
          select.add(new Option(result.json.label, result.json.id, true, true));
          select.dispatchEvent(new Event("change", { bubbles: true }));
        }
        contactModal().hide();
      }).catch(function () {
        showErrors(contactForm, {});
        const generic = contactForm.querySelector(".quick-generic-error");
        if (generic) { generic.textContent = "Errore di rete: riprova."; generic.classList.remove("d-none"); }
      });
    });
  }

  /* --------------------------------------------------------- articoli */
  const productModalEl = document.getElementById("quick-product-modal");
  if (productModalEl) {
    const productForm = productModalEl.querySelector("form");
    const productModal = function () { return bootstrap.Modal.getOrCreateInstance(productModalEl); };
    let currentSelect = null;

    const supplierSelect = productForm.querySelector('select[name="main_supplier"]');
    const saleInput = productForm.querySelector('input[name="sale_price"]');
    const priceInput = productForm.querySelector('input[name="purchase_price"]');
    const priceHint = productForm.querySelector("#qp-purchase-hint");

    function aggiornaPrezzoNetto() {
      if (!priceHint || !priceInput) return;
      priceHint.textContent = "";
      const option = supplierSelect ? supplierSelect.options[supplierSelect.selectedIndex] : null;
      const sconto = option ? parseFloat((option.dataset.sconto || "0").replace(",", ".")) : 0;
      if (sconto <= 0) return;
      const vendita = parseFloat(((saleInput && saleInput.value) || "0").replace(",", "."));
      if (vendita > 0) {
        const netto = vendita * (1 - sconto / 100);
        priceInput.value = netto.toFixed(2);
        priceHint.textContent = "Prezzo consigliato in base allo sconto abituale: " +
          netto.toFixed(2).replace(".", ",") + " €";
      } else {
        priceHint.textContent = "Prezzo consigliato in base allo sconto abituale: —";
      }
    }
    if (saleInput) saleInput.addEventListener("input", aggiornaPrezzoNetto);
    if (supplierSelect) supplierSelect.addEventListener("change", aggiornaPrezzoNetto);

    document.addEventListener("click", function (event) {
      const button = event.target.closest("[data-quick-product]");
      if (!button) return;
      const row = button.closest("tr");
      currentSelect = row ? row.querySelector('select[name$="-product"]') : null;
      if (!currentSelect) return;
      clearErrors(productForm);
      productForm.reset();
      aggiornaPrezzoNetto();
      productForm.dataset.context = currentSelect.dataset.context || "sale";
      productModal().show();
      window.setTimeout(function () {
        const nameInput = productForm.querySelector('input[name="name"]');
        if (nameInput) nameInput.focus();
      }, 250);
    });

    productForm.addEventListener("submit", function (event) {
      event.preventDefault();
      clearErrors(productForm);
      submitJson(productForm, { context: productForm.dataset.context || "sale" }).then(function (result) {
        if (!result.ok) { showErrors(productForm, result.json.errors); return; }
        if (currentSelect) {
          currentSelect.add(new Option(result.json.label, result.json.id, true, true));
          currentSelect.value = result.json.id;
          currentSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
        productModal().hide();
        currentSelect = null;
      }).catch(function () {
        const generic = productForm.querySelector(".quick-generic-error");
        if (generic) { generic.textContent = "Errore di rete: riprova."; generic.classList.remove("d-none"); }
      });
    });
  }
})();
