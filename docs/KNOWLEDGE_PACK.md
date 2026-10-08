# Wilfrid — Knowledge Pack v1 (offline)

## Emplacement

`knowledge_pack/` : `manifest.json` + 8 documents `.txt` (40 Ko).
Identité : `wilfrid-core-knowledge`, version `1.0.0`, langue `fr`.

## Structure

Chaque document : `id`, `titre`, `categorie`, `version`, `langue`,
`source`, `fichier`, `sha256`. Le manifeste est la source of truth ;
les empreintes sont vérifiées au chargement (corruption détectée,
`empreinte-invalide:<id>`).

## Ajouter un document

1. Écrire le `.txt` (affirmations vérifiées uniquement).
2. Ajouter l'entrée au manifeste avec son `sha256`
   (`sha256sum <fichier>`).
3. Relancer : l'ingestion ajoute sans doublon.

## Ingestion / reconstruction

`core/knowledge/pack.py::ingest_pack` (parse → upsert → chunks
déterministes → checkpoints). Idempotente : 2e passage = 0 ajout.
Contenu modifié (sha différente) → chunks du document remplacés
(borné au document). Supprimer `knowledge.sqlite` + redémarrer
reconstruit tout (~0,03 s pour v1).

## Vérifier

`load_pack()` : manifeste, fichiers, empreintes. En runtime :
composant `knowledge` = `pack 8 docs/8 chunks`, sinon raison explicite
(`pack-absent`, `empreinte-invalide:…`) et recherche indisponible
déclarée — jamais de faux READY.

## Absent / corrompu

Pack absent ou corrompu → `knowledge=ko` avec raison, boucle texte
toujours disponible, recherche répondue indisponible. Restaurer les
fichiers + redémarrer suffit.

## Offline

Corpus, SQLite, FTS5, retrieval, Core : 100 % locaux (vérifié AST :
aucun import réseau sur le chemin). Aucun téléchargement au démarrage.

## Distinctions

- Memory (souvenirs/contexte, `memory.sqlite`) ≠ Knowledge (stable,
  versionné, cité avec source).
- Knowledge (local-only) ≠ Internet (gouverné, permissions désactivées
  par défaut ; `scope=internet` → refusé par le retrieval local).
