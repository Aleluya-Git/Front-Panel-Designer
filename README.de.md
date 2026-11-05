<img width="255" height="275" alt="jpeg" src="https://github.com/user-attachments/assets/7f0727f9-37a1-493d-85f6-8608486a240b" />

# Electronic Front Panel Designer

[English](README.md) · [Español](README.es.md) · **Deutsch** · [Français](README.fr.md)

Desktop-Anwendung (Windows, Linux, macOS) zum Entwerfen von Front- und Rückplatten für elektronische Geräte:
Netzteile, Verstärker, Messgeräte, Eurorack-Module, Hammond-Gehäuse, 19"-Rackplatten und jedes andere Gerät
im Gehäuse. Zeichnen Sie die Platte, setzen Sie echte Bauteile aus der Bibliothek ein, fügen Sie Texte, Skalen
und Grafiken hinzu, prüfen Sie auf Kollisionen und exportieren Sie fertigungsreife Dateien (DXF, SVG, PDF, PNG,
STL, G-Code, HPGL).

Die Oberfläche gibt es auf Spanisch, Englisch, Deutsch und Französisch; weitere Sprachen lassen sich aus einer
JSON-Datei hinzufügen.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/f4160162-5d39-476f-833f-6bc74736f2b6" />

Geschrieben in Python mit PySide6 (Qt 6).

## Download

Installationsfertige Versionen für **Windows** (Installationsprogramm `.exe`) und **macOS** (`.dmg`, Apple
Silicon und Intel) finden Sie auf der [Releases-Seite](https://github.com/Aleluya-Git/Front-Panel-Designer/releases/latest).
Sie sind nicht digital signiert: Unter Windows klicken Sie bei einer SmartScreen-Warnung auf *Weitere
Informationen → Trotzdem ausführen*; unter macOS öffnen Sie beim ersten Start *Systemeinstellungen → Datenschutz
& Sicherheit → Dennoch öffnen*.

## Aus dem Quellcode starten

| System | Installieren | Starten | Selbsttest |
|---|---|---|---|
| Windows | `install.bat` | `run.bat` | `autoprueba.bat` |
| Linux / macOS | `./install.sh` | `./run.sh` | `./autoprueba.sh` |

Erfordert Python 3.10 oder neuer. Einzige Abhängigkeit ist **PySide6**.

```bash
git clone https://github.com/Aleluya-Git/Front-Panel-Designer.git
cd Front-Panel-Designer
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

`autoprueba` führt die Unit-Tests des Kerns und einen unbeaufsichtigten Durchlauf der gesamten Oberfläche aus
(Zeichnen mit simulierter Maus, Platzieren von Bauteilen, Export in alle Formate, Bildschirmfotos, 3D-Ansicht).
Der Bericht wird in `autoprueba_resultado.txt` geschrieben, die erzeugten Dateien landen in `autoprueba_salida/`.
Nur die Unit-Tests: `python -m unittest tests.test_core`.

Beispielprojekte liegen in `ejemplos/`: ein Labornetzteil, ein Eurorack-VCO mit 12 TE und die Rückplatte eines
2-HE-Rackverstärkers.

## Funktionen

- **2D-CAD-Zeichenfläche** in Millimetern (Ursprung unten links, Y nach oben): Zoom, Verschieben, Raster, Fang
  am Raster und an Objekten, Lineale, Fenster-/Kreuzungsauswahl wie in AutoCAD, Ebenen mit Sichtbarkeit,
  Sperre, Farbe und Bearbeitungsart (Durchbruch, Tasche, Gravur, Siebdruck, Bemaßung, Referenz). Formen werden
  bereits während des Zeichnens angezeigt.
- **Formen und Bearbeitungen**: Rechteck, abgerundetes Rechteck, Kreis, Ellipse, regelmäßiges und freies
  Polygon, Rechteck- und Langlöcher, D-Bohrungen, Befestigungs-, Senk- und Gewindebohrungen (metrische Tabelle
  M2–M8), Taschen mit Tiefe, Import von DXF- und SVG-Konturen.
- **Bauteilbibliothek** mit über 60 Teilen (jeweils mit Ausschnitt, sichtbarer Kontur und rückseitigem Körper):
  Dreh- und Schiebepotentiometer, Fader, Drehgeber, Schalter, Taster, LEDs, LCD/OLED/TFT-Anzeigen,
  Messinstrumente, Bananenbuchsen, BNC, Cinch, XLR, Speakon, Klinkenbuchsen 3,5/6,35 mm, DC, USB-A/B/C, RJ45,
  Kaltgerätebuchsen, Sicherungshalter, D-Sub, MIDI, Klemmen, Lüfter und über 80 Lüftergitter. Miniaturansicht
  und Tooltips mit Bild; eigene Bauteile lassen sich in neuen oder vorhandenen Bibliotheken speichern, die man
  exportieren und weitergeben kann.
- **Text und Grafik**: mehrzeiliger Text mit Systemschriften, Größe, Strichstärke, kursiv, unterstrichen,
  durchgestrichen, Farbe, Ausrichtung, Zeichenabstand und Drehung; automatische Bauteilbeschriftungen;
  SVG/DXF-Logos sowie PNG/JPG-Bilder.
- **Skalengenerator** für Dreh- und Schiebepotentiometer: Start- und Endwinkel, Radius oder Länge, Markierungen
  (Striche, Punkte, beliebiges Zeichen oder keine), Zwischenmarkierungen, Bezifferung (Anfang, Ende,
  Schrittweite, jede N-te Markierung, Dezimalstellen, Präfix/Suffix) oder eigene Texte, Textgröße, -abstand,
  -position und -drehung, eigene Farben für Haupt- und Zwischenmarkierungen, Einlinienmodus für CNC-Gravur,
  Live-Vorschau und 11 Vorlagen.
- **Einpress-Gewindebolzen und -Abstandshalter** (PEM-Typ, M2–M6), vorne oder hinten, mit Sacklöchern und
  bemaßtem Querschnitt.
- **Platte**: Vorlagen (19"-Rack 1–4 HE, Eurorack 3 HE, Hammond 1590B/BB/XX, Messgerätegehäuse), Material,
  Dicke, Eckenradius, Farbe von Platte und Siebdruck, Oberfläche.
- **Bemaßung und Prüfung**: automatische Bemaßung neben jedem Element, assoziative Benutzerbemaßungen,
  Messwerkzeug und Regelprüfung für Teile außerhalb der Platte, Randabstand, Mindeststeg zwischen Bohrungen,
  Überschneidungen, Kollisionen rückseitiger Körper, durchbrechende Taschen sowie Texte, Skalen und
  Beschriftungen, die in Bohrungen ragen, Taschenkanten kreuzen, unter einem Drehknopf liegen oder sich
  überlappen.
- **Parametrisches Design**: Jeder Wert akzeptiert Ausdrücke (`=W/2`, `=rand + 2*raster`) mit globalen Variablen
  und den eingebauten Größen W, H, T, HP (5,08) und U (44,45); verknüpfte automatische Verteilung, Ausrichten,
  Verteilen, Matrixkopien, Spiegeln und Drehen.
- **Export**: DXF R12 mit Ebenen, SVG (Fertigung oder realistisch, Inkscape-Ebenen), Vektor-PDF (realistisch
  oder als Bohrschablone 1:1), PNG mit wählbarer Auflösung und optionalen Benutzer- bzw. automatischen
  Bemaßungen, STL für den 3D-Druck, G-Code (Gravur, Taschenfräsen, Bohren, Kreisbögen, Fräserradiuskorrektur,
  Z-Zustellungen, Kontur) und HPGL.
- **3D-Vorschau** per Software gerendert (kein OpenGL nötig) mit Materialien und Beleuchtung.
- **Projekte**: `.efpd`-Dateien (ZIP mit lesbarem JSON), unbegrenztes Rückgängig/Wiederholen mit durchsuchbarem
  Verlauf, Änderungsprotokoll, automatisches Speichern mit Wiederherstellung nach einem Absturz, zuletzt
  geöffnete Dateien, helles und dunkles Design, anpassbare Werkzeugleisten und andockbare Fenster.

Die Maße der Bibliothek sind Richtwerte: Prüfen Sie vor dem Bearbeiten immer das Datenblatt des Herstellers.

## Projektstruktur

```
efpd/core   Geometrie, Entitäten, Dokument, Ausdrücke, Bibliothek, Prüfungen, Skalen, Bolzen (ohne Qt)
efpd/io     DXF/SVG-Import und -Export, STL-Netz, G-Code/HPGL, Projektdateien
efpd/gui    PySide6-Oberfläche: Hauptfenster, Zeichenfläche, Dialoge, 3D-Ansicht, Designs, Symbole
efpd/lang   Übersetzungen (en, de, fr)
tests       Unit-Tests und eine Zeichensimulation ohne Qt
tools       Selbsttest, Generatoren für Beispiele und Übersetzungen
packaging   PyInstaller-Spezifikation, Windows-Installer (Inno Setup) und macOS-Disk-Image-Skripte
```

Hinweise zur Architektur stehen in [ARQUITECTURA.md](ARQUITECTURA.md) (auf Spanisch).

## Lizenz

Copyright © 2026 Aleluya-Git.

Dieses Programm ist freie Software: Sie können es unter den Bedingungen der GNU General Public License Version 3,
wie von der Free Software Foundation veröffentlicht, weitergeben und/oder verändern (siehe [LICENSE](LICENSE)).
Es wird in der Hoffnung verbreitet, dass es nützlich ist, jedoch **ohne jede Gewährleistung**; sogar ohne die
implizite Gewährleistung der Marktreife oder der Eignung für einen bestimmten Zweck.
