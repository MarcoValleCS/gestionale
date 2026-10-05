/* Editor semplice per le note stampabili.
 *
 * Usa i comandi nativi del browser (document.execCommand): sono marcati come
 * deprecati ma funzionano ovunque senza dipendenze esterne. Sono attivi solo
 * grassetto, corsivo, sottolineato, dimensione, elenco e allineamento: tutto il
 * resto viene comunque rimosso dal filtro sulla lista bianca lato server.
 */
(function () {
  "use strict";

  function areaOf(editor) {
    return editor.querySelector(".rich-content");
  }

  function campoNascosto(editor) {
    return editor.querySelector(".rich-hidden textarea, .rich-hidden input");
  }

  function sincronizza(editor) {
    var campo = campoNascosto(editor);
    var area = areaOf(editor);
    if (campo && area) campo.value = area.innerHTML;
  }

  function esegui(area, comando, valore) {
    area.focus();
    // fa produrre a execCommand stili CSS invece di tag obsoleti come <font>
    try { document.execCommand("styleWithCSS", false, true); } catch (e) { /* non tutti lo supportano */ }
    document.execCommand(comando, false, valore || null);
  }

  function inizializza(editor) {
    var area = areaOf(editor);
    var campo = campoNascosto(editor);
    if (!area || !campo) return;

    editor.querySelectorAll("[data-rich]").forEach(function (bottone) {
      bottone.addEventListener("click", function (evento) {
        evento.preventDefault();
        /* data-value serve ai comandi che vogliono un valore (es. formatBlock h3) */
        esegui(area, bottone.dataset.rich, bottone.dataset.value);
        sincronizza(editor);
      });
    });

    var selettore = editor.querySelector(".rich-size");
    if (selettore) {
      selettore.addEventListener("change", function () {
        if (!selettore.value) return;
        esegui(area, "fontSize", selettore.value);
        selettore.value = "";
        sincronizza(editor);
      });
    }

    area.addEventListener("input", function () { sincronizza(editor); });
    area.addEventListener("blur", function () { sincronizza(editor); });
    // incolla come testo semplice: evita di portarsi dietro stili da altri programmi
    area.addEventListener("paste", function (evento) {
      evento.preventDefault();
      var testo = (evento.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, testo);
      sincronizza(editor);
    });

    var modulo = editor.closest("form");
    if (modulo) {
      modulo.addEventListener("submit", function () { sincronizza(editor); });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".rich-editor").forEach(inizializza);
  });

  window.GestionaleRichNotes = { sincronizza: sincronizza, inizializza: inizializza };
})();
