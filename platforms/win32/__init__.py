"""Wilfrid — automation Windows (P2.5).

ctypes reste STRICTEMENT local aux fonctions (aucun import au niveau
module) : l'import de ce package n'échoue jamais hors Windows.
Les fonctions ne s'exécutent que sous garde `sys.platform == "win32"`
maintenue par les appelants, exactement comme dans `jarvis.py`.
"""
