/* Caricamento di un modello di preventivo nel form del preventivo. */
(function () {
  "use strict";

  const select = document.getElementById("quote-template-select");
  const button = document.getElementById("load-template");
  if (!select || !button) return;

  function fillIfEmpty(id, value) {
    const field = document.getElementById(id);
    if (!field || !value) return;
    if (String(field.value || "").trim() !== "") return;
    field.value = value;
  }

  function showFeedback(message, isError) {
    const box = document.getElementById("template-feedback");
    if (!box) return;
    box.innerHTML = "<i class='bi " + (isError ? "bi-exclamation-triangle" : "bi-check-circle") + "'></i> " + message;
    box.className = "alert py-2 small mb-3 " + (isError ? "alert-warning" : "alert-info");
    box.classList.remove("d-none");
  }

  button.addEventListener("click", function () {
    if (!select.value) {
      select.focus();
      showFeedback("Scegli prima un modello dall'elenco.", true);
      return;
    }
    const api = window.GestionaleLines;
    if (!api) return;

    const url = button.dataset.url.replace("/0/", "/" + select.value + "/");
    button.disabled = true;
    fetch(url)
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (!data) {
          showFeedback("Impossibile caricare il modello.", true);
          return;
        }
        data.lines.forEach(function (line) {
          api.addRow({
            product: line.product,
            productLabel: line.product_label,
            description: line.description,
            qty: line.qty,
            uom: line.uom,
            unitPrice: line.unit_price,
            discount: line.discount_pct,
            vat: line.vat_rate,
          });
        });
        fillIfEmpty("id_payment_term", data.template.payment_term);
        fillIfEmpty("id_terms_text", data.template.terms_text);
        fillIfEmpty("id_notes", data.template.notes);
        showFeedback("Modello «" + data.template.name + "» caricato: " + data.lines.length + " righe aggiunte.", false);
      })
      .catch(function () {
        showFeedback("Errore di rete durante il caricamento del modello.", true);
      })
      .finally(function () {
        button.disabled = false;
      });
  });
})();
