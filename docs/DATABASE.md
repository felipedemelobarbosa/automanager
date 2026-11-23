# Formato da database (JSON)

Guia de edição, com todas as opções explicadas: [`GUIA_DATABASE.md`](GUIA_DATABASE.md).

Local: `database/<ano>/<categoria>_<ano>.json`. Um arquivo por categoria e temporada.
Todos os atributos vão de 0 a 100. Campos que começam com `_comentario` são ignorados pelo jogo.
Campos extras que você acrescentar são preservados no savegame.

```
{
  "versao_formato": 1,
  "categoria": { ... },
  "pilotos": [...], "chassis": [...], "motores": [...],
  "equipes": [...], "patrocinadores": [...], "calendario": [...]
}
```

## categoria

| Campo | Descrição |
|---|---|
| `id`, `nome`, `ano`, `moeda` | identificação |
| `tier` | nível da categoria (1 = topo, 2, 3...) |
| `mobilidade` | multiplicadores da chance de um piloto vir para esta categoria: `de_tier_inferior`, `de_tier_superior`, `mesmo_tier` |
| `mercado_patrocinio` | `{prob_busca_semanal, peso_desempenho, validade_oferta_semanas}` |
| `desenvolvimento` | `null` = sem desenvolvimento. `{perda_manutencao, chassis|motor: {custo_por_ponto, limite_custo_fixo, escala_progressiva}}`. Custo de +1 ponto: fixo até o limite; acima, × (1 + ((valor − limite)/escala)²). Calibração automática (`calibracao_automatica`, padrão true): no início do jogo o `custo_por_ponto` de chassis e motor é multiplicado por um fator para que a verba anual sustentável das equipes (receita prevista − despesas fixas) reconstrua, em média, o nível de chassis/motor da database; o fator fica em `calibracao` no save (o arquivo não muda). A cada virada de temporada o fator é corrigido aos poucos (−15% a +20%) se o nível médio real se afastar do alvo (a receita real inclui patrocínios fechados depois). Motores de fabricantes também evoluem a cada temporada: verba base que mantém o nível da database × receita de fornecimento atual/inicial (entre 0,8 e 1,25) × sorteio de ±15% |
| `regras.pilotos_de_teste` | há pilotos de testes? |
| `regras.pilotos_principais_por_equipe` / `pilotos_de_teste_por_equipe` | vagas por equipe (máximo: nenhuma contratação passa dele) |
| `regras.pilotos_minimos_por_equipe` | opcional (vazio = sem mínimo): titulares aptos (sem lesão, escalados) que cada equipe precisa ter em cada corrida. Abaixo dele, antes da corrida, o PC propõe a vários pilotos livres ao mesmo tempo até chegar ao mínimo (sem piloto livre, o jogo cria um); o jogador não avança a semana da corrida (as propostas pendentes são respondidas na hora). O arquivo precisa dar o mínimo a cada equipe ativa em todas as corridas |
| `regras.desenvolvimento_chassis_por_equipe` | cada equipe desenvolve o próprio chassis? (se não, chassis vêm da lista `chassis` com contrato) |
| `regras.fontes_de_chassis_permitidas` | opcional: `proprio`, `fabricante` (chassis de fornecedor) e/ou `equipe` (chassis de outra equipe). Sem a lista: só próprio com desenvolvimento de chassis, só de fornecedor sem. Com desenvolvimento e alguma fonte de compra, cada equipe escolhe entre desenvolver e comprar: no desenvolvimento inicial (equipe criada) e para a próxima temporada (comprar no Mercado com início na próxima temporada encerra o projeto próprio; o cliente cujo contrato termina pode voltar a fazer o próprio chassis, do zero). Quem vende: só a equipe que faz e usa o chassis (e não comprou o da próxima temporada); com clientes, ela não pode trocar o próprio por um comprado. Chassis de equipe sem preço na database: 15% do orçamento médio por temporada no nível 75, proporcional ao nível, recalculado a cada temporada. O cliente usa o mesmo chassis da dona (com a evolução dela). A IA compara o carro próprio esperado para a próxima temporada com o da equipe vendedora e compra se ele for 3+ pontos melhor |
| `regras.clientes_por_chassis` | quantas equipes podem comprar o chassis de uma mesma equipe (no arquivo da categoria; sem o campo, 2; 0 = sem limite). A equipe que faz e vende chassis ou motor recebe, a cada corrida, o valor que o cliente paga (receita "fornecimento") |
| `regras.desenvolvimento_motor_por_equipe` | há motor próprio? |
| `regras.equipes_com_desenvolvimento_de_motor` | lista de ids das equipes que podem desenvolver motor (vazia = todas) |
| `regras.fontes_de_motor_permitidas` | `proprio`, `equipe` (motor feito por outra equipe), `fabricante` |
| `regras.testes_coletivos` | há sessões de teste coletivo? |
| `regras.orcamento_medio` | em dólares |
| `regras.inflacao_media_anual` | ex.: 0.03 = 3% |
| `regras.patrocinios` | há patrocínios? |
| `regras.renda_tv` | `{ativa, ano_inicio, valor_medio_por_equipe, fator_por_posicao_campeonato[]}`. Paga a cada corrida: valor médio ÷ corridas × o fator da posição da equipe na classificação FINAL da temporada anterior (como a divisão de prêmios da F1). 1º ano do jogo: fator 1,0 para todas; equipe que não estava na classificação (nova): fator do último lugar. `ano_inicio` (opcional): antes dele não há renda de TV (nem sempre houve transmissão; F1: acordos de TV a partir do Pacto da Concórdia de 1981) |
| `regras.premios_corrida` | `{ativa, vitoria, podio, por_ponto}` (USD): depois de cada corrida, a equipe recebe o prêmio da vitória (1º), o de pódio por carro do 1º ao 3º e o valor por ponto marcado (corrida cancelada não paga). Sobem com a inflação. Exemplo: Fórmula Alfa 300 mil / 150 mil / 13,5 mil por ponto; Fórmula Beta 25 mil / 12 mil / 1,2 mil – total da temporada ~5% dos orçamentos somados (referência: premiações de corrida da IndyCar), ~5 a 7% da receita das equipes. Entra na receita prevista das equipes do PC (média por equipe) |
| `regras.importancia_carro` / `importancia_piloto` | pesos; devem somar 1.0 |
| `desenvolvimento_inicial` | equipe criada pelo usuário: `{chassis|motor: {custo_por_ponto, atributo_base, atributo_maximo}}` |
| `pontuacao` | `{posicoes[], volta_mais_rapida, pole}` |
| `regras_pitstop` | `{obrigatorio, paradas_minimas, reabastecimento, troca_de_pneus, segundos_por_volta_de_combustivel, dois_compostos_secos, penalidade_dois_compostos_s}` (sem penalidade de tempo: quem não para sofre com pneu/combustível). Opcional `dois_compostos_secos` (false): na corrida seca cada carro usa pelo menos 2 compostos secos diferentes (quem usou pneu de chuva fica dispensado; a IA cumpre); quem não cumpre é desclassificado (`penalidade_dois_compostos_s` = 0) ou recebe esses segundos |
| `pneus.compostos` | por composto: `{nome, tipo (seco/chuva_leve/chuva_pesada), ritmo, degradacao, vida, cliff, aquecimento_voltas, sensibilidade_termica}`. `ritmo` = multiplicador do tempo com pneu novo; `degradacao` = fração do tempo perdida por volta de uso; `vida` = voltas até o cliff (pista e carro de referência); `cliff` = perda extra × (voltas além da vida)^1,5 |
| `pneus.compostos_disponiveis` | quais compostos a categoria usa |
| `pneus.adequacao_clima` | multiplicador por clima atual × tipo de pneu |
| `pneus.penalidade_aquecimento`, `desgaste_critico`, `desgaste_quebra` | desgaste = % da vida usada; acima do crítico o pneu pode furar; a partir da quebra o furo tende a abandono |
| `clima.efeitos` | por clima: multiplicador de tempo e pesos de chassis/motor/piloto, acidentes, aleatoriedade, ultrapassagem |
| `clima.proporcao_chuva_forte`, `estabilidade_por_10min` | variação do clima. `prob_chuva` da pista = fração das sessões com chuva a longo prazo (das chuvas, `proporcao_chuva_forte` é forte). Cada sessão mantém o clima da anterior (50%) ou sorteia de novo; dentro da sessão, a cada 10 min há (1 − estabilidade) de chance de tentar mudar um passo (seco ↔ leve ↔ forte), aceito na proporção que mantém esse equilíbrio. A estabilidade só muda a frequência das mudanças, não quanto chove |
| `formato_evento.treinos_livres[]` | `{nome, limite: "tempo"|"voltas", valor}` (tempo em minutos) |
| `formato_evento.classificacao` | um dict ou uma **lista de etapas**. Cada etapa tem `modelo`: `tempo` (`fases[]` com `{nome, limite, valor, eliminados}`, ou `limite`/`valor` de sessão única; sem eliminação vale a melhor volta da sessão inteira), `grupos` (`grupos`, `limite`, `valor`; grid intercalado), `volta_unica` (`voltas_cronometradas`, `criterio`: melhor_volta/media, `ordem_saida`: campeonato_invertido/campeonato/aleatoria), `corrida_classificatoria` (`voltas`, `grid`: anterior/campeonato/campeonato_invertido/aleatorio) ou `campeonato` (`invertido`) |
| `formato_teste_coletivo` | `{dias, minutos_por_dia}` dos testes coletivos (calendário com `especie: "treino"`) |
| `formato_evento.corrida` | `{nome, tempo_maximo_min, grid_invertido_top}` |
| `novas_equipes` | `[{equipe: id, ano: n ou null}]` equipes inativas que podem surgir (com ano: naquele ano; sem ano: por sorteio) |
| `financas` | `{reserva_minima, uso_do_excedente, juros_anual, limite_emprestimo, prazo_temporadas, semanas_para_falencia}` |
| `contratos` | `{fator_multa}`: multa de rescisão = fator × valor por corrida × corridas restantes (contrato novo que começa numa temporada futura: só as corridas que se sobrepõem) |
| `ponderacao` | matriz de pesos: para `piloto`, `chassis` e `motor`, cada característica (`retas`, `curvas_alta`, `curvas_baixa`, `desgaste`, `dificuldade`, `chuva`, `sessao_treino`, `sessao_classificacao`, `sessao_corrida`) tem pesos sobre os atributos. `peso_caracteristicas` define o peso de cada característica; `importancia_motor_por_caracteristica` quanto o motor pesa em retas e curvas |
| `pneus.desgaste_quebra` | a partir deste desgaste (%) um furo tende a causar abandono |
| `simulacao` | constantes do evento (amplitude de desempenho, aleatoriedade, evolução da pista, taxas de acidente/quebra/erro, ultrapassagem, efeitos das ordens, penalidades) e `mercado_pilotos` (salários mínimo/máximo, fração do caixa para pilotos, pesos salário × perspectiva, semana de início das propostas) |

## pilotos

`{id, nome, nacionalidade, idade, ano_pico, potencial, ano_aposentadoria | idade_aposentadoria, wikipedia, imagem, atributos{consistencia, ritmo_corrida, concentracao, chuva, aceleracao,
acerto_carro, trabalho_equipe, classificacao, fisico, conducao, largada}, contrato}`

- `ano_pico`, `potencial` (média no pico, 0-100) e a aposentadoria são opcionais; o jogo define os que faltarem
- aposentadoria: `ano_aposentadoria` (ano em que deixa de correr) **ou** `idade_aposentadoria` (deixa de correr ao
  completar essa idade; vale também se o piloto for reaproveitado em databases de outros anos). Não use os dois
- novos pilotos de um ano: `database/<ano>/novos_pilotos_<ano>.json` (mesmo formato + `categoria` opcional)
- nomes para pilotos e patrocinadores fictícios: `database/nomes.json`

`contrato`: `null` (piloto livre) ou `{equipe, valor_por_corrida, situacao: "principal"|"teste"}` mais
`temporadas: n` **ou** `corridas: n`. O mesmo vale para os contratos de chassis/motor.
Piloto já contratado para uma temporada futura: `contrato_futuro` (opcional, um por piloto) = os campos do contrato
mais `inicio_ano` (depois do ano do arquivo e depois do fim do contrato atual; sem `corridas_definidas`). O piloto
não pode se aposentar antes (aposentadoria sorteada é adiada para depois do contrato) e a equipe precisa de vaga
nesse ano (contratos atuais que ainda valem + futuros ≤ carros, ou vagas de teste).

Revezamento: contrato de piloto por corridas pode ter `corridas_definidas: [ids do calendário]`. O piloto só corre
nessas corridas e o contrato termina depois da última delas (`corridas` = quantidade de corridas da lista; o editor
preenche sozinho). Sem a lista, corre todas enquanto durar o contrato. Uma equipe pode ter mais pilotos principais que
`pilotos_principais_por_equipe`, desde que em nenhuma corrida haja mais escalados que esse limite (a validação acusa).
A lista vale só para a temporada da database (some na virada de temporada). O importador da Wikipedia preenche a
lista a partir da coluna "Rounds" da tabela de inscritos.

## chassis

`{id, nome, nacionalidade, equipe, atributos{aerodinamica, grip, cambio, freio, eletrica, dirigibilidade,
confiabilidade, classificacao, chuva, pneus}, contrato}`

- `equipe`: id da equipe dona (chassis próprio) ou `null` (chassis de fornecedor)
- `contrato`: termos oferecidos quando de terceiros: `{valor_por_corrida, temporadas}`

## motores

`{id, nome, nacionalidade, potencia, fabricante, exclusividade, contrato}`

- `fabricante`: `{"tipo": "equipe", "equipe": "<id>"}` ou `{"tipo": "fabricante"}`
- `exclusividade`: `{"exclusivo": true, "equipe": "<nome da equipe>"}`: só essa equipe (e a fabricante) pode usar
- `contrato`: termos oferecidos a clientes `{valor_por_corrida, temporadas}`

## equipes

`{id, nome, ativa, nacionalidade, recursos, caixa, chassis, motor, ano_surgimento, prob_fechamento, prob_surgimento, cor, cor_secundaria, wikipedia, logotipo}`

- `chassis`: `{id, origem: "proprio"|"terceiros", contrato?: {valor_por_corrida, temporadas}}`
- `motor`: `{id, origem: "proprio"|"equipe"|"fabricante", contrato?}`. Com `proprio`, o menu Desenvolvimento > Motor é liberado
- `chassis_futuro` / `motor_futuro` (opcionais, um por peça): peça já comprada para uma temporada futura,
  `{id, origem, contrato: {valor_por_corrida, temporadas|corridas, inicio_ano}}`. Origem: chassis `terceiros`|`equipe`,
  motor `equipe`|`fabricante`. `inicio_ano` depois do ano do arquivo; se a peça atual for comprada, o contrato dela
  tem de terminar antes. Na temporada `inicio_ano` ela substitui a atual (os contratos futuros feitos no jogo usam o
  mesmo formato no save).
- `caixa`: `null` = calculado a partir do orçamento médio e dos recursos
- `cor` / `cor_secundaria` (opcionais): cores da equipe no formato `"#RRGGBB"`. Sem `cor`, o jogo usa uma cor fixa derivada do ID da equipe

## patrocinadores

`{id, nome, ativo, pais, ramo, valor_base, preferencia, contrato, prob_fechamento, prob_surgimento}`

- `valor_base`: valor anual de referência das propostas que o patrocinador faz

- `preferencia`: `{tipo: "nacionalidade_piloto"|"nacionalidade_equipe"|"posicao_campeonato", valor}`
- `contrato`: `{equipe, valor, pagamento: "por_corrida"|"por_temporada", duracao, unidade: "corridas"|"temporadas"}`

## calendario

`{id, nome, ativo, semana, especie: "corrida"|"treino", local, tipo_pista: "mista"|"oval"|"rua",
tempo_base_treino, tempo_base_corrida, voltas_corrida, retas, curvas_alta, curvas_baixa, desgaste_pneus,
dificuldade, duracao_pitstop, prob_chuva, prob_inativar, prob_ativar, anos_entrada, anos_saida, wikipedia, imagem}`

- tempos em segundos; `retas`/`curvas_*` são proporções (a soma é normalizada)
- tempo base por ano: opcional `tempos_por_ano` (`{"2028": [treino, corrida], ...}`, anos depois do ano do arquivo;
  no editor: "2028: 88.4 / 90.1; 2031: 87.2 / 88.9"). Anos sem valor seguem a evolução automática a partir do
  último ano informado (ou dos tempos do arquivo), com `categoria.evolucao_tempo_base`: `ganho_por_temporada`
  (0,012: −1,2% por temporada de regras estáveis), `grande_mudanca` (0,03: +3% no ano de uma grande mudança de
  regulamento), `ganho_sem_regulamento` (0,002: −0,2% por temporada com o regulamento desligado, a média de longo
  prazo da F1) e `ativa` (true). A nota de chassis, motor e pilotos também entra no tempo de volta (nota 50 = tempo
  base), mas o nível médio fica perto do da database (calibração), então só mexe ±0,5% ao longo dos anos; na grande
  mudança, o chassis mais fraco já soma ~0,5% (por isso 3% e não 3,5%)
- entrada e saída do calendário: a cada virada de temporada, `prob_inativar` (evento ativo) e `prob_ativar`
  (evento de reserva, inativo) são sorteados. Opcionais `anos_entrada` e `anos_saida` (listas de anos, depois do
  ano do arquivo; no ano do arquivo vale `ativo`): nesses anos a pista entra ou sai com certeza, no lugar do
  sorteio; a pista pode entrar e sair várias vezes (ex.: entra em 2028, sai em 2030, volta em 2033). Uma corrida
  não entra se a mesma pista já estiver no calendário
- `tipo_pista: "oval"` não admite chuva: se chover, bandeira vermelha e a sessão fica suspensa até a pista secar; se já estiver chovendo no início, a sessão é adiada; a corrida relarga atrás do safety car. Regras em `categoria.regras.bandeira_vermelha`: `relogio_durante_suspensao` (`"parado"`, padrão: a espera não tira tempo de pista nem conta para o tempo máximo da corrida; `"corre"`: conta), `limite_espera_sessao_min` (60) e `limite_espera_corrida_min` (120): passou do limite sem secar, a sessão é encerrada (valem os tempos feitos; as fases que faltam não acontecem e a ordem segue os tempos já feitos e, sem tempo, o campeonato) e a corrida termina na volta da bandeira vermelha (se nem largou, é cancelada: ninguém pontua e ela não conta no campeonato). 0 = sem limite
- no editor, "Calcular retas e curvas pelo mapa da pista..." preenche `retas`, `curvas_alta` e `curvas_baixa`
  (somando 100) a partir do mapa do artigo do circuito na Wikipedia (`wikipedia`) ou de uma imagem do computador.
  A escala vem do comprimento do circuito (quadro do artigo, ou informado). Cada trecho da volta é classificado
  pelo raio de curva ou pela velocidade estimada, com os limites de `categoria.mapa_pista`:
  `{criterio: "raio"|"velocidade", raio_reta: 400, raio_baixa: 80, vel_reta: 250, vel_baixa: 150, aderencia: 2.0}`
  (todos opcionais; velocidade = raiz(aderência × 9,81 × raio)). Se o traçado não for reconhecido (ou sair errado),
  marca-se a pista clicando sobre o mapa
- `especie: "treino"` = teste coletivo

## imagens

Fotos de pilotos (`imagem`), logotipos de equipes, chassis e motores (`logotipo`) e imagens de pistas (`imagem` no
calendário) são caminhos relativos a `database/imagens/` (ex.: `"pilotos/max_verstappen.png"`), sempre opcionais.
`wikipedia` é o título do artigo na Wikipedia em inglês usado para buscar a imagem (o importador preenche sozinho;
para chassis e motores usa o artigo da marca – construtor / fabricante do motor –, que costuma ter o logotipo).

Bandeiras: `database/imagens/bandeiras/<país em português, sem acentos>.png` (ex.: `brasil.png`, `reino_unido.png`).
Já vêm no jogo (104 países). Não precisam de campo: são achadas pela `nacionalidade` (pilotos, equipes, chassis,
motores), pelo `pais` (patrocinadores) e pelo país no fim do `local` (calendário: `"Serra Azul, Brasil"`). Nomes em
inglês também são reconhecidos.

Como obter as imagens (no editor):
- importação da Wikipedia (opção marcada por padrão) ou botão "Buscar imagens..." – fotos, logotipos, pistas e as
  bandeiras de países que faltarem;
- em cada registro: "Buscar na Wikipedia" ou "Escolher arquivo..." (arquivo do computador);
- "Imagens de pasta...": associa os arquivos de uma pasta aos registros pelo nome do arquivo (nome, ID ou artigo;
  nas pistas também o local; sem diferenciar acentos/maiúsculas). Subpastas `pilotos/`, `equipes/`, `chassis/`,
  `motores/`, `pistas/` e `bandeiras/` limitam o tipo. Arquivo com nome de país vira bandeira.
Tudo é convertido para PNG (biblioteca Pillow) e copiado para `database/imagens/`; o jogo só lê esses arquivos.

## modelo de volta e de corrida (categoria.simulacao e categoria.regras)

Todos opcionais (entre parênteses, o padrão). Em `simulacao`:
- `dispersao_consistencia` (0,006): dispersão que só piora a volta, k × (1,5 − 0,316·√(consistência/5)) × acaso
- `forma_sigma` (0,0015): variação da forma de cada piloto por evento (a forma muda devagar, 60% vem do evento anterior)
- `penalidade_chuva` (0,0035): penalidade cúbica para piloto + carro ruins no molhado
- `evolucao_pista` (0,012) e `voltas_emborrachamento` (15 por carro): pista emborracha com as voltas de todos; a chuva lava parte
- `fator_erro_classificacao` (0,5), `trafego_volta_rapida` (0,05), `limites_pista` (0,012): erros, tráfego e voltas apagadas na classificação
- `ar_sujo` (0,01), `ultrapassagem_base` (0,3): tráfego na corrida
- ultrapassagem pela pista: fator = (retas / `ultrapassagem_retas_referencia` (0,4)) ^ `ultrapassagem_expoente_retas` (2), × `fator_ultrapassagem_rua` (0,6) em pista de rua; pista rápida (muita reta) = fácil, lenta e travada = difícil. `ultrapassagem_sensibilidade_ritmo` (1,2) e `ultrapassagem_expoente_ritmo` (2): chance × (0,05 + sensibilidade × diferença de ritmo em %^expoente) – com ritmo parecido quase não se passa; com diferença grande (pneu novo, carro bem melhor), sim
- `variacao_estrategia_s` (6): as equipes do PC escolhem entre as estratégias perto da ótima por sorteio (mais recursos = mais perto da ótima; 0 = todas seguem a ótima); `variacao_stint` (0,1): variação do tamanho dos stints. A estratégia automática do jogador é sempre a ótima calculada
- `dano_para_reparo` (0,006): dano (fração do tempo de volta) que leva o carro ao box
- `prob_sc_acidente` (0,45, ×1,35 em pista de rua), `fracao_sc` (0,65), `prob_vsc_quebra` (0,3), `ritmo_sc` (1,4),
  `ritmo_vsc` (1,35), `pit_sob_sc` (0,55), `pit_sob_vsc` (0,7): safety car e VSC
- `vida_motor_voltas` (700; 0 desliga) e `perda_potencia_motor` (3): desgaste do motor

Em `regras`:
- `motores_por_temporada` (sem cota) e `penalidade_motor_grid` (10): cota de motores e punição no grid
- `lastro_por_posicao` (ex.: `[54, 45, 39]`) e `lastro_tempo_por_kg` (0,00007): lastro de sucesso pela posição no campeonato

O motor de cada piloto fica em `equipe.motores` no jogo salvo (voltas de uso e motores usados), zerado a cada temporada.



## Batidas graves, lesões e mortes, corrida interrompida

`categoria.regras.batida_grave` (todos opcionais; entre parênteses, o padrão):
- `prob_por_volta` (0,0015): chance de batida grave por volta do líder na corrida (× 3 na 1ª volta, × `acidentes`
  do clima, × (0,5 + dificuldade/100)); `fator_treinos` (0,5): multiplicador em treinos/classificação/testes
- `carros_min` (2) e `carros_max` (5): quantos carros abandonam juntos (na corrida, carros próximos na pista)
- `prob_encerrar_sessao` (0,2): chance de a bandeira vermelha encerrar a sessão; senão, a corrida relarga atrás do
  safety car e a sessão cronometrada continua (com `relogio_durante_suspensao: "corre"`, perde 15 min)
- `prob_lesao` (0,06) e `prob_morte` (0,002): por piloto envolvido. Vítimas ficam fora do resto do evento
- `lesao_corridas` ([1, 6]): corridas fora, sorteadas; `lesao_perda_atributos` ([1, 6]): pontos perdidos em cada
  atributo de `atributos_afetados` (["fisico", "concentracao", "conducao"]), de forma permanente
- substituição: equipe do PC promove o piloto de testes (até o titular voltar) ou contrata pelo mercado; equipe de
  jogador (individual e multijogador) recebe alerta e o carro não corre até contratar. Quem é contratado como
  titular enquanto há titular lesionado é substituto (sai quando ele volta). Falecidos ficam em `st["falecidos"]`

`categoria.pontuacao.corrida_interrompida`: corrida encerrada antes do fim (chuva que não para no oval, batida
grave): a partir de `distancia_minima` (0,5 = 50% das voltas) a pontuação é integral; abaixo, `pontos_parciais`
`"metade"` (padrão) ou `"proporcional"` à distância (posições e volta mais rápida; a pole não muda). Sem nenhuma
volta completa, a corrida é cancelada e ninguém pontua.


## Nível dos pilotos e retorno de aposentados

- `categoria.carreira.calibracao_automatica` (true): no início do jogo o nível da database é guardado (média dos
  titulares de cada categoria, nível dos estreantes = pilotos de até 21 anos do tier mais baixo, potencial = nível
  dos pilotos com 25 anos ou mais). Pilotos fictícios novos estreiam com esse nível e esse potencial (não com a
  média atual da categoria). A cada temporada, se a média dos titulares do tier mais alto se afastar da
  referência, o potencial dos estreantes e dos pilotos antes do auge é corrigido (no máx. 2 pontos por temporada).
  Nos tiers de baixo o nível vem do mercado (quem as equipes contratam).
- `categoria.mobilidade.retorno`: `prob_anual` (0,04), `anos_maximos_fora` (6), `idade_maxima` (40). A cada
  temporada, um aposentado da categoria pode voltar às pistas (chance × (1 − (anos fora − 1)/anos máximos)). Volta
  como piloto livre na categoria de onde saiu, com a idade e o declínio do tempo parado, e decide de novo quando
  se aposenta (1 a 4 temporadas). Base real: na F1, ~1 piloto por temporada volta depois de 1+ temporada parado.
  Quem sai para outra categoria e volta depois o faz pelo mercado (mobilidade entre tiers).
- `categoria.regras.idade_pilotos`: `idade_maxima` (vazio = sem limite): acima dela a categoria não contrata
  (equipes do PC e propostas do jogador) e, na virada de temporada, o contrato termina sem multa; aposentados acima
  dela não voltam para a categoria. `preferida_ate` e `penalidade_por_ano`: na escolha das equipes do PC, cada ano
  acima da idade preferida tira esses pontos da nota do piloto – categorias de base preferem pilotos jovens. Na
  database de exemplo a Fórmula Beta prefere até 22 anos (4 pontos/ano): a idade média dos titulares cai de ~26
  para ~21–22 anos.


## Peças de fornecedor, negociação e regulamento

- `categoria.regras.evolucao_fornecedores` (todos opcionais; padrão ligado): chassis e motores que nenhuma equipe
  desenvolve (fornecedores e categorias sem desenvolvimento) mudam a cada temporada. `variacao_anual` (2): todo ano,
  de −2 a +2 pontos em cada atributo; `prob_novo_modelo` (0,25, ~1 a cada 4 anos): modelo novo, de
  `novo_modelo` [−3, 8] pontos (o ano no fim do nome muda: Marlin M26 → M28); `reversao` (0,2): fração da distância
  até o nível médio inicial das peças da categoria (o nível da database se mantém; a média esperada dos modelos
  novos também é descontada). O preço por corrida acompanha o nível; contratos já assinados não mudam. `ativa: false`
  desliga. Motores de fabricante em categorias com desenvolvimento continuam evoluindo com verba própria.
- `categoria.regras.negociacao_partes` (padrão desligado = preço de tabela): `{ativa, variacao}`. Ligada, cada
  fornecedor pede a cada equipe um valor escondido (tabela ± `variacao`, 0,15), fixo por fornecedor, equipe e
  temporada. A equipe faz uma oferta (Mercado > Chassis/Motor) e a resposta vem na semana seguinte: aceita se a
  oferta cobre o pedido. As equipes do PC também negociam (sobem a oferta a cada recusa; sem a peça para correr,
  pagam o pedido na hora). No multijogador, a oferta vai nas ordens.
- `categoria.regulamento` (padrão desligado; a database de exemplo liga): no meio da temporada (`semana_anuncio`,
  30) a categoria anuncia as regras da temporada seguinte, aplicadas na virada:
  - grande mudança (`prob_grande_mudanca` 0,2): a manutenção do chassis perde mais (`perda_grande_mudanca`
    [0,15, 0,30], somada à perda normal) e a importância do carro sobe (`aumento_importancia_carro` [0,05, 0,10]).
    Sem desenvolvimento de chassis, todos os fornecedores lançam modelo novo. Nas temporadas sem grande mudança a
    importância do carro volta ao valor da database (`convergencia_por_temporada` 0,02);
  - limite de desenvolvimento (`prob_limite_desenvolvimento` 0,15) de uma parte que as equipes desenvolvem, por
    `limite_duracao` [2, 4] temporadas: congelado (`prob_congelamento` 0,5) ou no máximo
    `limite_pontos_por_temporada` [2, 5] pontos por atributo por temporada. A 1ª temporada do limite recebe o carro
    do projeto (manutenção ou novo); dali em diante o carro passa de um ano para o outro sem perda e não há projeto
    novo;
  - ajuste pequeno (`prob_ajuste_importancia` 0,15, ± `ajuste_importancia` 0,03) da importância do carro, entre
    `importancia_carro_min` (0,3) e `importancia_carro_max` (0,8); a do piloto é o complemento.
  Referência real (F1): grandes mudanças em 1989, 1994-95, 1998, 2009, 2014, 2017, 2022 e 2026; motor congelado em
  2007-2014 e 2022-2025. O que foi anunciado aparece nas notícias, em Histórico > Regulamento e na tela de
  desenvolvimento.

## Corrida em oval (`simulacao.oval`)

Vale para pistas com `tipo_pista: "oval"`. O tipo de oval sai das retas e curvas da própria pista, de forma
contínua: `pelotão` cresce com as retas entre `retas_pelotao` [0,5; 0,75] (superspeedway, "pack racing") e `curto`
cresce com as curvas lentas (short track; 50% de curvas de baixa = oval curto pleno); o intermediário fica entre os
dois. Para tirar as retas e curvas do mapa, use o critério pela velocidade (`mapa_pista.criterio_oval`, o padrão em
ovais): pelo raio, as curvas de um superspeedway (~300 m) contam como curvas e ele vira um intermediário.
- vácuo: quem vem até `alcance_vacuo_s` (1,5 s) atrás ganha até `vacuo` (0,012) do tempo nas retas; quem tem um carro
  colado atrás ganha metade (empurrão) – sozinho é mais lento; no pelotão o ar sujo quase não pesa
- `compressao_pelotao` (0,6): no superspeedway o vácuo e o limite de potência aproximam o ritmo dos carros
- `piso_ultrapassagem_pelotao` (0,4) e `custo_disputa_pelotao` (0,3): no pelotão passa-se mesmo com o mesmo ritmo e
  a briga custa pouco tempo
- `multiplicador_batida_pelotao` (6) e `carros_max_pelotao` (12): o "Big One" (batida grave com muitos carros)
- amarelas: toda batida chama safety car (`prob_amarela_acidente` 0,9; quebra `prob_amarela_quebra` 0,35), nunca VSC;
  `amarelas_detritos_por_corrida` (6, × (0,8·(1 + (`amarelas_oval_curto` − 1)·curto) + 0,4·pelotão), independe do nº
  de voltas); `amarelas_oval_curto` (2): no oval curto pleno, o dobro de amarelas; `voltas_amarela` [4, 7]
- `colisao_oval_curto` (2,5): oval curto é corrida de contato; `ultrapassagem_oval_curto` (0,7): no oval curto pleno a
  chance de ultrapassagem é multiplicada por 0,7 (pista estreita)
- `respeitar_tempo_maximo` (false): como na IndyCar/NASCAR, a corrida em oval cumpre a distância, sem o tempo máximo
  da categoria (true = vale o `tempo_maximo_min` também no oval)
- `efeito_largada` (0,3): largada lançada; `tentativas_relargada` (3), `piso_relargada` (0,6) e `alcance_relargada_s`
  (0,8): relargada em fila dupla – lado a lado, disputa quem está até 0,8 s do carro da frente

Medição (14 corridas por tipo): superspeedway ~48 trocas de liderança, ~10 carros colados no meio da corrida,
margem de ~1 s, ~6,5 amarelas, ~0,5 "Big One" por corrida; intermediário ~11 trocas, margem ~2 s, ~7 amarelas;
curto ~11–12 trocas, ~10 amarelas, mais abandonos por contato. Circuito misto sem mudança.
