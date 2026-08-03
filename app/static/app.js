(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const indicator = document.getElementById("processing-indicator");
  const errorMessage = document.getElementById("error-message");
  const tableBody = document.querySelector("#results-table tbody");

  const EDITABLE_FIELDS = ["emetteur", "date", "montant_ttc"];
  /** État éphémère du Lot en cours (Correction manuelle locale, hors Template). */
  let lotLignes = [];

  function statutLabel(statut) {
    return statut === "A_VERIFIER" ? "À vérifier" : statut;
  }

  function displayValue(value) {
    return value == null || value === "" ? "—" : String(value);
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = !message;
  }

  function setProcessing(active) {
    indicator.hidden = !active;
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
          td.textContent = displayValue(ligne[key]);
          td.contentEditable = "true";
          td.addEventListener("focus", () => {
            if (lotLignes[index][key] == null || lotLignes[index][key] === "") {
              td.textContent = "";
            }
          });
          td.addEventListener("blur", () => {
            corrigerLigneLocale(index, key, td.textContent || "");
            td.textContent = displayValue(lotLignes[index][key]);
          });
        } else {
          td.textContent = displayValue(ligne[key]);
        }
        tr.appendChild(td);
      }
      tableBody.appendChild(tr);
    });
  }

  async function uploadLot(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) {
      return;
    }

    showError("");
    setProcessing(true);

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
        showError(payload.error || "Échec du traitement du lot.");
        return;
      }
      renderLignes(payload.lignes || []);
    } catch (err) {
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
})();
