(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const indicator = document.getElementById("processing-indicator");
  const errorMessage = document.getElementById("error-message");
  const exportBlockMessage = document.getElementById("export-block-message");
  const totauxEmetteursSection = document.getElementById("totaux-emetteurs");
  const totauxEmetteursList = document.getElementById("totaux-emetteurs-list");
  const facturesCount = document.getElementById("factures-count");
  const avoirsCount = document.getElementById("avoirs-count");
  const issuerGroups = document.getElementById("issuer-groups");
  const exportDetailButton = document.getElementById("export-csv-detail");
  const exportAgregeButton = document.getElementById("export-csv-agrege");
  const exportJournalButton = document.getElementById("export-journal");
  const resetLotButton = document.getElementById("reset-lot");
  const appShell = document.querySelector(".app-shell");
  const splitHandle = document.getElementById("split-handle");
  const mainPane = document.getElementById("main-pane");
  const previewPane = document.getElementById("preview-pane");
  const mainZoomStage = document.getElementById("main-zoom-stage");
  const previewContent = document.getElementById("preview-content");
  const previewPlaceholder = document.getElementById("preview-placeholder");
  const previewFilename = document.getElementById("preview-filename");
  const mainZoomOut = document.getElementById("main-zoom-out");
  const mainZoomIn = document.getElementById("main-zoom-in");
  const mainZoomReset = document.getElementById("main-zoom-reset");
  const previewZoomOut = document.getElementById("preview-zoom-out");
  const previewZoomIn = document.getElementById("preview-zoom-in");
  const previewZoomReset = document.getElementById("preview-zoom-reset");

  const TYPE_FACTURE = "FACTURE";
  const TYPE_AVOIR = "AVOIR";
  const EDITABLE_FIELDS = ["emetteur", "date", "montant_ht"];
  const SUPPORTED_SUFFIXES = [".pdf", ".jpg", ".jpeg", ".png", ".heic"];
  const SUPPORTED_FORMATS_LABEL = SUPPORTED_SUFFIXES.join(", ");
  const FIELD_PLACEHOLDERS = {
    emetteur: "Émetteur",
    date: "JJ/MM/AAAA",
    montant_ht: "Montant HT",
  };
  const TABLE_COLUMN_COUNT = 8;
  const PANE_ZOOM_MIN = 0.5;
  const PANE_ZOOM_MAX = 3;
  const PANE_ZOOM_STEP = 0.1;
  /** État éphémère du Lot en cours (Correction manuelle locale, hors Template). */
  let lotLignes = [];
  /** Journal de diagnostic disponible côté serveur pour le Lot courant. */
  let journalDisponible = false;
  /** Incrémenté à chaque reset pour ignorer les réponses d’upload obsolètes. */
  let lotGeneration = 0;
  /** filename → object URL pour ouvrir le fichier (éphémère, côté navigateur uniquement). */
  const fileUrls = new Map();
  /** filename → File déposé (conservé pour conversion HEIC à l'ouverture). */
  const depositedFiles = new Map();
  /** Fichier actuellement affiché dans le panneau d'aperçu (null si vide). */
  let previewedFilename = null;
  /** Incrémenté à chaque rendu d’aperçu pour ignorer les assignations src obsolètes. */
  let previewRenderToken = 0;
  /** Dernier panneau survolé / ciblé pour raccourcis clavier et molette. */
  let activeZoomPane = "main";
  let mainZoom = 1;
  let previewZoom = 1;

  let heic2anyLoadPromise = null;
  let pdfJsLoadPromise = null;

  function isHeicFile(file) {
    const lower = file.name.toLowerCase();
    return (
      lower.endsWith(".heic") ||
      lower.endsWith(".heif") ||
      file.type === "image/heic" ||
      file.type === "image/heif"
    );
  }

  function loadHeic2any() {
    if (typeof heic2any !== "undefined") {
      return Promise.resolve(heic2any);
    }
    if (!heic2anyLoadPromise) {
      heic2anyLoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "/static/vendor/heic2any.min.js";
        script.onload = () => resolve(window.heic2any);
        script.onerror = () => reject(new Error("heic2any indisponible"));
        document.head.appendChild(script);
      });
    }
    return heic2anyLoadPromise;
  }

  function loadPdfJs() {
    if (typeof pdfjsLib !== "undefined") {
      pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdf.worker.min.js";
      return Promise.resolve(pdfjsLib);
    }
    if (!pdfJsLoadPromise) {
      pdfJsLoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "/static/vendor/pdf.min.js";
        script.onload = () => {
          const lib = window.pdfjsLib;
          if (!lib) {
            reject(new Error("pdf.js indisponible"));
            return;
          }
          lib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdf.worker.min.js";
          resolve(lib);
        };
        script.onerror = () => reject(new Error("pdf.js indisponible"));
        document.head.appendChild(script);
      });
    }
    return pdfJsLoadPromise;
  }

  async function createHeicPreviewUrl(file) {
    const converter = await loadHeic2any();
    const converted = await converter({
      blob: file,
      toType: "image/jpeg",
      quality: 0.85,
    });
    const blob = Array.isArray(converted) ? converted[0] : converted;
    return URL.createObjectURL(blob);
  }

  function isSupportedDocumentName(filename) {
    const lower = String(filename).toLowerCase();
    return SUPPORTED_SUFFIXES.some((suffix) => lower.endsWith(suffix));
  }

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

  function montantParEmetteurMap() {
    return new Map(
      LotGrouping.agregerParEmetteur(lotLignes).map((total) => [
        total.emetteur,
        total.montant_ht,
      ]),
    );
  }

  function formaterMontantAffichage(montant) {
    const [entier, decimales = "00"] = String(montant).split(",");
    const entierFormate = entier.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return `${entierFormate},${decimales}`;
  }

  function champsManquants(ligne) {
    return EDITABLE_FIELDS.filter((key) => {
      const value = ligne[key];
      return value == null || String(value).trim() === "";
    });
  }

  function labelChamp(key) {
    return FIELD_PLACEHOLDERS[key] || key;
  }

  function renderTotauxBanner() {
    const totaux = LotGrouping.agregerParEmetteur(lotLignes);
    totauxEmetteursList.replaceChildren();
    if (totaux.length === 0) {
      totauxEmetteursSection.hidden = true;
      return;
    }
    totauxEmetteursSection.hidden = false;
    for (const total of totaux) {
      const item = document.createElement("li");
      item.className = "totaux-emetteur-card";
      if (total.emetteur_manquant) {
        item.classList.add("emetteur-manquant");
      }
      const montantNumerique = LotGrouping.parseMontantHt(total.montant_ht);
      if (montantNumerique < 0) {
        item.classList.add("montant-negatif");
      }

      const nom = document.createElement("p");
      nom.className = "totaux-emetteur-nom";
      nom.textContent = total.emetteur;

      const montant = document.createElement("p");
      montant.className = "totaux-emetteur-montant";
      montant.textContent = `${formaterMontantAffichage(total.montant_ht)} €`;

      const meta = document.createElement("p");
      meta.className = "totaux-emetteur-meta";
      const labelDoc = total.nb_documents > 1 ? "documents" : "document";
      meta.textContent = `${total.nb_documents} ${labelDoc}`;

      item.append(nom, montant, meta);
      const lignesEmetteur = lotLignes.filter(
        (ligne) => LotGrouping.cleEmetteur(ligne.emetteur) === total.emetteur,
      );
      const manques = new Set();
      for (const ligne of lignesEmetteur) {
        for (const champ of champsManquants(ligne)) {
          manques.add(labelChamp(champ));
        }
      }
      if (manques.size > 0) {
        item.classList.add("incomplet");
        const warning = document.createElement("div");
        warning.className = "totaux-emetteur-warning";

        const warningTitle = document.createElement("p");
        warningTitle.className = "totaux-emetteur-warning-title";
        warningTitle.textContent = "Champs à remplir";

        const warningList = document.createElement("p");
        warningList.className = "totaux-emetteur-warning-list";
        warningList.textContent = Array.from(manques).join(" • ");

        warning.append(warningTitle, warningList);
        item.appendChild(warning);
      }
      totauxEmetteursList.appendChild(item);
    }
  }

  function syncExportJournalButton() {
    if (exportJournalButton) {
      exportJournalButton.disabled = !journalDisponible;
    }
  }

  function syncExportButton() {
    syncExportJournalButton();
    const disabled = lotLignes.length === 0;
    if (exportDetailButton) {
      exportDetailButton.disabled = disabled;
    }
    if (exportAgregeButton) {
      exportAgregeButton.disabled = disabled;
    }
    if (disabled) {
      exportBlockMessage.hidden = true;
      exportBlockMessage.textContent = "";
    }
  }

  function refreshGroupingUi() {
    renderTotauxBanner();
    syncExportButton();
  }

  function clearPreview() {
    previewRenderToken += 1;
    previewedFilename = null;
    previewContent.replaceChildren();
    previewPlaceholder.hidden = false;
    previewFilename.hidden = true;
    previewFilename.textContent = "";
  }

  function isPdfFilename(filename) {
    return String(filename).toLowerCase().endsWith(".pdf");
  }

  function clampPaneZoom(value) {
    const stepped = Math.round(value / PANE_ZOOM_STEP) * PANE_ZOOM_STEP;
    return Math.min(PANE_ZOOM_MAX, Math.max(PANE_ZOOM_MIN, Number(stepped.toFixed(2))));
  }

  function applyZoomTransform(element, zoom) {
    if (!element) {
      return;
    }
    element.style.transformOrigin = "0 0";
    if (zoom === 1) {
      element.style.transform = "";
      element.style.width = "";
    } else {
      element.style.transform = `scale(${zoom})`;
      element.style.width = `${100 / zoom}%`;
    }
  }

  function syncZoomControls(zoom, outBtn, inBtn, resetBtn) {
    if (!resetBtn || !outBtn || !inBtn) {
      return;
    }
    resetBtn.textContent = `${Math.round(zoom * 100)}%`;
    outBtn.disabled = zoom <= PANE_ZOOM_MIN;
    inBtn.disabled = zoom >= PANE_ZOOM_MAX;
  }

  function applyMainZoom() {
    applyZoomTransform(mainZoomStage, mainZoom);
    syncZoomControls(mainZoom, mainZoomOut, mainZoomIn, mainZoomReset);
  }

  function applyPreviewZoom() {
    if (!previewContent) {
      syncZoomControls(previewZoom, previewZoomOut, previewZoomIn, previewZoomReset);
      return;
    }
    // Médias en width:100% : élargir le conteneur (scale+width compensée s'annule).
    previewContent.style.transform = "";
    previewContent.style.transformOrigin = "";
    if (previewZoom === 1) {
      previewContent.style.width = "";
    } else {
      previewContent.style.width = `${previewZoom * 100}%`;
    }
    syncZoomControls(previewZoom, previewZoomOut, previewZoomIn, previewZoomReset);
  }

  function setMainZoom(value) {
    mainZoom = clampPaneZoom(value);
    applyMainZoom();
  }

  function setPreviewZoom(value) {
    previewZoom = clampPaneZoom(value);
    applyPreviewZoom();
  }

  function setActiveZoomPane(pane) {
    activeZoomPane = pane === "preview" ? "preview" : "main";
  }

  function adjustActiveZoom(delta) {
    if (activeZoomPane === "preview") {
      setPreviewZoom(previewZoom + delta);
    } else {
      setMainZoom(mainZoom + delta);
    }
  }

  async function renderPdfPages(filename, file, token) {
    const pdfjs = await loadPdfJs();
    if (token !== previewRenderToken) {
      return;
    }
    const data = await file.arrayBuffer();
    if (token !== previewRenderToken) {
      return;
    }
    const pdf = await pdfjs.getDocument({ data }).promise;
    if (token !== previewRenderToken) {
      return;
    }

    const container = document.createElement("div");
    container.className = "preview-pdf";
    container.setAttribute("role", "img");
    container.setAttribute("aria-label", `Aperçu de ${filename}`);
    previewContent.replaceChildren(container);

    const containerWidth = Math.max(previewContent.clientWidth || 0, 320);

    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum += 1) {
      if (token !== previewRenderToken) {
        return;
      }
      const page = await pdf.getPage(pageNum);
      const unscaled = page.getViewport({ scale: 1 });
      const scale = Math.min(2, Math.max(0.75, containerWidth / unscaled.width));
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement("canvas");
      canvas.className = "preview-pdf-page";
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      container.appendChild(canvas);
      await page.render({
        canvasContext: canvas.getContext("2d"),
        viewport,
      }).promise;
    }
  }

  function renderPreviewMedia(filename, url) {
    previewContent.replaceChildren();
    const image = document.createElement("img");
    image.src = url;
    image.alt = `Aperçu de ${filename}`;
    previewContent.appendChild(image);
    previewPlaceholder.hidden = true;
    previewFilename.hidden = false;
    previewFilename.textContent = filename;
    previewedFilename = filename;
    applyPreviewZoom();
  }

  function clearFileUrls() {
    clearPreview();
    for (const url of fileUrls.values()) {
      URL.revokeObjectURL(url);
    }
    fileUrls.clear();
    depositedFiles.clear();
  }

  function appendFiles(files) {
    for (const file of files) {
      depositedFiles.set(file.name, file);
      // Les PDF sont rendus via pdf.js (ArrayBuffer) : pas d'object URL nécessaire.
      if (!isHeicFile(file) && !isPdfFilename(file.name)) {
        fileUrls.set(file.name, URL.createObjectURL(file));
      }
    }
  }

  function forgetFiles(names) {
    const toForget = new Set(names);
    for (const name of toForget) {
      depositedFiles.delete(name);
      const url = fileUrls.get(name);
      if (url) {
        URL.revokeObjectURL(url);
        fileUrls.delete(name);
      }
    }
    if (previewedFilename && toForget.has(previewedFilename)) {
      clearPreview();
    }
  }

  function keepFilesForLignes(lignes) {
    const kept = new Set((lignes || []).map((ligne) => ligne.fichier));
    for (const name of [...depositedFiles.keys()]) {
      if (kept.has(name)) {
        continue;
      }
      depositedFiles.delete(name);
      const url = fileUrls.get(name);
      if (url) {
        URL.revokeObjectURL(url);
        fileUrls.delete(name);
      }
    }
  }

  async function resolvePreviewUrl(filename) {
    let url = fileUrls.get(filename);
    if (url) {
      return url;
    }
    const file = depositedFiles.get(filename);
    if (!file || !isHeicFile(file)) {
      return null;
    }
    try {
      url = await createHeicPreviewUrl(file);
      fileUrls.set(filename, url);
      return url;
    } catch {
      return null;
    }
  }

  function markPreviewMeta(filename) {
    previewPlaceholder.hidden = true;
    previewFilename.hidden = false;
    previewFilename.textContent = filename;
    previewedFilename = filename;
    applyPreviewZoom();
  }

  async function showPreview(filename) {
    previewRenderToken += 1;
    const token = previewRenderToken;
    previewContent.replaceChildren();

    if (isPdfFilename(filename)) {
      const file = depositedFiles.get(filename);
      if (!file) {
        clearPreview();
        return false;
      }
      markPreviewMeta(filename);
      try {
        await renderPdfPages(filename, file, token);
        return token === previewRenderToken;
      } catch {
        if (token === previewRenderToken) {
          clearPreview();
        }
        return false;
      }
    }

    const url = await resolvePreviewUrl(filename);
    if (token !== previewRenderToken) {
      return false;
    }
    if (!url) {
      clearPreview();
      return false;
    }
    renderPreviewMedia(filename, url);
    return true;
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

  function changerTypeDocument(index, typeDocument) {
    const ligne = lotLignes[index];
    if (!ligne || (typeDocument !== TYPE_FACTURE && typeDocument !== TYPE_AVOIR)) {
      return;
    }
    lotLignes[index] = { ...ligne, type_document: typeDocument };
    renderLignes(lotLignes);
  }

  function champsRemplis(ligne) {
    return EDITABLE_FIELDS.every((key) => {
      const value = ligne[key];
      return value != null && String(value).trim() !== "";
    });
  }

  function validerLigne(index) {
    const ligne = lotLignes[index];
    if (!ligne || ligne.statut !== "A_VERIFIER" || !champsRemplis(ligne)) {
      return;
    }
    lotLignes[index] = { ...ligne, statut: "OK", raisons_diagnostic: [] };
    renderLignes(lotLignes);
  }

  function appendLigneRow(tableBody, ligne, index) {
    const tr = document.createElement("tr");
    if (!champsRemplis(ligne)) {
      tr.classList.add("ligne-incomplete");
    }
    if (ligne.statut === "A_VERIFIER") {
      tr.classList.add("ligne-a-verifier");
    }
    if (previewedFilename && ligne.fichier === previewedFilename) {
      tr.classList.add("ligne-apercu");
    }
    let validerBtn = null;
    for (const key of ["fichier", "emetteur", "date", "montant_ht", "statut"]) {
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
          if (key === "emetteur") {
            return;
          }
          if (key === "montant_ht") {
            refreshGroupingUi();
          }
          if (validerBtn) {
            validerBtn.disabled = !champsRemplis(lotLignes[index]);
          }
        });
        if (key === "emetteur") {
          input.addEventListener("blur", () => {
            renderLignes(lotLignes);
          });
        }
        td.appendChild(input);
      } else {
        td.textContent = displayValue(ligne[key]);
      }
      tr.appendChild(td);
    }

    const tdType = document.createElement("td");
    const typeSelect = document.createElement("select");
    typeSelect.setAttribute("aria-label", "Type de document");
    for (const [value, label] of [
      [TYPE_FACTURE, "Facture"],
      [TYPE_AVOIR, "Avoir"],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      typeSelect.appendChild(option);
    }
    typeSelect.value = ligne.type_document || TYPE_FACTURE;
    typeSelect.addEventListener("change", () => {
      changerTypeDocument(index, typeSelect.value);
    });
    tdType.appendChild(typeSelect);
    tr.appendChild(tdType);

    const tdAction = document.createElement("td");
    if (ligne.statut === "A_VERIFIER") {
      validerBtn = document.createElement("button");
      validerBtn.type = "button";
      validerBtn.className = "valider-ligne";
      validerBtn.textContent = "Valider";
      validerBtn.disabled = !champsRemplis(ligne);
      validerBtn.addEventListener("click", () => {
        validerLigne(index);
      });
      tdAction.appendChild(validerBtn);
    }
    tr.appendChild(tdAction);

    const tdFichier = document.createElement("td");
    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "ouvrir-fichier";
    openBtn.textContent = "Ouvrir le fichier";
    const hasFile = depositedFiles.has(ligne.fichier);
    if (hasFile) {
      openBtn.addEventListener("click", async () => {
        const opened = await showPreview(ligne.fichier);
        if (!opened) {
          showError("Impossible d'afficher l'aperçu de ce fichier.");
          return;
        }
        showError("");
        renderLignes(lotLignes);
      });
    } else {
      openBtn.disabled = true;
      openBtn.title = "Fichier indisponible pour ce Lot";
    }
    tdFichier.appendChild(openBtn);
    tr.appendChild(tdFichier);
    tableBody.appendChild(tr);
  }

  function createResultsTable() {
    const table = document.createElement("table");
    table.className = "results-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Fichier</th>
          <th>Émetteur</th>
          <th>Date</th>
          <th>Montant HT</th>
          <th>Statut</th>
          <th>Type</th>
          <th>Action</th>
          <th>Aperçu</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    return table;
  }

  function appendTypeBlock(groupBody, title, entries) {
    if (entries.length === 0) {
      return;
    }
    const block = document.createElement("section");
    block.className = "issuer-type-block";

    const heading = document.createElement("h4");
    heading.className = "issuer-type-heading";
    heading.textContent = `${title} (${entries.length})`;

    const table = createResultsTable();
    const tbody = table.querySelector("tbody");
    for (const { ligne, index } of entries) {
      appendLigneRow(tbody, ligne, index);
    }

    block.append(heading, table);
    groupBody.appendChild(block);
  }

  function renderIssuerGroups() {
    issuerGroups.replaceChildren();
    const totals = montantParEmetteurMap();
    const groupedEntries = LotGrouping.grouperLignesParEmetteur(
      lotLignes.map((ligne, index) => ({ ligne, index })),
    );

    for (const [emetteur, entries] of groupedEntries) {
      const group = document.createElement("section");
      group.className = "issuer-group";
      if (emetteur === LotGrouping.EMETTEUR_MANQUANT) {
        group.classList.add("issuer-group-missing");
      }

      const header = document.createElement("div");
      header.className = "issuer-group-header";

      const title = document.createElement("h3");
      title.className = "issuer-group-title";
      title.textContent = emetteur;

      const total = document.createElement("p");
      total.className = "issuer-group-total";
      total.textContent = `Total net HT : ${totals.get(emetteur) || "0,00"} €`;

      header.append(title, total);

      const body = document.createElement("div");
      body.className = "issuer-group-body";
      const factures = entries.filter(({ ligne }) => ligne.type_document !== TYPE_AVOIR);
      const avoirs = entries.filter(({ ligne }) => ligne.type_document === TYPE_AVOIR);
      appendTypeBlock(body, "Factures", factures);
      appendTypeBlock(body, "Avoirs", avoirs);

      group.append(header, body);
      issuerGroups.appendChild(group);
    }
  }

  function renderLignes(lignes) {
    lotLignes = lignes.map((ligne) => ({
      ...ligne,
      type_document: ligne.type_document || TYPE_FACTURE,
    }));
    const factureCount = lotLignes.filter(
      (ligne) => ligne.type_document !== TYPE_AVOIR,
    ).length;
    const avoirCount = lotLignes.length - factureCount;

    renderIssuerGroups();
    facturesCount.textContent = String(factureCount);
    avoirsCount.textContent = String(avoirCount);
    refreshGroupingUi();
  }

  function resetLot() {
    lotGeneration += 1;
    clearFileUrls();
    journalDisponible = false;
    renderLignes([]);
    showError("");
    setProcessing(false);
    fileInput.value = "";
    syncExportJournalButton();
  }

  async function exportLotCsv(mode) {
    if (lotLignes.length === 0) {
      return;
    }
    const exportMode = mode === "agrege" ? "agrege" : "detail";
    const avertissement = LotGrouping.messageAvertissementExport(lotLignes);
    if (avertissement) {
      if (!window.confirm(avertissement)) {
        exportBlockMessage.hidden = true;
        exportBlockMessage.textContent = "";
        return;
      }
      exportBlockMessage.textContent =
        "Export confirmé alors que des factures sont encore à vérifier.";
      exportBlockMessage.hidden = false;
    } else {
      exportBlockMessage.hidden = true;
      exportBlockMessage.textContent = "";
    }
    showError("");
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lignes: lotLignes, mode: exportMode }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        showError(payload.error || "Échec de l'export CSV.");
        return;
      }
      const text = await response.text();
      const suggestedName =
        exportMode === "agrege" ? "lot-groupe.csv" : "lot-detail.csv";
      const saved = await saveTextFile(text, {
        suggestedName,
        description: "CSV",
        accept: { "text/csv": [".csv"] },
        mimeType: "text/csv;charset=utf-8",
        desktopFileTypes: ["CSV (*.csv)", "Tous les fichiers (*.*)"],
      });
      if (saved === "cancelled") {
        return;
      }
      if (saved === false) {
        showError("Impossible d'enregistrer le CSV.");
      }
    } catch (err) {
      showError("Impossible de contacter le serveur.");
    }
  }

  async function exportJournal() {
    if (!journalDisponible) {
      return;
    }
    showError("");
    try {
      const response = await fetch("/api/journal");
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        showError(payload.error || "Échec de l'export du journal.");
        return;
      }
      const text = await response.text();
      const saved = await saveJournalText(text);
      if (saved === "cancelled") {
        return;
      }
      if (saved === false) {
        showError("Impossible d'enregistrer le journal.");
      }
    } catch (err) {
      showError("Impossible d'exporter le journal (serveur injoignable).");
    }
  }

  /**
   * Propose un emplacement d'enregistrement (desktop / File System Access / fallback).
   * @returns {Promise<"ok"|"cancelled"|false>}
   */
  async function saveTextFile(text, options) {
    const suggestedName = (options && options.suggestedName) || "export.txt";
    const description = (options && options.description) || "Fichier texte";
    const accept = (options && options.accept) || { "text/plain": [".txt", ".log"] };
    const mimeType = (options && options.mimeType) || "text/plain;charset=utf-8";
    const desktopFileTypes =
      (options && options.desktopFileTypes) || [
        "Fichiers texte (*.txt;*.log)",
        "Tous les fichiers (*.*)",
      ];

    const api = window.pywebview && window.pywebview.api;
    if (api && typeof api.save_text_file === "function") {
      const result = await api.save_text_file(
        suggestedName,
        text,
        desktopFileTypes
      );
      if (result && result.cancelled) {
        return "cancelled";
      }
      if (result && result.saved) {
        return "ok";
      }
      return false;
    }
    if (typeof window.showSaveFilePicker === "function") {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName,
          types: [
            {
              description,
              accept,
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(text);
        await writable.close();
        return "ok";
      } catch (err) {
        if (err && (err.name === "AbortError" || err.name === "NotAllowedError")) {
          return "cancelled";
        }
        return false;
      }
    }
    // Fallback navigateur : dialogue de téléchargement du navigateur
    const blob = new Blob([text], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = suggestedName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return "ok";
  }

  /**
   * Enregistre le journal sans l'afficher dans l'UI.
   * @returns {Promise<"ok"|"cancelled"|false>}
   */
  async function saveJournalText(text) {
    return saveTextFile(text, {
      suggestedName: "journal.txt",
      description: "Journal",
      accept: { "text/plain": [".txt", ".log"] },
      mimeType: "text/plain;charset=utf-8",
      desktopFileTypes: [
        "Fichiers texte (*.txt;*.log)",
        "Tous les fichiers (*.*)",
      ],
    });
  }

  async function uploadLot(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) {
      return;
    }

    const unsupported = [];
    const candidates = [];
    for (const file of files) {
      if (isSupportedDocumentName(file.name)) {
        candidates.push(file);
      } else {
        unsupported.push(file.name);
      }
    }
    const unsupportedWarning =
      unsupported.length === 0
        ? ""
        : unsupported
            .map(
              (name) =>
                `Le fichier «${name}» n'est pas un format exploitable. ` +
                `Formats acceptés : ${SUPPORTED_FORMATS_LABEL}.`,
            )
            .join(" ");

    const existingNames = new Set([
      ...lotLignes.map((ligne) => ligne.fichier),
      ...depositedFiles.keys(),
    ]);
    const accepted = [];
    const duplicates = [];
    const seenInBatch = new Set();
    for (const file of candidates) {
      if (existingNames.has(file.name) || seenInBatch.has(file.name)) {
        duplicates.push(file.name);
      } else {
        seenInBatch.add(file.name);
        accepted.push(file);
      }
    }

    const duplicateWarning =
      duplicates.length === 0
        ? ""
        : [...new Set(duplicates)]
            .map((name) => `Le fichier «${name}» est déjà présent dans le Lot.`)
            .join(" ");

    if (accepted.length === 0) {
      showError(
        [unsupportedWarning, duplicateWarning].filter(Boolean).join(" ") ||
          "Aucun fichier reçu.",
      );
      fileInput.value = "";
      return;
    }

    showError("");
    setProcessing(true);
    const generation = lotGeneration;
    appendFiles(accepted);
    const appendedNames = accepted.map((file) => file.name);

    const formData = new FormData();
    for (const file of accepted) {
      formData.append("files", file, file.name);
    }

    try {
      const response = await fetch("/api/lot", {
        method: "POST",
        body: formData,
      });
      if (generation !== lotGeneration) {
        return;
      }
      const payload = await response.json();
      if (!response.ok) {
        forgetFiles(appendedNames);
        if (response.status === 500) {
          journalDisponible = Boolean(payload.journal_disponible) || true;
          showError(
            payload.error ||
              "Échec du traitement du lot. Exportez le journal pour le diagnostic.",
          );
        } else {
          showError(payload.error || "Échec du traitement du lot.");
        }
        syncExportJournalButton();
        return;
      }
      const nouvelles = payload.lignes || [];
      journalDisponible = Boolean(payload.journal_disponible);
      const merged = [...lotLignes, ...nouvelles];
      keepFilesForLignes(merged);
      renderLignes(merged);
      const warnings = Array.isArray(payload.warnings) ? [...payload.warnings] : [];
      if (unsupportedWarning) {
        warnings.push(unsupportedWarning);
      }
      if (duplicateWarning) {
        warnings.push(duplicateWarning);
      }
      if (warnings.length > 0) {
        showError(warnings.join(" "));
      }
    } catch (err) {
      if (generation !== lotGeneration) {
        return;
      }
      forgetFiles(appendedNames);
      showError("Impossible de contacter le serveur.");
    } finally {
      if (generation === lotGeneration) {
        setProcessing(false);
      }
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

  if (exportDetailButton) {
    exportDetailButton.addEventListener("click", () => {
      exportLotCsv("detail");
    });
  }
  if (exportAgregeButton) {
    exportAgregeButton.addEventListener("click", () => {
      exportLotCsv("agrege");
    });
  }

  if (exportJournalButton) {
    exportJournalButton.addEventListener("click", () => {
      exportJournal();
    });
  }

  if (resetLotButton) {
    resetLotButton.addEventListener("click", () => {
      resetLot();
    });
  }

  if (mainZoomOut && mainZoomIn && mainZoomReset) {
    mainZoomOut.addEventListener("click", () => {
      setActiveZoomPane("main");
      setMainZoom(mainZoom - PANE_ZOOM_STEP);
    });
    mainZoomIn.addEventListener("click", () => {
      setActiveZoomPane("main");
      setMainZoom(mainZoom + PANE_ZOOM_STEP);
    });
    mainZoomReset.addEventListener("click", () => {
      setActiveZoomPane("main");
      setMainZoom(1);
    });
  }

  if (previewZoomOut && previewZoomIn && previewZoomReset) {
    previewZoomOut.addEventListener("click", () => {
      setActiveZoomPane("preview");
      setPreviewZoom(previewZoom - PANE_ZOOM_STEP);
    });
    previewZoomIn.addEventListener("click", () => {
      setActiveZoomPane("preview");
      setPreviewZoom(previewZoom + PANE_ZOOM_STEP);
    });
    previewZoomReset.addEventListener("click", () => {
      setActiveZoomPane("preview");
      setPreviewZoom(1);
    });
  }

  if (mainPane) {
    mainPane.addEventListener("pointerenter", () => setActiveZoomPane("main"));
  }
  if (previewPane) {
    previewPane.addEventListener("pointerenter", () => setActiveZoomPane("preview"));
  }

  window.addEventListener("keydown", (event) => {
    if (!(event.metaKey || event.ctrlKey) || event.altKey) {
      return;
    }
    if (event.key === "+" || event.key === "=") {
      adjustActiveZoom(PANE_ZOOM_STEP);
      event.preventDefault();
    } else if (event.key === "-") {
      adjustActiveZoom(-PANE_ZOOM_STEP);
      event.preventDefault();
    } else if (event.key === "0") {
      if (activeZoomPane === "preview") {
        setPreviewZoom(1);
      } else {
        setMainZoom(1);
      }
      event.preventDefault();
    }
  });

  window.addEventListener(
    "wheel",
    (event) => {
      if (!(event.metaKey || event.ctrlKey)) {
        return;
      }
      if (previewPane && previewPane.contains(event.target)) {
        setActiveZoomPane("preview");
      } else if (mainPane && mainPane.contains(event.target)) {
        setActiveZoomPane("main");
      }
      event.preventDefault();
      const direction = event.deltaY < 0 ? PANE_ZOOM_STEP : -PANE_ZOOM_STEP;
      adjustActiveZoom(direction);
    },
    { passive: false },
  );

  applyMainZoom();
  applyPreviewZoom();

  function splitLayoutActive() {
    return window.matchMedia("(min-width: 961px)").matches;
  }

  function clampPreviewWidth(widthPx, shellWidth) {
    const minPreview = 240;
    const minMain = 320;
    const maxPreview = Math.max(minPreview, shellWidth - minMain);
    return Math.min(Math.max(widthPx, minPreview), maxPreview);
  }

  function setPreviewWidth(widthPx) {
    if (!appShell) {
      return;
    }
    const shellWidth = appShell.getBoundingClientRect().width;
    const clamped = clampPreviewWidth(widthPx, shellWidth);
    appShell.style.setProperty("--preview-width", `${Math.round(clamped)}px`);
  }

  function initSplitResize() {
    if (!appShell || !splitHandle) {
      return;
    }

    let dragging = false;

    splitHandle.addEventListener("pointerdown", (event) => {
      if (!splitLayoutActive() || event.button !== 0) {
        return;
      }
      dragging = true;
      splitHandle.setPointerCapture(event.pointerId);
      document.body.classList.add("is-resizing-split");
      event.preventDefault();
    });

    splitHandle.addEventListener("pointermove", (event) => {
      if (!dragging) {
        return;
      }
      const rect = appShell.getBoundingClientRect();
      setPreviewWidth(rect.right - event.clientX);
    });

    function endDrag(event) {
      if (!dragging) {
        return;
      }
      dragging = false;
      document.body.classList.remove("is-resizing-split");
      if (splitHandle.hasPointerCapture(event.pointerId)) {
        splitHandle.releasePointerCapture(event.pointerId);
      }
    }

    splitHandle.addEventListener("pointerup", endDrag);
    splitHandle.addEventListener("pointercancel", endDrag);

    splitHandle.addEventListener("keydown", (event) => {
      if (!splitLayoutActive()) {
        return;
      }
      const step = event.shiftKey ? 40 : 16;
      const previewPane = document.getElementById("preview-pane");
      const current = previewPane.getBoundingClientRect().width;
      if (event.key === "ArrowLeft") {
        setPreviewWidth(current + step);
        event.preventDefault();
      } else if (event.key === "ArrowRight") {
        setPreviewWidth(current - step);
        event.preventDefault();
      }
    });
  }

  initSplitResize();
  syncExportButton();
})();
