# AutoManager – instructions for Claude

## Standing rules from the owner
- Only do what is asked. If something is missing or a change beyond the request seems needed, ask first.
- After every change to the repository, give a full report: each file changed (`git diff --stat`), what changed
  in it and why, and – separately – anything changed beyond the request.
- **Database guide**: `docs/GUIA_DATABASE.md` explains how to edit the database and every option. Whenever a
  change touches the database (a new or changed field, default, editor form, file, or how the game uses an
  option), update the guide in the same change and add a line to its change log. The technical format reference
  `docs/DATABASE.md` is kept up to date as well. `tests/test_guia_database.py` fails if an editor field is missing
  from the guide.

## Project notes
- Python + Tkinter game (Win9x look); database in JSON under `database/<year>/`.
- Tests: `python -m unittest discover -s tests` (no pytest).
- Translations: texts are Portuguese in the code; `lang/en.json` and `lang/es.json` map them (add new texts there).
