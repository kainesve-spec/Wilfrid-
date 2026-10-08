# Wilfrid — capacités Android (chantier 1, lecture seule d'abord)

## Principe

DISPONIBLE ≠ ACCORDÉ ≠ AUTORISÉ ≠ RÉUSSI. Registre fermé
(`core/android/capabilities.py`), DEFAULT DENY, accords explicites
tracés (`grant`/`revoke`), révocation immédiate.

## Capacités

6 lectures inoffensives accordées par défaut : batterie, audio, caméras
(liste), capteurs (liste), moteurs TTS (liste), système. Tout le reste
(personnel, intents, communications, suppressions) : refusé sauf accord
+ confirmation explicites. Voix (« appelle X ») ne vaut jamais
autorisation.

## Exécution gouvernée

`core/android/execution.py` : connu ? accordé ? confirmation (Approval
Gate, `ANDROID.<ID>`, consommation unique) ? → adaptateur borné
(liste blanche, sans shell, timeout) → vérification (champs/listes ;
intent = accepté, pas succès distant) → journal → rapport. Refus =
zéro effet.

## Ajouter une future capacité

1. Fiche `Capability` (mécanisme prouvé, risque, vérification).
2. Adaptateur listé si nouveau binaire (jamais de shell arbitraire).
3. Accord explicite requis si personnel/sensible.
4. Tests : mocks sauf lectures inoffensives ; jamais de SMS/appel/
   suppression réels en test ; jamais de données personnelles en dépôt.
