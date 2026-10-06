"""Wilfrid — wake runtime (P3). Détection continue de « Wilfrid ».

Émet uniquement des événements WAKE_DETECTED via callback injecté.
Aucune action, aucun STT/TTS/dialogue/mémoire. Seuil et paramètres
lus dans models/wake.json, jamais codés en dur.
"""
