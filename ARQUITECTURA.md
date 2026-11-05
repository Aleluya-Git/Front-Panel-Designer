# Arquitectura

```
main.py                     lanzador
efpd/
  i18n.py                   traducciones: tr()/N_(), idiomas integrados (lang/*.json) y de usuario, plantilla
  lang/                     en.json, de.json, fr.json (generados con tools/generar_idiomas.py)
  resources/                icono de la aplicación (png / ico)
  core/                     núcleo CAD — Python puro, sin Qt, 100 % comprobable sin interfaz
    geometry.py             primitivas, arcos, desplazamiento de contornos, distancias, trapecios
    expr.py                 expresiones seguras (AST) y variables con detección de ciclos
    entities.py             entidades paramétricas (formas, agujeros, texto, componentes, cotas…)
    document.py             panel, material, capas, variables, plantillas, serialización
    history.py              deshacer/rehacer por instantáneas (ilimitado)
    library.py              biblioteca integrada + componentes de usuario (JSON)
    layout.py               alinear, distribuir (también vinculado a W/H), matrices, acotación automática
    checks.py               verificación de interferencias y reglas de fabricación
    textpath.py             contornos de texto (proveedor Qt registrado por la GUI; fuente de trazos de reserva)
  io/                       entrada/salida sin Qt
    project.py              .efpd (ZIP + JSON), escritura atómica, autoguardado
    dxf_export.py / dxf_import.py      DXF R12 / lector ASCII con bloques, splines y abombamientos
    svg_export.py / svg_import.py      SVG en mm / lector con transformaciones y arcos
    mesh.py                 extrusión 3D (tapas por trapecios + paredes) y STL binario
    gcode.py                G-code y HPGL
  gui/                      PySide6
    main_window.py          acciones, menús, barras configurables, orquestación
    canvas.py               lienzo: transformaciones, rejilla, reglas, ajuste, herramientas, selección
    render.py               dibujo QPainter compartido por lienzo, PDF y PNG
    properties.py / docks.py / dialogs.py / view3d.py / theme.py / icons.py / qt_text.py
tests/test_core.py          pruebas unitarias del núcleo
tools/autoprueba.py         recorrido automático completo de la GUI
tools/generar_ejemplos.py   proyectos de ejemplo
```

## Decisiones

**Núcleo propio en lugar de OpenCascade.** Un panel es geometría 2D extruida; OpenCascade
(pythonocc) añade cientos de MB, instalación vía conda y fricción multiplataforma sin aportar nada
imprescindible. El núcleo usa primitivas exactas (círculos como círculos hasta la exportación) y
aproxima arcos con tolerancia de cuerda de 0,02 mm. Si en el futuro se necesitan booleanas sólidas o
STEP, basta con un exportador nuevo en `io/` que lea las mismas primitivas.

**Modelo paramétrico.** Cada entidad guarda parámetros brutos (número o `=expresión`). La geometría
se recalcula bajo demanda con un `Evaluator`; mover una entidad con posición vinculada conserva la
expresión y ajusta su término constante.

**Primitivas por rol.** `entity.geometry()` devuelve `(rol, primitiva)`; el rol `main` toma el proceso
de la capa (cut, pocket, engrave, print, ref, dim). Todos los exportadores, la verificación, la vista 3D
y el lienzo consumen esa misma lista: una sola fuente de verdad.

**Historial por instantáneas** JSON compactas en lugar de comandos inversos: exacto con expresiones,
variables y capas, y trivialmente ilimitado.

**Vista 3D por software** (QPainter, algoritmo del pintor, tapas como un único trazado par-impar):
sin dependencias de OpenGL ni problemas de controladores; suficiente para piezas planas.

**Formato .efpd**: ZIP con `project.json` legible y versionado (`version`), escritura atómica.

**Idiomas.** El texto fuente es el español; cada idioma es un JSON `{"strings": {"español": "traducción"}}`.
La lista de textos se obtiene analizando el código (llamadas `tr("…")`/`N_("…")`) y los datos (entidades,
materiales, plantillas, biblioteca). Las traducciones se mantienen en `tools/traducciones/*.py`; una prueba
unitaria comprueba que en/de/fr están completos y conservan los marcadores `{x}`.

**Bibliotecas.** La integrada es de sólo lectura; cada biblioteca de usuario es un fichero
`{"format": "efpd-library", "name": …, "components": […]}` en la carpeta de datos del usuario.

## Extender

- Nueva forma: subclase de `Entity` con `FIELDS` y `local_prims()`, decorada con `@register`;
  el panel de propiedades, la serialización y todos los exportadores la soportan automáticamente.
- Nuevo componente integrado: añadir una entrada a `BUILTIN` en `library.py`.
- Nuevo texto de interfaz: envolverlo en `tr("…")` (usar `.format()` para datos, nunca f-strings) y añadir su
  traducción en `tools/traducciones/`; ejecutar `python tools/generar_idiomas.py`.
- Nuevo formato de salida: recorrer `io.common.collect(doc, roles)`.
