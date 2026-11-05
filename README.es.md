
# Electronic Front Panel Designer

[English](README.md) · **Español**

Aplicación de escritorio (Windows, Linux, macOS) para diseñar paneles frontales y traseros de
equipos electrónicos: fuentes de alimentación, amplificadores, instrumentos, módulos Eurorack,
cajas Hammond, paneles rack 19" y cualquier equipo en gabinete.
<img width="1920" height="1037" alt="image" src="https://github.com/user-attachments/assets/c9bd9a6b-6e53-464d-82dc-8e66d648dfea" />


## Instalación y uso

| Sistema | Instalar | Ejecutar | Verificar |
|---|---|---|---|
| Windows | `install.bat` | `run.bat` | `autoprueba.bat` |
| Linux / macOS | `./install.sh` | `./run.sh` | `./autoprueba.sh` |

Requiere Python 3.10 o superior. La única dependencia es **PySide6** (Qt 6).

`autoprueba` ejecuta las pruebas del núcleo y un recorrido completo de la interfaz sin intervención
(dibuja con el ratón simulado, coloca componentes, exporta en todos los formatos, genera capturas y la
vista 3D). El informe queda en `autoprueba_resultado.txt` y los archivos en `autoprueba_salida/`.
Con `autoprueba.bat --visible` se ve la ventana mientras se prueba.

Proyectos de ejemplo en `ejemplos/`: fuente de laboratorio, VCO Eurorack 12HP y panel trasero de
amplificador rack 2U.

## Funciones

**Idiomas** — español, inglés, alemán y francés (*Ver → Idioma*; al primer arranque se elige el del sistema).
Para crear un idioma nuevo: *Ver → Idioma → Generar plantilla de idioma…* produce un JSON con todos los textos
(precargados en inglés); tradúzcalo, cambie `code` y `language` e instálelo con *Instalar idioma desde fichero…*.
El cambio de idioma es inmediato y conserva el diseño abierto y su historial.

**Lienzo CAD 2D** — las formas se ven mientras se crean (arrastrando o con dos clics, con la medida en vivo
junto al cursor); coordenadas en mm (origen abajo-izquierda, Y hacia arriba), zoom con rueda,
desplazamiento con botón central o Espacio, rejilla configurable, ajuste a rejilla (F9) y a objetos
(F10, centros de entidades y puntos notables del panel) — ambos y el paso de rejilla están en la barra
superior *Rejilla y ajuste* —, reglas, ventana de selección estilo AutoCAD
(izquierda→derecha: dentro; derecha→izquierda: toca), capas con visibilidad, bloqueo, color y proceso.

**Formas y mecanizados** — rectángulo, rectángulo redondeado, círculo, elipse, polígono regular,
polígono libre, ranura rectangular, ranura ovalada, agujero en D, agujeros de montaje / avellanados /
roscados con tabla métrica M2–M8 (paso, broca de roscar, cabeza avellanada), fresados/rebajes con
profundidad, importación de contornos DXF y SVG.

**Biblioteca** — 60+ componentes con mecanizado, silueta de referencia y cuerpo trasero:
potenciómetros rotatorios y deslizantes (15–60 mm y faders de 60/100 mm), encoders, interruptores, pulsadores, LEDs, LCD 16×2/20×4/128×64, OLED, TFT,
voltímetros, bananas, BNC, RCA, XLR, Speakon, jacks 3.5/6.35, DC, USB-A/B/C, RJ45, IEC (simple, a presión,
con fusible), portafusibles, D-Sub, MIDI, bornas, ventiladores 40–120 mm (con rejilla hexagonal opcional),
galvanómetros y más de 80 rejillas de ventilador (40–140 mm: recorte redondo, ranuras curvadas o hexagonal,
con orificios Ø3.2/3.7/4.3 o avellanados M3/M4). Al seleccionar un componente se muestra su miniatura (mecanizado, silueta y cuerpo) bajo el árbol, y al pasar
el ratón aparece un tooltip con la imagen. Componentes propios: editor JSON con vista previa en vivo o
«Crear desde selección», guardándolos en una **biblioteca nueva o existente** (cada biblioteca es un fichero
JSON que se puede exportar, importar y compartir).
Cada instancia guarda su definición, así que el proyecto es portable. *Las medidas son orientativas:
verifíquelas con la hoja de datos antes de mecanizar.*

**Texto y gráficos** — la herramienta Texto abre un diálogo con vista previa: varias líneas, fuente del sistema,
tamaño, grosor (fina, normal, media, seminegrita, negrita, gruesa), cursiva, subrayado, tachado, mayúsculas,
color propio (o el de serigrafía del panel), alineación, escala, espaciado entre letras, interlineado y rotación
(doble clic sobre un texto para editarlo);
rótulos automáticos de componente; logotipos SVG/DXF (como contorno) y PNG/JPG (como imagen de serigrafía).
Cada elemento se fabrica según su capa: mecanizado, fresado, grabado o serigrafía.

**Pernos y casquillos roscados** (Mayús+B) — elementos a presión tipo PEM (casquillo o perno, M2–M6,
longitudes normalizadas) delante o en el reverso del panel, con corte en sección acotado. Con *Offset de
profundidad* el agujero es ciego por detrás (no se ve por delante): se exporta en la capa FRESADO_TRASERO y se
modela en 3D/STL. La verificación avisa si el panel no es metálico o es más fino que el mínimo.

**Generador de escalas** (Mayús+E) — escalas redondas para potenciómetros rotatorios y lineales para
deslizantes, con vista previa en vivo y 11 plantillas (300°, 270°, dB, MIN/MAX, selector, semicírculo…):
ángulos inicial y final (0° = izquierda, sentido horario), radio o longitud, tipo de marca (rayas, puntos,
un carácter cualquiera o ninguna), submarcas, longitudes, grosor, posición (exterior / interior / centradas)
y separación de las marcas, línea de referencia, numeración (valor inicial, final e incremento — de 5 en 5,
de 10 en 10… —, etiquetar cada N marcas, decimales, prefijo, sufijo, signo +) o textos propios, tamaño,
separación y posición del texto, orientación del texto (0°, 45°, 90°, 135°, 180° o tangente al arco), fuente,
color general y colores propios de marcas y submarcas, y trazo simple para grabado CNC. La vista previa se
actualiza con cada cambio a escala fija sobre cuadrícula en mm (doble clic para reajustar). Al aceptar, la
escala queda pegada al cursor para colocarla con un clic.
Si hay un potenciómetro seleccionado, la escala se centra en él (en un deslizante se crea lineal, con la
longitud del recorrido, girada y a su lado). La escala sigue siendo editable (doble clic).

**Panel** — plantillas (rack 19" 1U–4U, Eurorack 3U, Hammond 1590B/BB/XX, cajas de instrumento),
material (aluminio, acero, metacrilato, PVC o personalizado), espesor, radio de esquinas, color del panel
y de la serigrafía, acabado.

**Cotas y verificación** — con *Mostrar cotas* activo (botón en la barra superior, Ctrl+Mayús+D) cada
elemento muestra su tamaño a los lados (Ø en agujeros) y los seleccionados su posición X/Y desde la esquina
inferior izquierda; el modo se elige en *Ver → Cotas automáticas*. Además: cotas horizontales, verticales y alineadas vinculadas a entidades (se mueven
con ellas), acotación automática de centros, cotas de tamaño del panel, herramienta de medición, medida
entre dos entidades (centros y holgura) y verificador (F7): huecos fuera del panel, distancia mínima al
borde, puente mínimo entre huecos, solapes, choques de cuerpos traseros, rebajes que atraviesan. También
comprueba textos, escalas y rótulos de componentes: si invaden un hueco o quedan demasiado cerca
(*Preferencias → Separación mínima texto–hueco*), si se salen del panel o rozan el borde, si cruzan el borde
de un rebaje, si quedan debajo de un mando o bisel y no se verán, y si se solapan entre sí.

**Parametrización** — cualquier medida admite expresiones (`=W/2`, `=margen + 2*paso`) con variables
globales y las integradas W, H, T, HP (5.08) y U (44.45). La distribución automática escribe posiciones
vinculadas a W/H: al cambiar el tamaño del panel los mandos se redistribuyen solos. Alinear, distribuir,
matriz de copias, simetría y giro.

**Exportación** — DXF R12 por capas, SVG (fabricación o realista, capas Inkscape), PDF vectorial
(realista o plano técnico a escala 1:1, útil como plantilla de taladrado), PNG con resolución elegible, cotas de usuario y cotas automáticas (los mismos modos que *Ver → Cotas automáticas*),
STL para impresión 3D (con rebajes), G-code (grabado, vaciado de rebajes, taladrado, interpolación
circular, compensación de radio, pasadas en Z, contorno) y HPGL para plotters y grabadoras.

**Vista 3D** (F3) — extrusión según espesor, huecos, rebajes, grabado y serigrafía, materiales con
iluminación y brillo especular, giro, zoom y desplazamiento con el ratón, captura PNG. Se dibuja por
software, sin OpenGL, por lo que funciona en cualquier equipo.

**Proyectos** — formato `.efpd` (ZIP con JSON legible), deshacer/rehacer ilimitado con lista navegable,
registro de cambios con fecha, autoguardado con recuperación tras un cierre inesperado, archivos
recientes, tema claro/oscuro, iconos en color de tamaño ajustable (iconos de importar/exportar rotulados con
el formato: DXF, SVG, PDF, PNG, STL, NC, PLT), barras de herramientas configurables y paneles acoplables.

Atajos: menú *Ayuda → Atajos y uso* (F1).

## Licencia

Copyright © 2026 Aleluya-Git. Este programa es software libre: puede redistribuirlo y/o modificarlo bajo los
términos de la Licencia Pública General de GNU, versión 3 (véase [LICENSE](LICENSE)). Se distribuye con la
esperanza de que sea útil, pero **sin ninguna garantía**. Compruebe siempre las medidas antes de mecanizar.
