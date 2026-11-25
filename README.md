<div align="center">
  <a href="README.md">English</a> | 
  <a href="README.pt-br.md">Português</a> | 
  <a href="README.es.md">Español</a>
</div>

# AutoManager

A simple motorsport management game with a Windows 9x-style interface (Python + Tkinter).

## Requirements

- Python 3.10 or later, with Tkinter (included on Windows; on Linux: `sudo apt install python3-tk`)
- Pillow (`pip install pillow`) for images (photos, logos and tracks). The game works without it, but it only
  shows PNG images without resizing, and the editor can't convert Wikipedia photos (which come as JPG)

## How to run

```bash
python main.py               # the game
python evento_prototipo.py   # event screen prototype (separate from the game)
python -m unittest discover tests
```

The Wikipedia importer (Editor > Import from Wikipedia) and the image search need internet access.
The game itself only uses local files.

## Installers (.exe, .dmg, .deb)

Built on GitHub Actions (`.github/workflows/build.yml`) with PyInstaller, on GitHub's Windows, macOS and Linux
machines:

- Manually: **Actions** tab > **Build** > **Run workflow**. When it finishes, the files are under **Artifacts** on
  the run's page.
- By creating a `v*` tag (e.g. `v0.1` in Releases > Draft a new release): this also publishes a Release with the
  three files.

The tests run first; if they fail, nothing is built. In the installed program, saved games, leagues, settings, the
edited database and downloaded images are kept in the user folder (Windows: `%APPDATA%\AutoManager`; macOS:
`~/Library/Application Support/AutoManager`; Linux: `~/.local/share/automanager`); the database that ships with the
game is copied there on first run (on a new version, only the new files). When running from source
(`python main.py`), everything stays in the game folder. The programs are not signed: Windows (SmartScreen) and
macOS (Gatekeeper) show a warning the first time (on macOS: right-click the app > Open). The `.dmg` is for Macs with
Apple silicon (M1 or newer).

## Languages

Portuguese, English and Spanish: choose in the main menu ("Idioma / Language / Idioma"). The choice is saved in
`config.json`. Translations are in `lang/en.json` and `lang/es.json` ({"Portuguese text": "translation"});
messages with values use templates (`"{0} vence o {1}."`). Database names (drivers, teams, tracks) are not
translated; countries, tyres, weather and sessions are.

## Multiplayer (file-based)

One **commissioner** and several **players**; each week is a turn.

1. Commissioner: main menu > *Multiplayer – commissioner* > *Create a new league*: choose the series, register the
   players (name, team, password) and the policy for players who don't send their file (AI plays the turn /
   repeat last orders / block the turn). Saved in `ligas/<name>/` are the commissioner's file
   (`…_comissario.json`, do not share it) and the file for the players (`…_<year>_sNN_liga.json`).
2. Player: *Multiplayer – player* > open the league file > choose your name and enter your password. Make the
   week's decisions as in the single-player game (driver offers, chassis/engine, sponsors, loans,
   development) and, if there is an event, set the *Event plan* (setup, tyres, orders and pit stops per driver,
   for practice, qualifying and race). *Save orders* creates the password-signed file to send to the
   commissioner (you can save again; the last one imported counts).
3. Commissioner: *Import orders...*, *Skip player* if needed, and *Run week*. The league is saved and the new
   file for the players is created in the league folder.

The first time, the game shows a **step-by-step guide** (player and commissioner; later under *Help > Multiplayer guide*), and the player screen has a **Next steps this week** panel (decisions, event plan, orders saved/delivered).

Orders that were altered, or that belong to another league/week or another player, are refused. The order in which
players act in the market is drawn at random each week. Teams without a player are run by the AI.

### Inbox and shared folder

- **Shared folder** (Google Drive, Dropbox, OneDrive, Syncthing...): on the commissioner screen, *League inbox >
  Shared folder...*. Each week the game publishes `liga.json` (the players' version), a copy in `semanas/` and
  `status.json` there. The player opens the `liga.json` in that folder: *Save orders* delivers straight to
  `ordens/<player>.json`, the bottom bar shows the deadline and whether the commissioner received (or refused, with
  the reason) the orders, and the game tells you when the new week is published (it opens without asking for the
  password again). The commissioner imports automatically (every 5 s). The commissioner's file never goes into the
  shared folder.
- **Encrypted orders**: the orders file is encrypted with the player's key (derived from the password); in the
  shared folder, on Discord or by email, other players can only see whose file it is and which week it's for. Only
  the commissioner's game (and the player's own, to keep editing) can open it. Older, unencrypted files are still
  accepted.
- **Run by itself**: when all orders are in and/or at the deadline (the commissioner's game must be open).
- **This week's deadline**, **Import all from a folder...** (with the reason for each refusal) and **Submission history**.

### Discord bot (optional)

`python -m automanager.bot_discord <shared folder> --config bot_discord.json` (requires
`pip install -r requirements-bot.txt` and the token in `DISCORD_TOKEN`). Players send their orders file in the
league channel (or by private message); the bot saves it to the shared folder, posts each new week with the league
file, answers `!status`, `!liga`, `!prazo`, `!ajuda` and reminds whoever is missing before the deadline. With
`pasta_ordens` in the configuration, the bot saves orders to a private folder outside the shared folder (the
commissioner points to the same folder in *Bot's private folder...*). Step by step:
[docs/BOT_DISCORD.md](docs/BOT_DISCORD.md).

## Structure

```
main.py                     game
evento_prototipo.py         event prototype
database/<year>/*.json      series (one per file: <series>_<year>.json)
database/<year>/novos_pilotos_<year>.json   drivers who enter the market that year (optional)
database/nomes.json         names for fictional drivers and sponsors
database/imagens/           driver photos, logos (teams, chassis, engines), tracks and flags (PNG)
lang/                       translations (en, es)
ligas/                      multiplayer leagues (created by the commissioner)
saves/                      saved games
docs/CONTROLE.md            what is already defined, done, assumed or pending
tests/                      automated tests (includes a saved Wikipedia page for the importer)
docs/DATABASE.md            reference for every database field
docs/GUIA_DATABASE.md       database editing guide (editor and every option)
automanager/
  db.py                     database loading, lookup and validation
  state.py                  game state, team creation, save/load
  routines.py               weekly routines (races, finances, new season)
  mercado.py                drivers (tiers), chassis/engines, sponsors
  desenvolvimento.py        this season's / next season's car, AI
  campeonato.py             results, standings and history
  carreira.py               skill curve, retirement and new drivers
  imagens.py                image loading (database/imagens) and import from a local folder
  multiplayer.py            league, passwords, orders files, run week, absence policies
  acoes.py                  management actions (recorded in the player's orders file)
  i18n.py                   languages (translation of everything the interface shows)
  paises.py                 country names (English/Portuguese) and flags
  economia.py               AI budget, loans and bankruptcy
  contratos.py              contracts by seasons or by races
  editor/                   HTML table reading and Wikipedia importer
  ratings.py                driver/chassis/engine ratings from the weighting matrix
  event/                    event simulation (weather, lap model, sessions)
  ui/                       screens (Win9x theme, menu, new game, management, event, market,
                            development, history, editor)
tools/gerar_db_exemplo.py   generates the fictional sample series
```

The two sample series (Fórmula Alfa and Fórmula Beta) are fictional and have different rules:
own chassis × bought chassis, test drivers, refuelling, event format.
They are there to test how flexible the structure is.
