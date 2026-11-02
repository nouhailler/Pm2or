// Faits affichés sur le site, à revérifier à chaque nouvelle release.
// tests/static.test.mjs contrôle que VERSION correspond à ../pyproject.toml.
export const VERSION = "0.1.8";
export const RELEASE_DATE = "1er novembre 2026";
export const DEB_SIZE = "109 Mo";

export const GALLERY = [
  ["plan-de-travail", "Plan de travail", "Structure des tâches, Gantt simple, dépendances et chemin critique.", "Écran Plan de travail : arborescence des tâches, Gantt simple, tableau des dépendances et calcul du chemin critique, avec les tâches critiques surlignées."],
  ["registres", "Registres", "Risques, problèmes, décisions et modifications, avec recherche et filtre par statut.", "Écran Registres PM² : onglets Risques, Problèmes, Décisions et Modifications, et tableau de trois risques avec statut, responsable et score."],
  ["conformite", "Conformité PM²", "Score, état des revues de passage et actions correctives.", "Écran Centre de conformité PM² : score global, progression par domaine, contrôles de la revue RfP et liste des écarts avec un bouton Corriger."],
  ["objets-orphelins", "Traçabilité", "Détection des éléments sans lien, avec raccourci de correction.", "Écran Traçabilité, onglet Objets orphelins : contrôles des exigences, risques, livrables et tâches sans lien."],
  ["documents", "Documents", "Les 21 artefacts PM², leur phase, leur statut et leurs versions.", "Écran Documents et artefacts : tableau des artefacts avec code, titre, phase, caractère requis et statut, et choix du format d'export."],
  ["audit-trail", "Journal d'audit", "Chronologie des actions, avec comparaison avant et après.", "Écran Audit Trail : chronologie des événements à gauche, détail de l'événement sélectionné à droite avec les valeurs avant et après."],
  ["glossaire", "Glossaire et encyclopédie", "Notions, méthodes, histoire et guide de choix, consultables hors ligne.", "Écran Glossaire et encyclopédie : liste alphabétique de notions avec recherche, et définition du terme Acceptation."],
  ["lancement", "Assistant de phase", "Complétude, validations et artefacts de la phase de Lancement.", "Écran Assistant de Lancement : barre de complétude de la phase, onglets des artefacts de la phase et synthèse de l'avancement."],
];
