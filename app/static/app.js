(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const indicator = document.getElementById("processing-indicator");
  const errorMessage = document.getElementById("error-message");
  const tableBody = document.querySelector("#results-table tbody");

  function statutLabel(statut) {
    return statut === "A_VERIFIER" ? "À vérifier" : statut;
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = !message;
  }

  function setProcessing(active) {
    indicator.hidden = !active;
  }

  function renderLignes(lignes) {
    tableBody.replaceChildren();
    for (const ligne of lignes) {
      const tr = document.createElement("tr");
      for (const key of ["fichier", "emetteur", "date", "montant_ttc", "statut"]) {
        const td = document.createElement("td");
        let value = ligne[key];
        if (key === "statut") {
          value = statutLabel(value);
        }
        td.textContent = value == null || value === "" ? "—" : String(value);
        tr.appendChild(td);
      }
      tableBody.appendChild(tr);
    }
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
