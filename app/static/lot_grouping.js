(function (global) {
  const EMETTEUR_MANQUANT = "sans émetteur";

  function cleEmetteur(emetteur) {
    if (emetteur == null || String(emetteur).trim() === "") {
      return EMETTEUR_MANQUANT;
    }
    return String(emetteur).trim();
  }

  function parseMontantHt(montant) {
    if (montant == null || String(montant).trim() === "") {
      return 0;
    }
    const cleaned = String(montant).trim().replace(/\s/g, "").replace(/\./g, "").replace(",", ".");
    const value = Number(cleaned);
    return Number.isFinite(value) ? value : 0;
  }

  function formaterMontantHt(value) {
    return value.toFixed(2).replace(".", ",");
  }

  function compareEmetteurs(a, b) {
    if (a === EMETTEUR_MANQUANT && b !== EMETTEUR_MANQUANT) {
      return -1;
    }
    if (b === EMETTEUR_MANQUANT && a !== EMETTEUR_MANQUANT) {
      return 1;
    }
    return a.localeCompare(b, "fr");
  }

  function agregerParEmetteur(lignes) {
    const totals = new Map();
    for (const ligne of lignes) {
      const cle = cleEmetteur(ligne.emetteur);
      const amount = parseMontantHt(ligne.montant_ht);
      const prev = totals.get(cle) || { total: 0, count: 0 };
      totals.set(cle, { total: prev.total + amount, count: prev.count + 1 });
    }
    return Array.from(totals.entries())
      .sort(([a], [b]) => compareEmetteurs(a, b))
      .map(([emetteur, { total, count }]) => ({
        emetteur,
        montant_ht: formaterMontantHt(total),
        nb_documents: count,
        emetteur_manquant: emetteur === EMETTEUR_MANQUANT,
      }));
  }

  function messageAvertissementExport(lignes) {
    let aVerifierCount = 0;
    for (const ligne of lignes) {
      if (ligne.statut === "A_VERIFIER") {
        aVerifierCount += 1;
      }
    }
    if (aVerifierCount === 0) {
      return null;
    }
    const label = aVerifierCount === 1 ? "facture" : "factures";
    return (
      "Attention : " +
      aVerifierCount +
      " " +
      label +
      " encore à vérifier. L'export contient ces lignes avec le statut A_VERIFIER."
    );
  }

  function grouperLignesParEmetteur(entries) {
    const groups = new Map();
    for (const entry of entries) {
      const cle = cleEmetteur(entry.ligne.emetteur);
      if (!groups.has(cle)) {
        groups.set(cle, []);
      }
      groups.get(cle).push(entry);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => compareEmetteurs(a, b));
  }

  global.LotGrouping = {
    EMETTEUR_MANQUANT,
    cleEmetteur,
    parseMontantHt,
    formaterMontantHt,
    agregerParEmetteur,
    messageAvertissementExport,
    grouperLignesParEmetteur,
  };
})(window);
