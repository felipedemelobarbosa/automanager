# AutoManager – Database editing guide

How to create and edit the game's database with the editor, and what every option does.
Labels are given as they appear with the game in English (the editor follows the language chosen in the
main menu); the JSON key is next to each one, for whoever edits the files by hand.
Technical reference of the file format: [`DATABASE.md`](DATABASE.md).

> This guide is kept up to date with the game: every change to database options updates it (see
> [Change log](#change-log) at the end).

---

## 1. How the database works

- **One file per series and season**: `database/<year>/<series id>_<year>.json`
  (e.g. `database/2026/formula_alfa_2026.json`). The file holds the series' rules (`categoria`) and its
  drivers, chassis, engines, teams, sponsors and calendar.
- **New game**: the player picks a season year and one or several series of that year. The game copies
  everything from those files into the save. **Files of later years are not read during a career**: the career
  evolves on its own (drivers age and retire, cars are developed, regulations change). The only per-year files
  read during a career are the new-drivers lists (`novos_pilotos_<year>.json`, section 10).
- **Changes in the editor only affect new games.** A save that already exists keeps its own copy.
- **Ratings** (drivers, chassis, engines, team resources, track features) go from 0 to 100. A rating of 50 gives
  the track's base lap time.
- **Optional fields**: empty fields use the game's default (given in this guide). Fields starting with
  `_comentario` are notes and are ignored. Unknown fields are preserved.
- **Several series at once**: series of the same year form one "world" with a shared driver pool. `tier`
  (1 = top) defines the ladder; drivers move between series through the market.
- **Packaged version** (.exe/.dmg/.deb): the editable database lives in the user's folder
  (Windows `%APPDATA%\AutoManager`, macOS `~/Library/Application Support/AutoManager`,
  Linux `~/.local/share/automanager`). Running from source, it is the `database/` folder of the game.

---

## 2. The editor

Main menu > **Open editor**.

### Toolbar

| Button | What it does |
|---|---|
| **New...** | Creates a new series: ID, name, year and, optionally, **Copy rules from:** an existing file (copies the whole `categoria` block: rules, tyres, weather, event format, weighting...; lists start empty). |
| **Open...** | Opens a database file. |
| **Save** / **Save as...** | Saves. The default name is `database/<year>/<id>_<year>.json`. If validation finds problems, it asks before saving. |
| **Duplicate to another year...** | Copies the open file to another year and saves it as `database/<new year>/<id>_<new year>.json` (a new starting point, e.g. the 2027 season). Drivers' ages are increased by the difference in years. |
| **Validate** | Checks the whole file. Double-click a problem to jump to the record. |
| **Import from Wikipedia...** | Wizard: series and year, choose the season page, copy rules from an existing file, review teams/calendar, apply. Fills drivers, teams, chassis, engines, calendar and (optionally) images. Ratings are estimated from the season's results; track data uses defaults to adjust. |
| **Find images...** | Downloads the missing photos, logos, track images and flags from Wikipedia. |
| **Images from folder...** | Matches the files of a folder to records by file name (name, ID or article; for tracks also the location). Sub-folders `pilotos/`, `equipes/`, `chassis/`, `motores/`, `pistas/`, `bandeiras/` limit the type. |

### Record tabs (Drivers, Chassis, Engines, Teams, Sponsors, Calendar)

- List on the left with **Search** and a filter; **New...**, **Duplicate** and **Delete** below.
- Form on the right. The yellow line on top summarises the record in plain words (e.g. the contract).
  Problems of the record show in red.
- Each record has a unique **ID** (generated from the name; references between records use it).

### Category tab

Sub-tabs: General, Rules, Regulations, Points and pit stops, Tyres, Weather, Event format, Development,
Market and economy, Weighting, Track map, Simulation and **Advanced (tree)**: every setting of the series as
a tree (double-click a value to edit). Settings that have no form field are edited there (section 11).

---

## 3. Category – General

| Label | JSON | What it does |
|---|---|---|
| Category ID | `id` | Used in the file name `<id>_<year>.json`. Required. |
| Name, Year, Currency | `nome`, `ano`, `moeda` | Identification. |
| Tier | `tier` | Level of the series: 1 = top, 2, 3... New fictional drivers debut in the lowest tier loaded. |
| From lower tier / From higher tier / From same tier | `mobilidade.de_tier_inferior` / `de_tier_superior` / `mesmo_tier` | Multipliers of the chance of a driver coming to this series from a lower tier (moving up), a higher tier (moving down) or the same tier. |
| Retired driver returning: chance per season | `mobilidade.retorno.prob_anual` | Chance of a former driver of the series returning (falls with time away). Default 0.04 (≈ 1 return per season in F1). |
| Return: maximum seasons out | `mobilidade.retorno.anos_maximos_fora` | Default 6. |
| Return: maximum age | `mobilidade.retorno.idade_maxima` | Default 40. |
| Keep the database's driver level | `carreira.calibracao_automatica` | Default on: new drivers get the database's level and potential and the level is corrected gently each season, so the field neither strengthens nor weakens over the years. |

---

## 4. Category – Rules

### Drivers, teams and parts

| Label | JSON | What it does |
|---|---|---|
| Main drivers per team | `regras.pilotos_principais_por_equipe` | Cars per team – the maximum: no signing ever takes a team above it (several offers can be open at once; when a seat fills, the other offers for it are refused). |
| Minimum race drivers per team | `regras.pilotos_minimos_por_equipe` | Optional (empty = no minimum). Main drivers each team must have able to race (not injured, assigned when there is a rotation) at every race. Below it, before the race, a computer team sends offers to several free drivers at once until it reaches the minimum; with no free driver, the game creates a new one for the team. A player's team can't advance the race week: pending offers are answered at once when the player clicks Continue (in multiplayer, when the commissioner runs the week – the week is blocked while a player's team is short). The file must give every active team the minimum at every race. |
| Test drivers / Test drivers per team | `regras.pilotos_de_teste`, `regras.pilotos_de_teste_por_equipe` | Whether there are test drivers, and how many. |
| Teams develop the chassis | `regras.desenvolvimento_chassis_por_equipe` | On: each team develops its own chassis. Off: chassis are bought from suppliers. |
| Allowed chassis sources | `regras.fontes_de_chassis_permitidas` | `proprio` (own), `fabricante` (supplier), `equipe` (another team's chassis). Empty = own only (with chassis development) or supplier only (without). With development and a buying source, each team chooses between developing and buying, both at the initial development and for next season. |
| Customers per chassis | `regras.clientes_por_chassis` | How many teams can buy the same team's chassis. Default 2; 0 = no limit. The selling team receives what customers pay. |
| Own engine allowed | `regras.desenvolvimento_motor_por_equipe` | Whether teams may build their own engine. |
| Teams that may have an own engine | `regras.equipes_com_desenvolvimento_de_motor` | None ticked = all. |
| Allowed engine sources | `regras.fontes_de_motor_permitidas` | `proprio`, `equipe` (another team's engine), `fabricante`. |
| Collective tests | `regras.testes_coletivos` | Whether the calendar's test sessions happen. |
| Engines per driver per season | `regras.motores_por_temporada` | Quota. Empty = no quota. |
| Penalty for an engine over the quota | `regras.penalidade_motor_grid` | Grid places. Default 10. |
| Success ballast (kg) | `regras.lastro_por_posicao` | By championship position: 1st, 2nd... (e.g. 54, 45, 39). Empty = none. |
| Time per kg of ballast | `regras.lastro_tempo_por_kg` | Share of lap time per kg. Default 0.00007 (≈ 0.06 s per 10 kg on a 90 s lap). |

### Money

| Label | JSON | What it does |
|---|---|---|
| Average budget (USD) | `regras.orcamento_medio` | Reference for teams' starting cash, costs and AI budgets. |
| Average yearly inflation | `regras.inflacao_media_anual` | E.g. 0.03 = 3%. Raises budgets, salaries, prices, TV and prizes each season. |
| Sponsorships | `regras.patrocinios` | Whether there are sponsors. |
| TV income | `regras.renda_tv.ativa` | Whether there is TV money. |
| TV: from year | `regras.renda_tv.ano_inicio` | No TV income before this year (racing was not always broadcast). Empty = always. Example database: 1981. |
| TV: average amount per team | `regras.renda_tv.valor_medio_por_equipe` | Per season; paid a little after each race. |
| TV: factor by position | `regras.renda_tv.fator_por_posicao_campeonato` | By the **previous season's final team standings**: 1st, 2nd... (e.g. 1.4, 1.3, 1.2). First year of a game: 1.0 for all. A new team gets the last place's factor. |
| Race prizes | `regras.premios_corrida.ativa` | Paid to the team after each race (a cancelled race pays nothing). |
| Prize: win (USD) | `regras.premios_corrida.vitoria` | 1st place. |
| Prize: podium, per car (USD) | `regras.premios_corrida.podio` | 1st to 3rd (the winner also gets the win prize). |
| Prize: per point scored (USD) | `regras.premios_corrida.por_ponto` | Points of the race result. Example: Fórmula Alfa 300k / 150k / 13.5k per point (≈ 5% of all budgets per season). |
| Chassis and engine negotiation | `regras.negociacao_partes.ativa` | Off (default): list price. On: the supplier asks a hidden price (list ± variation) and answers offers the following week. |
| Negotiation: asking price variation | `regras.negociacao_partes.variacao` | Share of the list price. Default 0.15 (±15%). |

### Car and driver importance, age

| Label | JSON | What it does |
|---|---|---|
| Car importance / Driver importance | `regras.importancia_carro` / `regras.importancia_piloto` | Weights of car and driver in lap time; must add up to 1. |
| Maximum driver age | `regras.idade_pilotos.idade_maxima` | Above it the series does not hire and contracts end at the season change. Empty = no limit. |
| Preferred age (up to) | `regras.idade_pilotos.preferida_ate` | Junior series: AI teams prefer drivers up to this age. |
| Penalty per year above the preferred age | `regras.idade_pilotos.penalidade_por_ano` | Points taken from the driver's rating in AI teams' choice. E.g. 4. |

### Red flag (oval in the rain) and major crashes

| Label | JSON | What it does |
|---|---|---|
| Red flag (oval in the rain): clock | `regras.bandeira_vermelha.relogio_durante_suspensao` | `parado` (default): the wait doesn't use session time. `corre`: it does. |
| Waiting limit – practice/qualifying (min) | `regras.bandeira_vermelha.limite_espera_sessao_min` | Passed without drying: the session ends with the times set. 0 = no limit. Default 60. |
| Waiting limit – race (min) | `regras.bandeira_vermelha.limite_espera_corrida_min` | The race ends on the red-flag lap (cancelled if it hadn't started). 0 = no limit. Default 120. |
| Major crash: chance per lap (race) | `regras.batida_grave.prob_por_volta` | Several cars out together. ×3 on lap 1, × weather accidents, × difficulty. Default 0.0015. |
| Major crash: factor in practice/qualifying | `regras.batida_grave.fator_treinos` | Default 0.5. |
| Major crash: minimum / maximum cars | `regras.batida_grave.carros_min` / `carros_max` | Default 2 / 5. |
| Major crash: chance of ending the session | `regras.batida_grave.prob_encerrar_sessao` | Otherwise red flag and restart. Default 0.2. |
| Major crash: chance of injury / death (per driver) | `regras.batida_grave.prob_lesao` / `prob_morte` | Default 0.06 / 0.002. |
| Injury: races missed (min., max.) | `regras.batida_grave.lesao_corridas` | E.g. 1, 6. |
| Injury: loss per attribute (min., max.) | `regras.batida_grave.lesao_perda_atributos` | Permanent points lost in fitness, concentration and driving. E.g. 1, 6. |

### Supplier parts

Chassis and engines that no team develops (suppliers, and series without development) change every season.

| Label | JSON | What it does |
|---|---|---|
| Supplier parts change every season | `regras.evolucao_fornecedores.ativa` | Default on. |
| Suppliers: yearly update (± points) | `regras.evolucao_fornecedores.variacao_anual` | Default 2. |
| Suppliers: chance of a new model | `regras.evolucao_fornecedores.prob_novo_modelo` | Per season. Default 0.25 (≈ 1 every 4 years). The year at the end of the name changes (Marlin M26 → M28). |
| Suppliers: new model (min., max. points) | `regras.evolucao_fornecedores.novo_modelo` | Default -3, 8. |
| Suppliers: pull back to the database level | `regras.evolucao_fornecedores.reversao` | Share of the gap to the starting level, per season. Default 0.2. The price follows the level. |

---

## 5. Category – Regulations

Announced mid-season for the next one (news, History > Regulations, development screen), applied at the
season change. Off by default (imported seasons); on in the example database.

| Label | JSON | What it does |
|---|---|---|
| Regulation changes | `regulamento.ativo` | On/off. |
| Announcement week | `regulamento.semana_anuncio` | Default 30. |
| Major change: chance per season | `regulamento.prob_grande_mudanca` | Default 0.2 (F1: ~1 every 4 years). |
| Major change: extra chassis loss (min., max.) | `regulamento.perda_grande_mudanca` | Added to the maintenance loss. Default 0.15, 0.30. Without chassis development, all suppliers launch new models. |
| Major change: car importance increase | `regulamento.aumento_importancia_carro` | Default 0.05, 0.10. |
| Car importance return per season | `regulamento.convergencia_por_temporada` | Without a major change, car importance returns towards the database value. Default 0.02. |
| Development limit: chance per season | `regulamento.prob_limite_desenvolvimento` | One part (chassis or engine) that teams develop. Default 0.15. |
| Limit: duration in seasons (min., max.) | `regulamento.limite_duracao` | Default 2, 4. |
| Limit: chance of a freeze | `regulamento.prob_congelamento` | Otherwise points per attribute per season. Default 0.5. |
| Limit: points per attribute (min., max.) | `regulamento.limite_pontos_por_temporada` | Default 2, 5. |
| Car importance adjustment: chance / (±) | `regulamento.prob_ajuste_importancia` / `ajuste_importancia` | Default 0.15 / 0.03. |
| Car importance: minimum / maximum | `regulamento.importancia_carro_min` / `importancia_carro_max` | Default 0.3 / 0.8. |

**Base lap time evolution** (same tab), used for years without a time set on the track (section 9):

| Label | JSON | What it does |
|---|---|---|
| Track base times evolve every year | `evolucao_tempo_base.ativa` | Default on. |
| Base time: drop per season (stable rules) | `evolucao_tempo_base.ganho_por_temporada` | Default 0.012 (−1.2%; F1: 1–2% a year). |
| Base time: increase at a major change | `evolucao_tempo_base.grande_mudanca` | Default 0.03 (+3%; the weaker chassis already adds ~0.5%). |
| Base time: drop per season without regulations | `evolucao_tempo_base.ganho_sem_regulamento` | With regulation changes off. Default 0.002 (−0.2%, F1's long-term average). |

---

## 6. Category – Points and pit stops

| Label | JSON | What it does |
|---|---|---|
| Points per position | `pontuacao.posicoes` | 1st, 2nd, 3rd... separated by commas. |
| Fastest lap / Pole position | `pontuacao.volta_mais_rapida` / `pontuacao.pole` | Extra points. |
| Interrupted race: distance for full points | `pontuacao.corrida_interrompida.distancia_minima` | Share of the laps (e.g. 0.5). Below it, partial points. No lap completed = nobody scores. |
| Interrupted race: partial points | `pontuacao.corrida_interrompida.pontos_parciais` | `metade` (half) or `proporcional` (by distance). |
| Mandatory stop | `regras_pitstop.obrigatorio` | No time penalty: whoever doesn't stop suffers from tyres/fuel. |
| Minimum stops | `regras_pitstop.paradas_minimas` | |
| Refuelling / Tyre changes | `regras_pitstop.reabastecimento` / `troca_de_pneus` | |
| Two dry compounds mandatory | `regras_pitstop.dois_compostos_secos` | Dry race: each car uses at least 2 different dry compounds (cars that used wet tyres are exempt). |
| Penalty (two compounds) in seconds | `regras_pitstop.penalidade_dois_compostos_s` | 0 = disqualification. |
| Seconds per lap of fuel | `regras_pitstop.segundos_por_volta_de_combustivel` | Refuelling time. |

---

## 7. Category – Tyres, Weather, Event format

### Tyres

Compound table (`pneus.compostos`, ID → compound):

| Column | JSON | What it does |
|---|---|---|
| Name, Type | `nome`, `tipo` | Type: `seco` (dry), `chuva_leve` (light rain), `chuva_pesada` (heavy rain). |
| Pace | `ritmo` | Lap time multiplier on new tyres (lower = faster). |
| Degradation per lap | `degradacao` | Share of time lost per lap of use. |
| Life (laps) | `vida` | Laps until the cliff, on a reference track and car (track wear and car divide it). |
| Cliff intensity | `cliff` | Extra loss × (laps beyond life)^1.5. |
| Warm-up laps / Thermal sensitivity | `aquecimento_voltas` / `sensibilidade_termica` | Warm-up; how much aggression and car use speed up wear. |

| Label | JSON | What it does |
|---|---|---|
| Available compounds | `pneus.compostos_disponiveis` | Compounds used by this series. |
| Warm-up penalty | `pneus.penalidade_aquecimento` | |
| Critical wear (%) | `pneus.desgaste_critico` | Above it the tyre may puncture. |
| Breaking wear (%) | `pneus.desgaste_quebra` | Above it a puncture tends to mean retirement. |

### Weather

Effects table (`clima.efeitos`, per weather state – dry, light rain, heavy rain): Time `tempo` (lap time
multiplier), Chassis / Engine / Driver weight `peso_chassis` / `peso_motor` / `peso_piloto`, Accidents
`acidentes` (risk multiplier), Randomness `aleatoriedade`, Overtaking `ultrapassagem`.

| Label | JSON | What it does |
|---|---|---|
| Share of heavy rain | `clima.proporcao_chuva_forte` | Of the rainy sessions, how many are heavy. |
| Stability (per 10 min) | `clima.estabilidade_por_10min` | Chance the weather doesn't try to change every 10 minutes. It doesn't change how much it rains: that's each track's `prob_chuva`. |

### Event format

- **Free practice** (`formato_evento.treinos_livres`): list of sessions with Name `nome`, Limit `limite`
  (`tempo` minutes or `voltas` laps) and Value `valor`.
- **Qualifying** (`formato_evento.classificacao`): list of stages, in order; the grid comes from the last one.
  Each stage has a **Model** `modelo`:
  - `tempo`: session(s) by time/laps (`limite`, `valor`), with **phases** `fases` (Name, Limit, Value,
    **Eliminated at the end** `eliminados`; 0 = no elimination – e.g. Q1/Q2/Q3);
  - `grupos`: groups with interleaved grid (**Number of groups** `grupos`);
  - `volta_unica`: single lap (**Timed laps** `voltas_cronometradas`, **Criterion** `criterio` best lap/average,
    **Running order** `ordem_saida` reversed championship/championship/random);
  - `corrida_classificatoria`: qualifying race (**Heat laps** `voltas`, **Heat grid** `grid`: previous result,
    reversed championship, championship, random);
  - `campeonato`: by the championship standings (**Reversed** `invertido`).
- **Race** (`formato_evento.corrida`): Name, **Maximum time (min)** `tempo_maximo_min` (0 = no limit),
  **Reverse the top N of the grid** `grid_invertido_top` (0 = normal grid).
- Collective tests: number of days and minutes per day in `formato_teste_coletivo` (`{dias, minutos_por_dia}`,
  default 2 × 240; Advanced tree only).

---

## 8. Category – Development, Market and economy, Weighting, Track map, Simulation

### Development

| Label | JSON | What it does |
|---|---|---|
| Development by team | `desenvolvimento` | Untick if the series has none (`null`). |
| Maintenance loss | `desenvolvimento.perda_manutencao` | Share lost in each attribute when keeping the car for next season (e.g. 0.30). |
| Automatic cost calibration | `desenvolvimento.calibracao_automatica` | Default on: the game adjusts the cost per point so chassis and engines stay, on average, at the database level over the seasons. |
| Chassis / Engine: cost per point | `desenvolvimento.chassis.custo_por_ponto` / `motor...` | |
| Chassis / Engine: fixed cost up to | `...limite_custo_fixo` | Above this level the point gets progressively dearer. |
| Chassis / Engine: progressive scale | `...escala_progressiva` | Lower = dearer faster. Cost of +1 point above the limit: × (1 + ((value − limit)/scale)²). |
| Initial investment (created team) | `desenvolvimento_inicial` | For a team created by the player. |
| Initial: chassis/engine per point, base, maximum | `desenvolvimento_inicial.chassis|motor.custo_por_ponto`, `atributo_base`, `atributo_maximo` | Cost per point and the range of the initial car. |

### Market and economy

| Label | JSON | What it does |
|---|---|---|
| Minimum / Maximum salary per race | `simulacao.mercado_pilotos.salario_minimo_por_corrida` / `salario_maximo_por_corrida` | Range of drivers' asking salaries (by rating). |
| Share of cash for drivers | `simulacao.mercado_pilotos.fracao_orcamento_pilotos` | AI teams' salary ceiling. |
| Weight of salary / of prospects in the choice | `simulacao.mercado_pilotos.peso_salario_na_escolha` / `peso_perspectiva_na_escolha` | How drivers choose between offers: salary (compared with the asking price) and the team's prospects (car 60%, resources 40%). Default 0.55 / 0.45. |
| Week offers start | `simulacao.mercado_pilotos.semana_inicio_propostas` | From this week AI teams sign for next season, and may also sign a driver for a later season (a seat that opens in 2+ seasons, through a contract ending or a retirement; small weekly chance, higher for richer teams and nearer seasons; at most one such contract per team). The player can offer for any future season at any time (Market > Start > In year). |
| Fee factor | `contratos.fator_multa` | Termination fee = factor × value per race × races left. When a contract (driver, chassis or engine) is signed to start in a future season while the current one still runs then, the fee covers only the overlapping races and the current contract is shortened to end the season before. |
| Sponsorship: search chance/week, performance weight, offer validity | `mercado_patrocinio.prob_busca_semanal`, `peso_desempenho`, `validade_oferta_semanas` | How free sponsors look for teams. |
| Minimum reserve, Use of surplus cash | `financas.reserva_minima`, `uso_do_excedente` | AI teams' cash management (shares of the average budget). |
| Loan interest (per year), Loan limit, Default term (seasons) | `financas.juros_anual`, `limite_emprestimo`, `prazo_temporadas` | Limit × average budget × (0.5 + resources/100). |
| Weeks until bankruptcy | `financas.semanas_para_falencia` | Negative cash with no credit for this long = bankruptcy. |
| Teams that may appear | `novas_equipes` | Table of inactive teams (Team, Year): with a year they appear in that year; empty year = random. |

### Weighting

Matrix (`ponderacao`): for `piloto`, `chassis` and `motor`, the weight of each attribute in each track
feature (`retas`, `curvas_alta`, `curvas_baixa`, `desgaste`, `dificuldade`, `chuva`, `sessao_treino`,
`sessao_classificacao`, `sessao_corrida`). **General weights**: `peso_caracteristicas` (weight of each feature)
and `importancia_motor_por_caracteristica` (how much the engine weighs on straights and corners).
Empty cells = 0.

### Track map

Defaults of the calendar's **Compute straights and corners from the track map...** (`mapa_pista`):

| Label | JSON | Default |
|---|---|---|
| Default criterion | `criterio` | `raio` (corner radius) or `velocidade` (estimated speed) |
| Straight: radius from (m) / Slow corner: radius below (m) | `raio_reta` / `raio_baixa` | 400 / 80 (between them = fast corner) |
| Straight: speed from (km/h) / Slow corner: below (km/h) | `vel_reta` / `vel_baixa` | 250 / 150 |
| Grip in corners (g) | `aderencia` | 2.0 (speed = √(grip × 9.81 × radius)) |

### Simulation

Event constants (`simulacao.*`; all optional, default in brackets):

| Label | JSON | What it does |
|---|---|---|
| Performance range | `amplitude_desempenho` | Maximum lap-time gap between rating 0 and 100 (share). |
| Dispersion by consistency | `dispersao_consistencia` | Only worsens the lap (0.006). |
| Form variation per event | `forma_sigma` | (0.0015 ≈ 0.13 s on a 90 s lap). |
| Cubic penalty in the rain | `penalidade_chuva` | Poor driver + car in the wet (0.0035). |
| Track evolution / Laps to rubber in (per car) | `evolucao_pista` / `voltas_emborrachamento` | (0.012 / 15; rain washes part away). |
| Learning per lap, Maximum setup penalty, Reduction by the 'setup' attribute | `aprendizado_por_volta`, `penalidade_maxima_acerto`, `reducao_maxima_acerto_piloto` | Setup and learning. |
| Fuel effect per lap | `efeito_combustivel_por_volta` | |
| Error rate per lap, Accident rate, Breakdown rate | `taxa_erro_volta`, `taxa_acidente_base`, `taxa_quebra_base` | |
| Base overtaking, Collision risk in a fight, Minimum gap between cars (s) | `ultrapassagem_base`, `risco_colisao_disputa`, `distancia_minima_s` | |
| Qualifying errors (factor), Traffic on the fast lap, Deleted lap (track limits) | `fator_erro_classificacao`, `trafego_volta_rapida`, `limites_pista` | (0.5 / 0.05 / 0.012) |
| Dirty air | `ar_sujo` | Loss behind another car (0.01). |
| Overtaking on street tracks (factor) | `fator_ultrapassagem_rua` | (0.6) |
| Reference straights / straights exponent for overtaking | `ultrapassagem_retas_referencia` / `ultrapassagem_expoente_retas` | Track factor = (straights / reference)^exponent (0.4 / 2): fast tracks easy, slow tracks hard. |
| Overtaking: weight / exponent of the pace gap | `ultrapassagem_sensibilidade_ritmo` / `ultrapassagem_expoente_ritmo` | With the same pace you hardly pass (1.2 / 2). |
| Teams' strategy variation (s), Stint length variation | `variacao_estrategia_s`, `variacao_stint` | 0 = all follow the best strategy (6 / 0.1). |
| Damage that brings the car in | `dano_para_reparo` | (0.006) |
| Safety car after an accident, SC vs VSC, VSC after a breakdown | `prob_sc_acidente`, `fracao_sc`, `prob_vsc_quebra` | (0.45, ×1.35 on street tracks / 0.65 / 0.3) |
| Pace under SC / VSC, Pit stop under SC / VSC | `ritmo_sc`, `ritmo_vsc`, `pit_sob_sc`, `pit_sob_vsc` | (1.4 / 1.35 / 0.55 / 0.7) |
| Engine life (laps), Power loss at end of life | `vida_motor_voltas`, `perda_potencia_motor` | (700, 0 = no wear / 3) |
| Grid interval (s) | `intervalo_grid_s` | |
| Oval: slipstream gain, pack compression, ease of passing in the pack, "Big One" risk, debris cautions per race, restart reach (s), short-oval contact | `oval.vacuo`, `oval.compressao_pelotao`, `oval.piso_ultrapassagem_pelotao`, `oval.multiplicador_batida_pelotao`, `oval.amarelas_detritos_por_corrida`, `oval.alcance_relargada_s`, `oval.colisao_oval_curto` | (0.012 / 0.6 / 0.4 / 6 / 6 / 0.8 / 2.5). Other oval settings: section 11. |

---

## 9. Records

### Drivers (`pilotos`)

| Label | JSON | What it does |
|---|---|---|
| ID, Name, Nationality, Age | `id`, `nome`, `nacionalidade`, `idade` | Nationality in Portuguese (e.g. Brasil) – it also picks the flag. |
| Peak year | `ano_pico` | Year the skills reach their maximum. Empty: the game decides (age 27–31). |
| Potential | `potencial` | Average of the attributes at the peak (0–100). Empty: the game estimates. |
| Retirement | `ano_aposentadoria` **or** `idade_aposentadoria` | By year or by age (form field `aposentadoria`). Random: the game decides (34–40). |
| Wikipedia article, Photo | `wikipedia`, `imagem` | Article in English (empty = uses the name); photo in `database/imagens`. |
| Attributes | `atributos.*` | Consistency, Race pace, Concentration, Rain, Acceleration, Car setup, Teamwork, Qualifying, Fitness, Driving, Start (0–100). |
| Contract | `contrato` | No contract = free driver. Team, Salary per race (USD), Role (`principal` main / `teste` test), Duration in seasons **or** races. |
| Assigned races | `contrato.corridas_definidas` | Optional (rotation): tick the races the driver takes part in; the duration becomes the number ticked. None ticked = all races. Valid only in the file's season. |
| Future contract | `contrato_futuro` | Optional: the driver is already signed for a later season (one per driver). Team, Salary per race, Role, **Starts in (year)** (`inicio_ano`) and Duration. Until then the driver keeps the current contract or, if it ends earlier, is free but cannot sign for that season. Checks: the year must be after the file's year and after the current contract ends; the driver must not retire before it (a random retirement is moved to after the contract); the team must have a free seat that year (current contracts that still run plus future ones, at most the number of cars – or test seats). No assigned races. |

### Chassis (`chassis`)

| Label | JSON | What it does |
|---|---|---|
| ID, Name, Nationality, Wikipedia article, Logo | `id`, `nome`, `nacionalidade`, `wikipedia`, `logotipo` | |
| Owner team | `equipe` | Team that develops it. Empty = supplier that sells to teams. |
| Attributes | `atributos.*` | Aerodynamics, Grip, Gearbox, Brakes, Electrical system, Handling, Reliability, Qualifying, Rain, Tyres. |
| Contract | `contrato` | Terms offered to customers: value per race and seasons. A team's chassis without a price, when other teams may buy it, costs 15% of the average budget per season at level 75 (scaled by level). |

### Engines (`motores`)

| Label | JSON | What it does |
|---|---|---|
| ID, Name, Nationality, Wikipedia article, Logo | as above | |
| Power | `potencia` | 0–100. |
| Manufacturer / Manufacturer team | `fabricante.tipo` (`equipe`/`fabricante`), `fabricante.equipe` | A team of the series or an independent manufacturer. |
| Exclusive / Exclusive to team | `exclusividade.exclusivo`, `exclusividade.equipe` | Only that team (and the manufacturer) may use it. |
| Contract | `contrato` | Terms offered to customers. |

### Teams (`equipes`)

| Label | JSON | What it does |
|---|---|---|
| ID, Name, Nationality | `id`, `nome`, `nacionalidade` | |
| Active | `ativa` | Inactive teams may appear later. |
| Main / Secondary colour | `cor`, `cor_secundaria` | `#RRGGBB`. Empty = automatic colour. |
| Resources | `recursos` | Team structure (0–100): starting cash, appeal to drivers (40% of the team's prospects), precision of the AI's setup and strategy, loan limit. |
| Wikipedia article, Logo | `wikipedia`, `logotipo` | |
| Starting cash (USD) | `caixa` | Empty = from the average budget and resources. |
| Year of entry | `ano_surgimento` | For inactive teams. Empty = random. |
| Chassis / Chassis source | `chassis.id`, `chassis.origem` | `proprio` (own), `terceiros` (supplier), `equipe` (another team). Contract (value per race) for bought chassis. |
| Engine / Engine source | `motor.id`, `motor.origem` | `proprio`, `equipe`, `fabricante`. |
| Future chassis / Future engine | `chassis_futuro`, `motor_futuro` | Optional: the team has already bought a chassis or engine for a later season (one per part). Chassis or Engine (`id`), Source (`origem`: chassis `terceiros` or `equipe`; engine `equipe` or `fabricante` – a future part is always bought), Price per race, **Starts in (year)** (`contrato.inicio_ano`) and Duration. The year must be after the file's year; if the current part is bought, its contract must end before. It replaces the current part in that year. One that starts next season also ends the team's own design project for that part. |
| Chance of closing / appearing per year | `prob_fechamento`, `prob_surgimento` | 0–1 (e.g. 0.02 = 2%). |

### Sponsors (`patrocinadores`)

| Label | JSON | What it does |
|---|---|---|
| ID, Name, Country, Sector | `id`, `nome`, `pais`, `ramo` | |
| Active | `ativo` | Inactive sponsors may appear later. |
| Base value (USD/season) | `valor_base` | Reference for the offers the company makes. |
| Preference / Preference value | `preferencia.tipo`, `preferencia.valor` | Driver nationality, team nationality or championship position (the value is the country or the highest position). |
| Contract | `contrato` | No contract = looking for a team. Team, Amount (USD), Payment (per season/per race), Duration and unit (seasons/races). **Contracts in the file are the sponsorships teams start the game with.** |
| Chance of leaving / appearing per year | `prob_fechamento`, `prob_surgimento` | |

### Calendar (`calendario`)

| Label | JSON | What it does |
|---|---|---|
| ID, Name, Location | `id`, `nome`, `local` | Location "Town, Country" – the country gives the flag. |
| Active | `ativo` | Inactive = reserve track that may join later. |
| Week | `semana` | 1–52. |
| Type | `especie` | `corrida` (race) or `treino` (collective test). |
| Wikipedia article, Track image | `wikipedia`, `imagem` | |
| Track type | `tipo_pista` | `mista` (circuit), `oval`, `rua` (street). Ovals have pack racing, cautions and no racing in the rain. |
| Base practice/qualifying time, Base race time (s) | `tempo_base_treino`, `tempo_base_corrida` | Lap time of a rating-50 car and driver. |
| Base lap times per year (s) | `tempos_por_ano` | Optional: "2028: 88.4 / 90.1; 2031: 87.2 / 88.9" (practice / race). Years without a value follow the automatic evolution (section 5) from the last year given. |
| Race laps | `voltas_corrida` | |
| Straights, Fast corners, Slow corners | `retas`, `curvas_alta`, `curvas_baixa` | Shares (normalised). **Compute straights and corners from the track map...** fills them from a map. |
| Tyre wear, Difficulty | `desgaste_pneus`, `dificuldade` | 50 = reference. |
| Pit stop time loss (s), Chance of rain | `duracao_pitstop`, `prob_chuva` | Rain: share of rainy sessions in the long run. |
| Chance of leaving / joining the calendar | `prob_inativar`, `prob_ativar` | Random, at each season change. |
| Years it joins / leaves the calendar | `anos_entrada`, `anos_saida` | E.g. joins 2028, 2033; leaves 2030. In those years it's certain (the random chance doesn't apply). It can join and leave several times. A race doesn't join if the same track is already on the calendar. |

---

## 10. Files outside the editor

- **New drivers of a year**: `database/<year>/novos_pilotos_<year>.json` – same format as drivers, plus an
  optional `"categoria"` (series ID). With it, the driver debuts directly in that series (even the top one);
  without it, in the lowest tier. Read at the start of a game (for that year) and at each season change.
  They count towards the season's quota: the game then creates only the fictional drivers still needed
  (retirements + 2).
- **Names**: `database/nomes.json` – first names and surnames by nationality (fictional drivers) and company
  name parts (fictional sponsors).
- **Images**: `database/imagens/` (paths in `imagem`/`logotipo`). Flags in
  `database/imagens/bandeiras/<country in Portuguese, no accents>.png` (104 included), found by nationality,
  country or the location of the track.

---

## 11. Options only in JSON (Advanced tree)

Not in the forms; edit them in **Advanced (tree)** or in the file (default in brackets):

- `simulacao.oval`: `alcance_vacuo_s` (1.5), `retas_pelotao` ([0.5, 0.75]), `custo_disputa_pelotao` (0.3),
  `carros_max_pelotao` (12), `prob_amarela_acidente` (0.9), `prob_amarela_quebra` (0.35), `voltas_amarela`
  ([4, 7]), `respeitar_tempo_maximo` (false – ovals run the full distance), `efeito_largada` (0.3),
  `tentativas_relargada` (3), `piso_relargada` (0.6).
- `regras.batida_grave.atributos_afetados` (["fisico", "concentracao", "conducao"]): attributes hurt by injuries.
- `pneus.adequacao_clima`: lap time multiplier by weather × tyre type.
- `formato_teste_coletivo`: `{dias, minutos_por_dia}` of collective tests (2 × 240).

---

## 12. Common tasks

- **Create a new series**: New... > copy rules from a similar series > fill teams, chassis, engines, drivers,
  sponsors and calendar > Validate > Save.
- **Next season of a series**: Duplicate to another year... (a new starting point; it doesn't change running
  careers).
- **Reserve track joining in a given year**: Calendar > untick Active > Years it joins the calendar.
- **Track leaving and coming back**: Years it leaves (e.g. 2030) and Years it joins (e.g. 2033).
- **Lap times of a future season**: Calendar > Base lap times per year.
- **A rookie debuting directly in a series**: `novos_pilotos_<year>.json` with `"categoria"`.
- **Customer chassis in a series with development**: Rules > Allowed chassis sources (own + another team
  and/or supplier) > Customers per chassis.
- **Spec series** (everyone buys): Rules > untick Teams develop the chassis; give the supplier chassis a
  contract (price); Development > untick Development by team.
- **Historic season without TV money**: Rules > TV: from year (e.g. 1981).
- **Teams starting without sponsors**: Sponsors > remove each contract.

---

## Change log

| Date | Change |
|---|---|
| 2026-11-18 | First version of the guide (game as of commit `57de5cf`). |
| 2026-11-18 | Contracts can start in any future season (drivers, chassis, engines): `semana_inicio_propostas` now also starts the AI's far-ahead offers; `fator_multa` charges only the overlap; note that the file holds only current contracts. |
| 2026-11-19 | Drivers: new optional `contrato_futuro` (Future contract, with `inicio_ano`) in the file and the editor; checks for start year, current contract, retirement and seats. Editor: fields of an unticked group (e.g. no contract) are no longer marked red. |
| 2026-11-19 | Teams: new optional `chassis_futuro` / `motor_futuro` (Future chassis / Future engine, with `contrato.inicio_ano`) in the file and the editor. |
| 2026-11-20 | Rules: new `pilotos_minimos_por_equipe` (Minimum race drivers per team) with file check; Main drivers per team is now a hard maximum when signing. |
