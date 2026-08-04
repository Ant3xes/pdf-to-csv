(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const indicator = document.getElementById("processing-indicator");
  const errorMessage = document.getElementById("error-message");
  const tableBody = document.querySelector("#results-table tbody");
  const exportButton = document.getElementById("export-csv");

  const EDITABLE_FIELDS = ["emetteur", "date", "montant_ttc"];
  const FIELD_PLACEHOLDERS = {
    emetteur: "Émetteur",
    date: "JJ/MM/AAAA",
    montant_ttc: "Montant TTC",
  };
  /** État éphémère du Lot en cours (Correction manuelle locale, hors Template). */
  let lotLignes = [];
  /** filename → object URL des PDF déposés (éphémère, côté navigateur uniquement). */
  const pdfUrls = new Map();

  function statutLabel(statut) {
    return statut === "A_VERIFIER" ? "À vérifier" : statut;
  }

  function displayValue(value) {
    return value == null || value === "" ? "—" : String(value);
  }

  function inputValue(value) {
    return value == null || value === "" ? "" : String(value);
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = !message;
  }

  function setProcessing(active) {
    indicator.hidden = !active;
  }

  function syncExportButton() {
    exportButton.disabled = lotLignes.length === 0;
  }

  function clearPdfUrls() {
    for (const url of pdfUrls.values()) {
      URL.revokeObjectURL(url);
    }
    pdfUrls.clear();
  }

  function rememberPdfFiles(files) {
    clearPdfUrls();
    for (const file of files) {
      pdfUrls.set(file.name, URL.createObjectURL(file));
    }
  }

  function corrigerLigneLocale(index, champ, valeur) {
    const ligne = lotLignes[index];
    if (!ligne || !EDITABLE_FIELDS.includes(champ)) {
      return;
    }
    const cleaned = valeur.trim();
    lotLignes[index] = {
      ...ligne,
      [champ]: cleaned === "" ? null : cleaned,
    };
  }

  function renderLignes(lignes) {
    lotLignes = lignes.map((ligne) => ({ ...ligne }));
    tableBody.replaceChildren();
    lotLignes.forEach((ligne, index) => {
      const tr = document.createElement("tr");
      for (const key of ["fichier", "emetteur", "date", "montant_ttc", "statut"]) {
        const td = document.createElement("td");
        if (key === "statut") {
          td.textContent = statutLabel(ligne[key]);
        } else if (EDITABLE_FIELDS.includes(key)) {
          const input = document.createElement("input");
          input.type = "text";
          input.value = inputValue(ligne[key]);
          input.placeholder = FIELD_PLACEHOLDERS[key] || "";
          input.setAttribute("aria-label", FIELD_PLACEHOLDERS[key] || key);
          input.addEventListener("input", () => {
            corrigerLigneLocale(index, key, input.value || "");
          });
          td.appendChild(input);
        } else {
          td.textContent = displayValue(ligne[key]);
        }
        tr.appendChild(td);
      }
      const tdPdf = document.createElement("td");
      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "ouvrir-pdf";
      openBtn.textContent = "Ouvrir le PDF";
      const pdfUrl = pdfUrls.get(ligne.fichier);
      if (pdfUrl) {
        openBtn.addEventListener("click", () => {
          window.open(pdfUrl, "_blank", "noopener,noreferrer");
        });
      } else {
        openBtn.disabled = true;
        openBtn.title = "PDF indisponible pour ce Lot";
      }
      tdPdf.appendChild(openBtn);
      tr.appendChild(tdPdf);
      tableBody.appendChild(tr);
    });
    syncExportButton();
  }

  async function exportLotCsv() {
    if (lotLignes.length === 0) {
      return;
    }
    showError("");
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lignes: lotLignes }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        showError(payload.error || "Échec de l'export CSV.");
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "factures.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      showError("Impossible de contacter le serveur.");
    }
  }

  async function uploadLot(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) {
      return;
    }

    showError("");
    setProcessing(true);
    rememberPdfFiles(files);

    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file, file.name);
    }

    try {
      const response = await fetch("/api/lot", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        clearPdfUrls();
        showError(payload.error || "Échec du traitement du lot.");
        return;
      }
      renderLignes(payload.lignes || []);
    } catch (err) {
      clearPdfUrls();
      showError("Impossible de contacter le serveur.");
    } finally {
      setProcessing(false);
      fileInput.value = "";
    }
  }

  dropZone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", (event) => {
    if (!dropZone.contains(event.relatedTarget)) {
      dropZone.classList.remove("drag-over");
    }
  });
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-over");
    uploadLot(event.dataTransfer.files);
  });

  fileInput.addEventListener("change", () => {
    uploadLot(fileInput.files);
  });

  exportButton.addEventListener("click", () => {
    exportLotCsv();
  });
  syncExportButton();
})();
