<img width="255" height="275" alt="jpeg" src="https://github.com/user-attachments/assets/7f0727f9-37a1-493d-85f6-8608486a240b" />

# Electronic Front Panel Designer

[English](README.md) · [Español](README.es.md) · [Deutsch](README.de.md) · **Français**

Application de bureau (Windows, Linux, macOS) pour concevoir les faces avant et arrière d'appareils
électroniques : alimentations, amplificateurs, instruments de mesure, modules Eurorack, boîtiers Hammond,
panneaux rack 19" et tout autre appareil en boîtier. Dessinez le panneau, placez de vrais composants depuis la
bibliothèque, ajoutez textes, échelles et graphismes, vérifiez les interférences et exportez des fichiers prêts
pour la fabrication (DXF, SVG, PDF, PNG, STL, G-code, HPGL).

L'interface est disponible en espagnol, anglais, allemand et français, et de nouvelles langues peuvent être
ajoutées à partir d'un fichier JSON.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/f4160162-5d39-476f-833f-6bc74736f2b6" />

Écrit en Python avec PySide6 (Qt 6).

## Téléchargement

Les versions prêtes à installer pour **Windows** (installateur `.exe`) et **macOS** (`.dmg`, Apple Silicon et
Intel) se trouvent sur la [page des versions](https://github.com/Aleluya-Git/Front-Panel-Designer/releases/latest).
Elles ne sont pas signées numériquement : sous Windows, si SmartScreen affiche un avertissement, cliquez sur
*Informations complémentaires → Exécuter quand même* ; sous macOS, au premier lancement, allez dans *Réglages
Système → Confidentialité et sécurité → Ouvrir quand même*.

## Lancer depuis le code source

| Système | Installer | Lancer | Autotest |
|---|---|---|---|
| Windows | `install.bat` | `run.bat` | `autoprueba.bat` |
| Linux / macOS | `./install.sh` | `./run.sh` | `./autoprueba.sh` |

Nécessite Python 3.10 ou plus récent. La seule dépendance est **PySide6**.

```bash
git clone https://github.com/Aleluya-Git/Front-Panel-Designer.git
cd Front-Panel-Designer
python -m venv .venv
# Windows : .venv\Scripts\activate   ·   Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

`autoprueba` exécute les tests unitaires du noyau et un parcours automatique de toute l'interface (dessin à la
souris simulée, placement de composants, export dans tous les formats, captures d'écran, vue 3D). Le rapport est
écrit dans `autoprueba_resultado.txt` et les fichiers générés dans `autoprueba_salida/`. Tests unitaires seuls :
`python -m unittest tests.test_core`.

Des projets d'exemple se trouvent dans `ejemplos/` : une alimentation de laboratoire, un VCO Eurorack 12HP et la
face arrière d'un amplificateur rack 2U.

## Fonctionnalités

- **Plan de travail CAO 2D** en millimètres (origine en bas à gauche, Y vers le haut) : zoom, déplacement,
  grille, accrochage à la grille et aux objets, règles, sélection par fenêtre ou capture façon AutoCAD, calques
  avec visibilité, verrouillage, couleur et procédé (découpe traversante, poche, gravure, sérigraphie, cotes,
  référence). Les formes s'affichent pendant qu'on les dessine.
- **Formes et usinages** : rectangle, rectangle arrondi, cercle, ellipse, polygones réguliers et libres, fentes
  rectangulaires et oblongues, trous en D, trous de fixation / fraisés / taraudés (tableau métrique M2–M8),
  poches avec profondeur, import de contours DXF et SVG.
- **Bibliothèque de composants** de plus de 60 pièces (chacune avec usinage, silhouette visible et corps
  arrière) : potentiomètres rotatifs et à glissière, faders, encodeurs, interrupteurs, boutons-poussoirs, LED,
  afficheurs LCD/OLED/TFT, galvanomètres, fiches banane, BNC, RCA, XLR, Speakon, jacks 3,5/6,35 mm, DC,
  USB-A/B/C, RJ45, embases IEC, porte-fusibles, D-Sub, MIDI, borniers, ventilateurs et plus de 80 grilles de
  ventilateur. Miniatures et infobulles avec image ; composants personnalisés enregistrés dans des bibliothèques
  nouvelles ou existantes, exportables et partageables.
- **Texte et graphismes** : texte multiligne avec les polices du système, taille, graisse, italique, souligné,
  barré, couleur, alignement, espacement et rotation ; libellés automatiques des composants ; logos SVG/DXF et
  images PNG/JPG.
- **Générateur d'échelles** pour potentiomètres rotatifs et à glissière : angles de début et de fin, rayon ou
  longueur, repères (traits, points, n'importe quel caractère ou aucun), sous-repères, numérotation (début, fin,
  pas, tous les N repères, décimales, préfixe/suffixe) ou textes personnalisés, taille, écart, position et
  rotation du texte, couleurs des repères et sous-repères, mode trait simple pour la gravure CNC, aperçu en
  direct et 11 modèles.
- **Goujons et entretoises filetés à sertir** (type PEM, M2–M6), à l'avant ou à l'arrière, avec trous borgnes et
  coupe cotée.
- **Panneau** : modèles (rack 19" 1U–4U, Eurorack 3U, Hammond 1590B/BB/XX, boîtiers d'instruments), matériau,
  épaisseur, rayon des angles, couleurs du panneau et de la sérigraphie, finition.
- **Cotes et vérification** : cotes automatiques à côté de chaque élément, cotes utilisateur associatives, outil
  de mesure et vérificateur de règles pour les pièces hors du panneau, la distance au bord, le pont minimal entre
  trous, les chevauchements, les collisions des corps arrière, les poches traversantes, ainsi que les textes,
  échelles et libellés qui empiètent sur un trou, chevauchent le bord d'une poche, se trouvent sous un bouton ou
  se superposent.
- **Conception paramétrique** : chaque valeur accepte des expressions (`=W/2`, `=marge + 2*pas`) avec des
  variables globales et les grandeurs intégrées W, H, T, HP (5,08) et U (44,45) ; répartition automatique liée,
  alignement, distribution, réseaux de copies, symétrie et rotation.
- **Export** : DXF R12 par calques, SVG (fabrication ou réaliste, calques Inkscape), PDF vectoriel (réaliste ou
  gabarit de perçage 1:1), PNG à résolution choisie avec cotes utilisateur et/ou automatiques en option, STL pour
  l'impression 3D, G-code (gravure, vidage de poches, perçage, arcs, compensation du rayon d'outil, passes en Z,
  contour) et HPGL.
- **Aperçu 3D** rendu par logiciel (sans OpenGL) avec matériaux et éclairage.
- **Projets** : fichiers `.efpd` (ZIP contenant du JSON lisible), annuler/rétablir illimité avec historique
  navigable, journal des modifications, sauvegarde automatique avec récupération après un plantage, fichiers
  récents, thèmes clair et sombre, barres d'outils et panneaux ancrables configurables.

Les dimensions de la bibliothèque sont indicatives : vérifiez toujours la fiche technique du fabricant avant
d'usiner.

## Structure du projet

```
efpd/core   géométrie, entités, document, expressions, bibliothèque, vérifications, échelles, goujons (sans Qt)
efpd/io     import et export DXF/SVG, maillage STL, G-code/HPGL, fichiers de projet
efpd/gui    interface PySide6 : fenêtre principale, plan de travail, dialogues, vue 3D, thèmes, icônes
efpd/lang   traductions (en, de, fr)
tests       tests unitaires et simulation de dessin sans Qt
tools       autotest, générateurs d'exemples et de traductions
packaging   spécification PyInstaller, installateur Windows (Inno Setup) et scripts d'image disque macOS
```

Les notes d'architecture se trouvent dans [ARQUITECTURA.md](ARQUITECTURA.md) (en espagnol).

## Licence

Copyright © 2026 Aleluya-Git.

Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier selon les termes de la Licence
publique générale GNU version 3 telle que publiée par la Free Software Foundation (voir [LICENSE](LICENSE)). Il
est distribué dans l'espoir qu'il sera utile, mais **sans aucune garantie** ; sans même la garantie implicite de
qualité marchande ou d'adéquation à un usage particulier.
