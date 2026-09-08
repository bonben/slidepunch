# SlidePunch — notes de projet

## Direction

**L'application est 100 % navigateur.** Il n'y a plus de backend : le mode
serveur et `slidepunch.py` ont été supprimés. Tout — import PDF,
enregistrement, montage, export MP4 — tourne dans le navigateur, et rien ne
quitte la machine de l'utilisateur.

Conséquences pratiques :
- Ne pas réintroduire de chemin « serveur » ni d'appel `/api/...`.
- Le stockage, c'est IndexedDB (`SlidePunchDB`) : projets, diapos, audio,
  prises caméra. Pas de dossier `projects/`.
- `serve_static.py` n'est qu'un confort de développement (fichiers statiques
  + `Cache-Control: no-store`). N'importe quel serveur statique convient.

## Lancement

```bash
python3 serve_static.py       # http://localhost:8081
```

Déployé sur GitHub Pages depuis `main`, dossier `web/` (voir
`.github/workflows/deploy-pages.yml`).

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
- Les prises sont adressées par `takeSrcFor()` et résolues en blob URLs depuis
  IndexedDB par `preloadSlideTakes()`.

## Pièges rencontrés

- `MediaRecorder` produit du WebM **sans durée** dans l'entête → `duration`
  vaut `Infinity` et les `currentTime` deviennent hasardeux : la prise se fige
  sur une image. `makeVideoSeekable()` force le navigateur à scanner le fichier
  une fois (saut très au-delà de la fin) avant tout repositionnement — à
  appeler sur **chaque** élément `<video>` qui charge une prise.
- Un `<video>` en `display:none` voit son décodage suspendu au bout de
  quelques secondes. Les éléments vidéo hors écran utilisent
  `position:fixed; left:-10000px`, jamais `display:none`.
- **L'export ne doit pas dépendre de l'horloge murale.** Il a d'abord lu les
  prises en lecture accélérée : comme la boucle est freinée par la file de
  l'encodeur et pas la lecture, la prise prenait de l'avance, les images se
  figeaient puis la caméra disparaissait. Le parcours se fait maintenant par
  `seek` déterministe, vidéo en pause (~3 ms par image).
- Une prise servie en HTTP **sans support des requêtes `Range`** rapporte une
  plage cherchable vide et tout `seek` devient silencieusement inopérant. Les
  blob URLs n'ont pas ce problème.
- L'AAC n'est pas encodable dans plusieurs Chromium : `configure()` l'accepte
  puis l'export échoue en cours sur « Unsupported codec type ». `pickAudioCodec()`
  teste réellement le support et retombe sur Opus. Le conteneur reste MP4.
- `index.html` est servi en `Cache-Control: no-store` : toute l'application
  tient dans ce fichier, et le cache navigateur a déjà fait croire à des bugs
  déjà corrigés.

## Vérifier une modification

Chromium headless sait décoder la vidéo et exécuter WebCodecs. La méthode qui a
fait ses preuves : fabriquer une prise dont **la couleur encode l'instant
source** (rouge la 1ʳᵉ seconde, vert la 2ᵉ, bleu la 3ᵉ), exporter, puis
échantillonner les pixels de la zone d'incrustation avec `ffprobe`/`ffmpeg`.
Un gel se voit immédiatement : la couleur cesse de changer.
