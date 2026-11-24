# AutoManager league bot for Discord

The bot connects a multiplayer league's **shared folder** to a Discord channel. Players send their orders file in
the channel (or by private message to the bot); the bot stores it in the shared folder, where the commissioner's
game imports it automatically. When the commissioner runs a week, the bot posts the new league file in the channel.

The bot runs on any computer that has the league's shared folder – usually the commissioner's. It never sees the
commissioner's private file: it only reads `liga.json` / `status.json` and writes into `ordens/`.

## 1. Set up the league folder (in the game)

Commissioner screen > **League inbox > Shared folder...** – choose a folder synced with the players (Google Drive,
Dropbox, OneDrive, Syncthing) or, if only the bot is used, any folder on the commissioner's computer. The game
publishes the week there and imports orders from `ordens/` every 5 seconds while the commissioner screen is open.

## 2. Create the bot in Discord

1. Go to <https://discord.com/developers/applications> > **New Application** > give it a name.
2. **Bot** tab > **Reset Token** > copy the token (keep it secret).
3. Same tab > **Privileged Gateway Intents** > turn on **Message Content Intent** (needed to read `!status` etc.).
4. **OAuth2 > URL Generator**: scope **bot**; permissions **View Channels, Send Messages, Attach Files,
   Read Message History**. Open the generated URL and add the bot to your server.
5. In Discord, *User Settings > Advanced > Developer Mode* on; right-click the league channel > **Copy Channel ID**.
   To let the bot mention players in reminders, right-click each player > **Copy User ID**.

## 3. Configure and run

Install the library (only the bot needs it):

```bash
pip install -r requirements-bot.txt
```

Create `bot_discord.json` (all fields optional):

```json
{
  "canal": 123456789012345678,
  "jogadores": {"ana": 111111111111111111, "bia": 222222222222222222},
  "lembrete_horas": 12,
  "prefixo": "!",
  "idioma": "en"
}
```

- `canal`: the league channel. Without it the bot only answers private messages and does not post new weeks.
- `jogadores`: league player id (the name used in the league, in lowercase without accents – the file name in
  `ordens/`) → Discord user id. Used to mention missing players and to refuse orders sent by someone else.
- `lembrete_horas`: remind missing players this many hours before the deadline (once per week).
- `idioma`: `pt`, `en` or `es`.

Run (keep it running while the league is active):

```bash
DISCORD_TOKEN=your-token python -m automanager.bot_discord "/path/to/shared folder" --config bot_discord.json
```

On Windows (PowerShell): `$env:DISCORD_TOKEN="your-token"; python -m automanager.bot_discord "C:\...\folder" --config bot_discord.json`

## What players and the commissioner see

| In the channel | What happens |
|---|---|
| A player attaches an orders file (`.json`) | The bot checks the format, league, player and week and replies ✅ or ❌ with the reason. The file goes to `ordens/`; the commissioner's game checks the password signature on import, and the result appears in `!status`. |
| `!status` | Who has sent this week's orders (✅ received at, ⏳ waiting, ❌ refused with the reason, ⏭ skipped). |
| `!liga` | The current league file, attached. |
| `!prazo` | This week's deadline (set on the commissioner screen: *This week's deadline...*). |
| `!ajuda` | The list of commands. |
| Commissioner runs the week | The bot posts "Week N published" with the new league file attached (checked every minute). |
| Before the deadline | One reminder per week mentioning who is still missing. |

Security: orders are signed with each player's password, so a file sent by someone else, or changed, is refused
by the commissioner's game anyway; the `jogadores` map adds a check at the bot. The token gives control of the bot –
never share it or put it in the shared folder.
