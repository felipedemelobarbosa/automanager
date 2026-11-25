<div align="center">
  <a href="README.md">English</a> | 
  <a href="README.pt-br.md">Português</a> | 
  <a href="README.es.md">Español</a>
</div>

# AutoManager

Juego de gestión de automovilismo sencillo, con interfaz al estilo Windows 9x (Python + Tkinter).

## Requisitos

- Python 3.10 o superior, con Tkinter (en Windows ya viene incluido; en Linux: `sudo apt install python3-tk`)
- Pillow (`pip install pillow`) para las imágenes (fotos, logotipos y circuitos). Sin ella el juego funciona, pero
  solo muestra imágenes PNG sin redimensionar y el editor no convierte las fotos de Wikipedia (que vienen en JPG)

## Cómo ejecutar

```bash
python main.py               # el juego
python evento_prototipo.py   # prototipo de la pantalla de evento (aislado del juego)
python -m unittest discover tests
```

El importador de Wikipedia (Editor > Importar de Wikipedia) y la búsqueda de imágenes necesitan acceso a internet.
El juego en sí solo usa archivos locales.

## Instaladores (.exe, .dmg, .deb)

Se generan en GitHub Actions (`.github/workflows/build.yml`), con PyInstaller, en las máquinas Windows, macOS y
Linux de GitHub:

- Manualmente: pestaña **Actions** > **Build** > **Run workflow**. Al terminar, los archivos quedan en
  **Artifacts**, en la página de la ejecución.
- Creando una etiqueta `v*` (p. ej.: `v0.1` en Releases > Draft a new release): además, publica una Release con
  los tres archivos.

Las pruebas se ejecutan antes; si fallan, no se genera nada. En el programa instalado, las partidas guardadas, las
ligas, la configuración, la database editada y las imágenes descargadas quedan en la carpeta del usuario (Windows:
`%APPDATA%\AutoManager`; macOS: `~/Library/Application Support/AutoManager`; Linux: `~/.local/share/automanager`);
la database que viene con el juego se copia allí en la 1.ª ejecución (en una versión nueva, solo los archivos
nuevos). Ejecutando desde el código (`python main.py`), todo sigue en la carpeta del juego. Los programas no están
firmados: Windows (SmartScreen) y macOS (Gatekeeper) muestran un aviso la 1.ª vez (en macOS: clic derecho en la
app > Abrir). El `.dmg` es para Macs con chip Apple (M1 o más reciente).

## Idiomas

Portugués, inglés y español: elige en el menú inicial ("Idioma / Language / Idioma"). La elección se guarda en
`config.json`. Las traducciones están en `lang/en.json` y `lang/es.json` ({"texto en portugués": "traducción"});
los mensajes con valores usan plantillas (`"{0} vence o {1}."`). Los nombres de la database (pilotos, equipos,
circuitos) no se traducen; los países, neumáticos, clima y sesiones sí.

## Multijugador (por archivos)

Un **comisario** y varios **jugadores**; cada semana es un turno.

1. Comisario: menú inicial > *Multijugador – comisario* > *Crear una liga nueva*: elige las categorías, registra
   a los jugadores (nombre, equipo, contraseña) y la política para quien no envíe el archivo (la IA juega el turno /
   repetir las últimas órdenes / bloquear el turno). Se guardan, en `ligas/<nombre>/`, el archivo del comisario
   (`…_comissario.json`, no distribuir) y el archivo para los jugadores (`…_<año>_sNN_liga.json`).
2. Jugador: *Multijugador – jugador* > abre el archivo de la liga > elige su nombre y escribe la contraseña. Toma
   las decisiones de la semana como en el juego de un jugador (ofertas a pilotos, chasis/motor, patrocinios,
   préstamos, desarrollo) y, si hay evento, define el *Plan del evento* (reglaje, neumáticos, órdenes y paradas por
   piloto, para entrenamientos, clasificación y carrera). *Guardar órdenes* genera el archivo firmado con la
   contraseña para enviar al comisario (puede guardar de nuevo; vale el último importado).
3. Comisario: *Importar órdenes...*, si hace falta *Saltar jugador*, y *Jugar semana*. La liga se guarda y el
   nuevo archivo para los jugadores se genera en la carpeta de la liga.

La primera vez, el juego muestra una **guía paso a paso** (jugador y comisario; después en *Ayuda > Guía del multijugador*), y la pantalla del jugador tiene el cuadro **Próximos pasos de esta semana** (decisiones, plan del evento, órdenes guardadas/entregadas).

Se rechazan las órdenes modificadas, de otra liga/semana o de otro jugador. El orden en que los jugadores actúan en
el mercado se sortea cada semana. Los equipos sin jugador quedan a cargo de la IA.

### Bandeja de entrada y carpeta compartida

- **Carpeta compartida** (Google Drive, Dropbox, OneDrive, Syncthing...): en la pantalla del comisario, *Bandeja de
  entrada de la liga > Carpeta compartida...*. Cada semana el juego publica en ella el `liga.json` (versión de los
  jugadores), una copia en `semanas/` y el `status.json`. El jugador abre el `liga.json` de esa carpeta: *Guardar
  órdenes* entrega directamente en `ordens/<jugador>.json`, la barra inferior muestra el plazo y si el comisario
  recibió (o rechazó, con el motivo) las órdenes, y el juego avisa cuando se publica la semana nueva (la abre sin
  volver a pedir la contraseña). El comisario importa automáticamente (cada 5 s). El archivo del comisario nunca va
  a la carpeta compartida.
- **Órdenes cifradas**: el archivo de órdenes se cifra con la clave del jugador (derivada de la contraseña); en la
  carpeta compartida, en Discord o por correo, los demás jugadores solo ven de quién es y de qué semana. Solo lo
  abre el juego del comisario (y el del propio jugador, para seguir editando). Los archivos antiguos, sin cifrar,
  se siguen aceptando.
- **Ejecutar sola**: cuando lleguen todas las órdenes y/o al vencer el plazo (el juego del comisario tiene que
  estar abierto).
- **Plazo de esta semana**, **Importar todas de una carpeta...** (con el motivo de cada rechazo) e **Historial de envíos**.

### Bot de Discord (opcional)

`python -m automanager.bot_discord <carpeta compartida> --config bot_discord.json` (requiere
`pip install -r requirements-bot.txt` y el token en `DISCORD_TOKEN`). Los jugadores envían el archivo de órdenes en
el canal de la liga (o por mensaje privado); el bot lo guarda en la carpeta compartida, publica cada semana nueva con
el archivo de la liga, responde a `!status`, `!liga`, `!prazo`, `!ajuda` y recuerda a quién le falta antes del
plazo. Con `pasta_ordens` en la configuración, el bot guarda las órdenes en una carpeta privada fuera de la carpeta
compartida (el comisario indica la misma carpeta en *Carpeta privada del bot...*). Paso a paso:
[docs/BOT_DISCORD.md](docs/BOT_DISCORD.md).

## Estructura

```
main.py                     juego
evento_prototipo.py         prototipo del evento
database/<año>/*.json       categorías (una por archivo: <categoría>_<año>.json)
database/<año>/novos_pilotos_<año>.json   pilotos que entran al mercado ese año (opcional)
database/nomes.json         nombres para pilotos y patrocinadores ficticios
database/imagens/           fotos de pilotos, logotipos (equipos, chasis, motores), circuitos y banderas (PNG)
lang/                       traducciones (en, es)
ligas/                      ligas multijugador (creadas por el comisario)
saves/                      partidas guardadas
docs/CONTROLE.md            lo que ya está definido, hecho, supuesto o pendiente
tests/                      pruebas automáticas (incluye una página de Wikipedia guardada para el importador)
docs/DATABASE.md            referencia de todos los campos de la database
docs/GUIA_DATABASE.md       guía de edición de la database (editor y todas las opciones)
automanager/
  db.py                     lectura, búsqueda y validación de la database
  state.py                  estado del juego, creación de equipo, guardar/cargar
  routines.py               rutinas semanales (carreras, finanzas, nueva temporada)
  mercado.py                pilotos (tiers), chasis/motores, patrocinadores
  desenvolvimento.py        coche de esta temporada / de la próxima, IA
  campeonato.py             resultados, clasificación e historial
  carreira.py               curva de habilidades, retirada y nuevos pilotos
  imagens.py                lectura de imágenes (database/imagens) e importación desde carpeta local
  multiplayer.py            liga, contraseñas, archivos de órdenes, jugar semana, políticas de ausencia
  acoes.py                  acciones de gestión (guardadas en el archivo de órdenes del jugador)
  i18n.py                   idiomas (traducción de todo lo que muestra la interfaz)
  paises.py                 nombres de países (inglés/portugués) y banderas
  economia.py               presupuesto de la IA, préstamos y bancarrota
  contratos.py              contratos por temporadas o por carreras
  editor/                   lectura de tablas HTML e importador de Wikipedia
  ratings.py                notas de piloto/chasis/motor según la matriz de ponderación
  event/                    simulación del evento (clima, modelo de vuelta, sesiones)
  ui/                       pantallas (tema Win9x, menú, nuevo juego, gestión, evento, mercado,
                            desarrollo, historial, editor)
tools/gerar_db_exemplo.py   genera las categorías ficticias de ejemplo
```

Las dos categorías de ejemplo (Fórmula Alfa y Fórmula Beta) son ficticias y tienen reglas distintas:
chasis propio × chasis comprado, pilotos de prueba, repostaje, formato del evento.
Sirven para probar la flexibilidad de la estructura.
