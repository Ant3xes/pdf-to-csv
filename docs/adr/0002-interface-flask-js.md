# Interface en Flask + JS plutôt que Streamlit

Le contexte : l'application a besoin d'une interface locale avec drag & drop multi-fichiers et un tableau de résultats éditable inline pour la correction manuelle. Décision : construire l'interface en Flask + JavaScript plutôt qu'en Streamlit. Raison : plus de contrôle sur l'UX du drag & drop et de l'édition inline, jugé prioritaire malgré un développement plus long que ne l'aurait permis Streamlit (qui offre `st.data_editor` prêt à l'emploi).

## Consequences

- Pas de composant d'édition de tableau prêt à l'emploi : l'édition inline des champs "À vérifier" doit être implémentée côté front.
- Le drag & drop multi-fichiers doit être implémenté à la main (JS), plutôt que délégué à un widget Streamlit.
- Développement initial plus long, en échange d'une UX plus fine sur les interactions clés (édition, drag & drop).
