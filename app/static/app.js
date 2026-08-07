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
  const exportButton = document.getElementById("export-csv");
  const exportJournalButton = document.getElementById("export-journal");
  const appShell = document.querySelector(".app-shell");
  const splitHandle = document.getElementById("split-handle");
  const mainPane = document.getElementById("main-pane");
  const previewPane = document.getElementById("preview-pane");
  const mainZoomStage = document.getElementById("main-zoom-stage");
  const previewZoomStage = document.getElementById("preview-zoom-stage");
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
  /** filename → object URL pour ouvrir le fichier (éphémère, côté navigateur uniquement). */
  const fileUrls = new Map();
  /** filename → File déposé (conservé pour conversion HEIC à l'ouverture). */
  const depositedFiles = new Map();
  /** Fichier actuellement affiché dans le panneau d'aperçu (null si vide). */
  let previewedFilename = null;
  /** Dernier panneau survolé / ciblé pour raccourcis clavier et molette. */
  let activeZoomPane = "main";
  let mainZoom = 1;
  let previewZoom = 1;

  let heic2anyLoadPromise = null;

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
    if (lotLignes.length === 0) {
      exportButton.disabled = true;
      exportBlockMessage.hidden = true;
      exportBlockMessage.textContent = "";
      return;
    }
    const raison = LotGrouping.raisonExportBloque(lotLignes);
    exportButton.disabled = raison != null;
    if (raison) {
      exportBlockMessage.textContent = raison;
      exportBlockMessage.hidden = false;
    } else {
      exportBlockMessage.hidden = true;
      exportBlockMessage.textContent = "";
    }
  }

  function refreshGroupingUi() {
    renderTotauxBanner();
    syncExportButton();
  }

  function clearPreview() {
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

  function applyStageZoom(stage, zoom) {
    if (!stage) {
      return;
    }
    stage.style.transformOrigin = "0 0";
    if (zoom === 1) {
      stage.style.transform = "";
      stage.style.width = "";
    } else {
      stage.style.transform = `scale(${zoom})`;
      stage.style.width = `${100 / zoom}%`;
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
    applyStageZoom(mainZoomStage, mainZoom);
    syncZoomControls(mainZoom, mainZoomOut, mainZoomIn, mainZoomReset);
  }

  function applyPreviewZoom() {
    applyStageZoom(previewZoomStage, previewZoom);
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

  function renderPreviewMedia(filename, url) {
    previewContent.replaceChildren();
    if (isPdfFilename(filename)) {
      // <embed> se comporte mieux que <iframe> avec transform:scale sous WKWebView.
      const embed = document.createElement("embed");
      embed.src = url;
      embed.type = "application/pdf";
      embed.title = `Aperçu de ${filename}`;
      previewContent.appendChild(embed);
    } else {
      const image = document.createElement("img");
      image.src = url;
      image.alt = `Aperçu de ${filename}`;
      previewContent.appendChild(image);
    }
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

  function rememberFiles(files) {
    clearFileUrls();
    for (const file of files) {
      depositedFiles.set(file.name, file);
      if (!isHeicFile(file)) {
        fileUrls.set(file.name, URL.createObjectURL(file));
      }
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

  async function showPreview(filename) {
    const url = await resolvePreviewUrl(filename);
    if (!url) {
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
    lotLignes[index] = { ...ligne, statut: "OK" };
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

  async function exportLotCsv() {
    const raison = LotGrouping.raisonExportBloque(lotLignes);
    if (lotLignes.length === 0 || raison) {
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
      link.download = "lot.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
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
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "journal.txt";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      showError("Impossible d'exporter le journal (serveur injoignable).");
    }
  }

  async function uploadLot(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) {
      return;
    }

    showError("");
    setProcessing(true);
    rememberFiles(files);

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
        clearFileUrls();
        journalDisponible = response.status === 500;
        syncExportJournalButton();
        showError(payload.error || "Échec du traitement du lot.");
        return;
      }
      const lignes = payload.lignes || [];
      journalDisponible = Boolean(payload.journal_disponible);
      keepFilesForLignes(lignes);
      renderLignes(lignes);
      const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      if (warnings.length > 0) {
        showError(warnings.join(" "));
      }
    } catch (err) {
      clearFileUrls();
      journalDisponible = false;
      syncExportJournalButton();
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

  if (exportJournalButton) {
    exportJournalButton.addEventListener("click", () => {
      exportJournal();
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
