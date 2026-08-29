# SlidePunch — notes de projet

## Direction

**À terme, le mode serveur n'a pas vocation à être conservé.** La cible est
l'application 100 % navigateur (celle déployée sur GitHub Pages). Quand une
fonctionnalité doit être écrite deux fois — une version `isServerMode` et une
version navigateur — c'est la version navigateur qui compte ; le mode serveur
est du sursis.

Conséquences pratiques :
- Ne pas ajouter de fonctionnalité qui n'existerait qu'en mode serveur.
- En cas d'arbitrage, corriger d'abord le chemin navigateur.
- Un jour, `slidepunch.py` se réduira à servir des fichiers statiques (voire
  disparaîtra), et `ffmpeg` / `pdftoppm` cesseront d'être des prérequis.

## Les deux modes, aujourd'hui

`detectBackend()` teste `GET /api/projects` : si ça répond, mode serveur ;
sinon mode navigateur.

| | Mode serveur | Mode navigateur |
|---|---|---|
| Lancement | `python3 slidepunch.py` → :8080 | `python3 -m http.server 8081 --directory web` |
| Stockage | dossier `projects/` | IndexedDB (`SlidePunchDB`) |
| Diapos PDF | `pdftoppm` | PDF.js |
| Export vidéo | `ffmpeg` | canvas + `MediaRecorder` |

## Modèle de la timeline caméra

Chaque diapo porte une `videoTimeline` : une suite de clips couvrant
**exactement** la durée de l'audio.

- `takeId` renseigné → prise filmée ; `takeId: null` → **gap**, aucune caméra.
- Toute édition qui change la durée de l'audio doit faire la même modification
  ici (punch-in, couper, coller). Sans ça, les clips suivants glissent et la
  caméra apparaît là où rien n'a été filmé — la source de la majorité des bugs
  caméra rencontrés.
- Une timeline qui existe fait autorité, **vide comprise** : vide = caméra
  retirée. Ne pas retomber sur un drapeau `hasVideo` dans ce cas.
- L'aperçu doit refléter l'export : pendant la lecture c'est la timeline qui
  décide de l'affichage, pas la présence d'une caméra live.

## Pièges rencontrés

- `MediaRecorder` produit du WebM **sans durée** dans l'entête → `duration`
  vaut `Infinity` et les `currentTime` deviennent hasardeux. Le serveur remuxe
  (`ffmpeg -c copy`) à l'upload ; le mode navigateur n'a pas d'équivalent.
- `index.html` est servi avec `Cache-Control: no-store` : toute l'application
  tient dans ce fichier, et le cache navigateur a déjà fait croire à des bugs
  déjà corrigés.
- Les chemins de projet/fichier venant des paramètres d'URL sont validés
  (`safe_project_dir`, `safe_child`) — la version pré-caméra sur `main` n'a
  **pas** ces garde-fous.

## Branches

- `main` — version pré-caméra (`c8510a0`), c'est elle qui est déployée sur
  GitHub Pages.
- `wip/camera-overlay-fixes` — développement caméra en cours.
