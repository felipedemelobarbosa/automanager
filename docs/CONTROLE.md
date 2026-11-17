# AutoManager – controle do escopo

Legenda: ✅ feito conforme definido · 🟡 feito com **suposição minha** (confirmar) · ⏸ aguardando sua descrição · 🔌 feito, mas não integrado (por sua instrução)

## Decisões já tomadas

| Tema | Decisão |
|---|---|
| Linguagem / GUI | Python + Tkinter, tema Win9x próprio |
| Formato da DB | JSON |
| Escala de atributos e recursos | 0 a 100 |
| Importância carro × piloto | pesos que somam 100% |
| Organização dos arquivos | `database/<ano>/<categoria>_<ano>.json` (1 arquivo por categoria) |
| Ponderação atributo × pista | matriz no JSON da categoria (`ponderacao`) |
| Passagem do tempo | botão **Continuar** avança 1 semana |
| Equipe criada em categoria com desenvolvimento | tela simples de distribuição inicial (só na criação) |
| Integração do evento | sim: você joga o evento da sua categoria; as outras são simuladas em segundo plano |
| Ordem das categorias | `tier` no arquivo da categoria (1 = topo) + multiplicadores de mobilidade |
| Contratos | por temporadas **ou** por corridas, para pilotos, chassis, motores e patrocínios |

## 1. Database

| Item | Situação |
|---|---|
| Definições gerais da categoria (testes, desenvolvimento chassis/motor, equipes que desenvolvem motor, testes coletivos, orçamento médio, inflação, patrocínios, TV, importância carro/piloto) | ✅ |
| Probabilidade de surgimento na categoria | ✅ removida, conforme pedido (fica só em cada equipe) |
| Origem do motor: próprio / de outra equipe / de fabricante (marcado no motor e na categoria) | ✅ |
| Pilotos (dados, 11 atributos, contrato com valor/corrida, temporadas, situação) | ✅ |
| Chassis (atributos + contrato quando de terceiros) | ✅ |
| Motores (potência + fabricante + contrato) | ✅ |
| Equipes (ativa, recursos 0-100, chassis/motor próprio ou de terceiros, prob. fechamento/surgimento) | ✅ |
| Patrocinadores (preferência por nacionalidade ou posição; contrato em corridas ou temporadas; prob. fechamento/surgimento) | ✅ |
| Calendário (inclui tempo base treino/corrida, prob. de chuva, duração do pit stop, voltas, espécie corrida/teste coletivo) | ✅ |
| Pontuação, regras de pit stop, pneus (7 compostos), clima, formato do evento | ✅ no arquivo da categoria |
| Caixa inicial das equipes existentes quando a DB não informa (`caixa: null`) | 🟡 orçamento médio × (0,6 + 0,6 × recursos/100) |
| Nº de voltas da corrida | 🟡 fica em cada pista (`voltas_corrida`) |
| Validação automática dos arquivos ao carregar | ✅ (mensagem lista os erros) |

## 2. Motor do jogo

| Item | Situação |
|---|---|
| Menu inicial (novo jogo, carregar, opções, editor) | ✅ |
| Novo jogo: categoria única / múltiplas (busca automática por ano ou seleção manual) | ✅ |
| Carregar jogo: lista dos saves na pasta `saves/` | ✅ |
| Escolher equipe (com seleção prévia da categoria quando há várias) | ✅ |
| Criar equipe com orçamento aleatório de 0,7 a 1,2 do orçamento médio | ✅ |
| Recursos da equipe criada pelo usuário | 🟡 50 |
| Distribuição inicial de dinheiro no chassis/motor (equipe criada) | ✅ custo por ponto, base e máximo no JSON (`desenvolvimento_inicial`) |
| Página de gestão: carro, pilotos, finanças, próximo evento, notícias | ✅ |
| Menu Arquivo (abrir, salvar, salvar como, opções, fechar) | ✅ |
| **Opções** (conteúdo) | ⏸ |
| **Editor** | ✅ ver seção 6 |
| **Mercado** (pilotos, chassis, motor, patrocinadores) | ✅ ver seção 5 |
| **Desenvolvimento** (carro desta temporada / da próxima) | ✅ ver seção 4 |
| **Histórico** (temporada atual, anteriores, pontuação total) | ✅ ver seção 7 |
| Loop de contratos: equipes do PC sem pilotos fazem propostas (melhores pilotos possíveis com os recursos) | ✅ |
| Escolha do piloto: salário + perspectivas da equipe (pesos no JSON) | ✅ |
| Pilotos livres de todas as categorias carregadas no mesmo mercado | ✅ |
| Quem conta como "disponível" para a próxima temporada | 🟡 sem contrato **ou** com contrato terminando na temporada atual |
| Propostas para a próxima temporada começam na semana | 🟡 20 (`semana_inicio_propostas`) |
| Aviso nas notícias quando a SUA equipe tem vaga sem piloto | ✅ (aponta para Mercado > Pilotos) |
| Finanças de corrida: salários, contratos de chassis/motor, patrocínio, TV | ✅ |
| Patrocínio "por temporada" | 🟡 pago dividido pelas corridas |
| Fator da TV por posição no campeonato | ✅ posição atual; antes da 1ª corrida, a final do ano anterior |
| Inflação anual (média ± variação) sobre custos e receitas | ✅ |
| Fechamento/surgimento de equipes e patrocinadores; entrada/saída de corridas no calendário | ✅ na virada da temporada |
| Contratos de chassis/motor de terceiros que vencem | ✅ não há mais renovação automática: o PC escolhe no mercado, você contrata em Mercado |
| Novos patrocínios com equipes (patrocinador procurar equipe) | ✅ ver seção 5 |
| Notícias de resultados (todas as categorias) e campeões | ✅ |
| Temporada com 52 semanas | 🟡 |
| Pilotos envelhecem 1 ano por temporada | 🟡 sem aposentadoria nem geração de novos pilotos (não definido) |

## 3. Evento (integrado ao jogo; o protótipo isolado continua em `python evento_prototipo.py`)

| Item | Situação |
|---|---|
| Treinos livres (n sessões, limite por tempo ou voltas) | ✅ JSON `formato_evento` |
| Classificação: vários modelos (seção 8) | ✅ |
| Corrida por voltas com tempo máximo | ✅ |
| Tempo base separado para treino/classificação e corrida | ✅ por pista |
| Fórmula: base × aerodinâmica/chassis × motor × piloto × (acerto, pneu, combustível, ordens, evolução, aleatoriedade) | ✅ |
| Rating do piloto: ponderação dos atributos de piloto, chassis e motor × características da pista, por sessão e clima | ✅ |
| Tendência de melhora ao longo dos treinos (pista emborrachando + aprendizado) | ✅ |
| Clima seco / chuva leve / chuva forte, estável mas não estático, prob. por pista | ✅ |
| Pneus: super macio, macio, médio, duro, muito duro, chuva leve, chuva forte | ✅ |
| Pit stop obrigatório, reabastecimento e troca de pneus configuráveis | ✅ |
| Quebras e acidentes (aleatórios, tendendo a confiabilidade/concentração) | ✅ |
| Ultrapassagens (proporção de retas, ritmo, agressividade) e spread pela proporção retas/curvas | ✅ |
| Pontuação (posições, volta mais rápida, pole) | ✅ |
| Acerto inicial a cada sessão: aerodinâmica, câmbio, suspensão, freios, pneu, combustível | ✅ |
| Penalidade do acerto limitada para não gerar voltas irreais | ✅ máx. 1,8% (JSON) |
| Feedback do piloto sobre o acerto nos treinos (precisão pelo atributo "acerto do carro") | 🟡 extra para dar sentido ao acerto por sessão |
| Ordens: agressividade, uso do motor, uso do carro (−2 a +2) | ✅ |
| Estratégia automática liga/desliga + chamar ao box | ✅ |
| Não cumprir a parada obrigatória | ✅ sem penalidade de tempo: a consequência é o desgaste do pneu (furo/abandono a partir de `desgaste_quebra`) ou a falta de combustível |
| Regra de uso de compostos | ✅ removida: a estratégia sai só da degradação (seção 8) |
| Sem combustível (com reabastecimento) | 🟡 abandono |
| Só pilotos principais correm | 🟡 |
| Integração do evento com o jogo (calendário, campeonato, finanças, notícias) | ✅ |
| Botão "Simular evento inteiro" na tela do evento | 🟡 extra, para não precisar jogar sessão a sessão |
| Janela maximizada durante o evento | 🟡 |

## 4. Desenvolvimento

| Item | Situação |
|---|---|
| Só disponível se a categoria permitir (e a parte for própria da equipe) | ✅ |
| Dividido em carro desta temporada e carro da próxima | ✅ |
| Dinheiro × pontos: custo fixo até `limite_custo_fixo`, depois progressivo (`escala_progressiva`) | ✅ JSON `desenvolvimento` |
| Evolução vale na hora | ✅ |
| Carro da próxima temporada: projeto novo parte do zero | ✅ |
| Manutenção do carro atual com perda de 30% em cada atributo (configurável: `perda_manutencao`) | ✅ |
| Próxima temporada: OU manutenção (carro atual no fim da temporada com −30%, sem investimento) OU projeto novo do zero (com investimento) | ✅ corrigido |
| Voltar do projeto novo para a manutenção descarta o que foi investido | ✅ |
| Padrão quando não se escolhe nada | 🟡 manutenção |
| Equipes do PC desenvolvem com a verba planejada pela economia (receita − despesas fixas ± caixa) e escolhem entre projeto novo e manutenção pelo melhor resultado esperado | ✅ |
| Clientes de um motor de equipe recebem as evoluções desse motor | 🟡 |

## 5. Mercado

| Item | Situação |
|---|---|
| Proposta do usuário: salário/corrida, duração, principal/testes, agora ou próxima temporada; resposta na semana seguinte | ✅ |
| "Agora" só com vaga na equipe e piloto sem contrato ativo | ✅ |
| Proposta do usuário disputa com as do PC; recusa ou cancelamento vira notícia | ✅ |
| Movimentação entre categorias por `tier` + multiplicadores (`mobilidade`: de tier inferior, de tier superior, mesmo tier) | ✅ |
| Como o multiplicador age | 🟡 chance de o piloto entrar no radar das equipes de destino e peso na escolha do piloto |
| Contratar piloto com contrato vigente | ✅ pagando a multa à equipe atual (seção 8) |
| Contratos por temporadas ou por corridas (pilotos, chassis, motores, patrocínios) | ✅ |
| Chassis/motor de terceiros: sem limite de clientes; PC escolhe melhor custo-benefício que cabe no caixa | ✅ |
| Exclusividade de motor (`exclusividade: {exclusivo, equipe}` com o nome da equipe) | ✅ outras equipes têm o fornecimento recusado |
| Trocar chassis/motor no meio do ano | ✅ rescindindo o contrato atual com multa |
| Patrocinadores procuram equipes: índice carro × pilotos com aleatoriedade; após a 1ª corrida inclui o desempenho (`peso_desempenho`) | ✅ |
| Escolha da equipe pelo patrocinador | 🟡 sorteio ponderado pelo índice; cada patrocínio que a equipe já tem reduz um pouco a atratividade |
| Valor oferecido | 🟡 `valor_base` do patrocinador × índice da equipe |
| Ofertas à sua equipe ficam em Mercado > Patrocinadores (aceitar/recusar), validade de 4 semanas | 🟡 |

## 6. Editor

| Item | Situação |
|---|---|
| Janela Win9x com aba por entidade, lista à esquerda e formulário à direita | ✅ |
| Aba Categoria: árvore editável de todas as definições (aceita campos novos) | ✅ |
| Validação ao salvar, novo arquivo (copiando regras de outro), duplicar para outro ano | ✅ |
| Importar da Wikipedia (inglês), página da temporada: equipes, pilotos (com nacionalidade), chassis, motores, calendário, pontuação | ✅ testado com F1 2005 e 2023 |
| Atributos estimados pela classificação final da temporada | ✅ |
| Dados de pista, idade dos pilotos e patrocinadores | 🟡 valores padrão para ajustar no editor |
| Regras da categoria importada | 🟡 copiadas de um arquivo modelo escolhido na importação |
| Pilotos com mais corridas na equipe viram principais; os demais, de teste (se a categoria tiver) ou livres | 🟡 |
| Outras categorias além da F1 | ⏸ o parser procura as mesmas tabelas; páginas com outro formato podem precisar de ajuste |

## 7. Histórico

| Item | Situação |
|---|---|
| Temporada atual de todas as categorias: pilotos, equipes, resultado de cada corrida | ✅ |
| Temporadas anteriores: classificação final, corridas, campeões, finanças da sua equipe | ✅ |
| Pontuação total de todas as temporadas (pilotos e equipes, títulos, vitórias, pódios), com filtro por categoria e total geral | ✅ |

## 8. Rodada atual

| Item | Situação |
|---|---|
| Salvar o jogo no meio de um evento (botão "Salvar jogo" na tela do evento; ao carregar, continua do mesmo ponto, com o mesmo resultado) | ✅ |
| **Pneus**: ritmo, degradação linear, aquecimento, sensibilidade térmica, vida e cliff por composto; pista (desgaste), carro (pneus), piloto (consistência) e ordens multiplicam a degradação | ✅ |
| Estratégia: o PC (e a estratégia automática) compara planos de 0 a 3 paradas com todas as combinações de compostos | ✅ |
| Valores de pneus | 🟡 estimativas de referência (não são dados oficiais), ajustáveis no JSON |
| **Classificação** em vários modelos: por tempo/voltas com ou sem eliminação, com uma ou várias fases; grupos intercalados; volta única (melhor volta ou média); corrida classificatória; grid pelo campeonato (normal ou invertido); grid invertido opcional na corrida; etapas combinadas | ✅ |
| **Carreira**: `ano_pico`, `potencial` e `ano_aposentadoria` (opcionais; o jogo define os que faltarem), curva até o pico e queda depois | ✅ |
| Aposentadoria antecipada | ✅ após 2 temporadas sem contrato (a partir de 24 anos) |
| Novos pilotos: `novos_pilotos_<ano>.json` → subida dos tiers inferiores → fictícios (`database/nomes.json`) no tier mais baixo | ✅ |
| Quantidade de fictícios | ✅ aposentados + margem de 2 por temporada |
| **Saída de contrato**: multa = `fator_multa` (0,5) × valor por corrida × corridas restantes, para pilotos, chassis e motores; você e o PC | ✅ |
| PC: compra piloto de outra equipe só se ele for ≥ 5 pontos melhor que o melhor livre e a multa couber em 8% do caixa | 🟡 |
| PC: dispensa o pior piloto se houver livre ≥ 8 pontos melhor e a multa couber em 5% do caixa | 🟡 |
| **Economia**: verba de desenvolvimento do PC planejada (receita prevista − despesas fixas, ajustada pelo caixa acima/abaixo da reserva) | ✅ |
| Calibragem | 🟡 custos de desenvolvimento, TV e patrocínios ajustados para o caixa ficar estável e as equipes subirem ou caírem de nível conforme a situação financeira (simulado por 8 temporadas) |
| Empréstimos com juros (Finanças > Finanças e empréstimos), parcelas por corrida, quitação antecipada; o PC recorre a empréstimo quando o caixa fica negativo | ✅ |
| Falência após N semanas com caixa negativo e sem crédito (PC: deixa a categoria; você: fim de jogo) | ✅ |
| Lista de equipes que podem surgir (`novas_equipes` na categoria e `ano_surgimento` na equipe; sem ano = sorteio) | ✅ |
| Equipe que surge sem carro cadastrado | 🟡 constrói o carro do zero com parte do orçamento |
| Todas as equipes precisam de patrocínio | ✅ prioridade absoluta para quem não tem nenhum + patrocinadores fictícios quando faltam |
| Inflação no valor dos patrocínios | ✅ |
| **Importador** genérico (qualquer série/época): sinônimos de colunas, monomarca, inscritos particulares, carros por equipe, pontuação (corrida principal, pole, volta mais rápida), busca de página | ✅ testado com F1 1958/1988/2005/2023, F2, IndyCar, Fórmula E e BTCC |
| **Editor**: formulários por seção com explicação em cada campo, referências pelo nome, IDs automáticos (renomear atualiza as referências), barras deslizantes nos atributos, registro descrito em frase, busca e filtro nas listas, erros marcados no campo e no registro, importação em 3 etapas com prévia, árvore no modo avançado | ✅ |
| **Opções** | ⏸ deixar para o final (pedido seu) |

## 9. Rodada atual

| Item | Situação |
|---|---|
| Semana atual em destaque na tela principal (quadro "SEMANA x / 52" + linha do tempo com corridas, testes e a semana atual) | ✅ |
| Resultados dos testes coletivos: simulados (dias de pista), notícia com os mais rápidos e o resultado da sua equipe, aba "Testes coletivos" no Histórico | ✅ |
| Formato do teste coletivo (`formato_teste_coletivo`: dias e minutos por dia; padrão 2 × 240) | 🟡 Fórmula Alfa: 3 dias de 4 horas |
| Teste coletivo jogável | ✅ na semana do teste o jogo pergunta se você quer participar na tela do evento (se não, sua equipe testa no modo automático) |
| Desenvolvimento: manutenção sem investimento OU projeto do zero | ✅ |
| Recalibragem dos custos de desenvolvimento | 🟡 20 mil/ponto (chassis) e 80 mil/ponto (motor) até 55, encarecendo rápido acima; carros de 65 a 89 e caixa estável em 8 temporadas simuladas |


## 10. Rodada atual

| Item | Situação |
|---|---|
| Estabilidade no mercado de pilotos | ✅ contrato que começou na temporada não pode ser comprado nem rescindido pelo PC até a seguinte (vale também para as suas propostas de compra); o PC só compra contratos para a próxima temporada, com critério mais exigente (8 pontos melhor que o melhor livre) e menor frequência |
| Resultado em 4 temporadas simuladas | ✅ nenhum piloto assinou com duas equipes diferentes na mesma temporada |
| Participar do teste coletivo | ✅ |
| Chamar ao box nos treinos livres, na classificação e no teste coletivo para mudar o acerto e o pneu | ✅ o piloto termina a volta, faz a volta de entrada e espera; o acerto fica liberado enquanto ele está parado; "Voltar à pista" aplica o novo acerto |
| Tempo correndo com o carro parado no box | ✅ confirmado (use "Pausar" para ajustar com calma) |
| Box na classificação | ✅ disponível em todos os modelos com saídas livres (por tempo ou voltas, com ou sem eliminação, uma ou várias partes, grupos); só a volta única não tem box (confirmado) |
| Pilotos homônimos entre categorias na DB de exemplo | ✅ corrigido no gerador |

## 11. Rodada atual

| Item | Situação |
|---|---|
| Cores das equipes | ✅ `cor` e `cor_secundaria` (#RRGGBB) na equipe; sem cor, o jogo usa uma cor fixa derivada do ID |
| Onde aparecem | ✅ ficha colorida nas tabelas (cronometragem, histórico, mercado de pilotos, escolha de equipe, editor) e faixa vertical ao lado do nome da sua equipe (gestão e evento) |
| Editor | ✅ campos "Cor principal" e "Cor secundária" com botão Escolher (seletor de cores) |
| Criar equipe | ✅ escolha das duas cores no diálogo (sugere uma cor ainda não usada na categoria) |
| Importador | ✅ cores conhecidas pelo nome (Ferrari, McLaren, Williams…) ou a próxima cor livre da paleta |
| DB de exemplo | ✅ cores definidas para todas as equipes |

## 12. Rodada atual

| Item | Situação |
|---|---|
| Imagens de pilotos, logotipos de equipes e pistas | ✅ em `database/imagens/` (PNG); campos `imagem`/`logotipo` + `wikipedia` (artigo) |
| Busca na Wikipedia | ✅ no editor: na importação (opção marcada por padrão, com barra de progresso), botão "Buscar na Wikipedia" em cada piloto/equipe/pista e "Buscar imagens..." para o arquivo todo; o jogo só usa arquivos locais (confirmado) |
| Biblioteca Pillow | ✅ usada para converter/redimensionar (confirmado); sem ela o jogo funciona, só com PNG |
| Onde aparecem | ✅ foto do piloto na gestão (piloto selecionado) e no mercado; logotipo no topo da gestão e no painel "Sua equipe" do evento; pista no "Próximo evento" e no painel "Pista" do evento; pré-visualização no editor |
| Aposentadoria por ano ou por idade | ✅ editor: "(sorteio)", "por ano" ou "por idade"; a database guarda o que foi escolhido (`ano_aposentadoria` ou `idade_aposentadoria`) |
| Corridas definidas no contrato por corridas | ✅ misto de revezamento com lista opcional (confirmado): com lista, o piloto corre só nelas e o contrato termina após a última; sem lista, comportamento anterior; validação impede mais escalados que carros numa corrida |
| Importador preenche as corridas definidas | ✅ pela coluna "Rounds" da Wikipedia: quem correu tudo fica sem lista; quem correu parte recebe a lista das etapas (ex.: F1 2023 AlphaTauri – de Vries 1–10, Ricciardo 11–12 e 18–22, Lawson 13–17). Etapa com pilotos demais: sai quem não continua na etapa seguinte. Piloto em duas equipes fica onde fez mais etapas |
| Pilotos fictícios / database de exemplo | ⚠ sem imagens (são fictícios); aparecem como "sem foto" |

## 13. Rodada atual

| Item | Situação |
|---|---|
| Logotipos de chassis e motores | ✅ campo `logotipo` (+ `wikipedia`); importador usa o artigo da marca (construtor / fabricante do motor) |
| Onde aparecem os logotipos de chassis/motor | ✅ gestão (painel Carro), mercado de chassis/motor (lista e detalhe) e evento (linha chassis/motor do painel do piloto) – escolhido |
| Bandeiras | ✅ 104 países já vêm no jogo (`database/imagens/bandeiras`); o editor baixa as que faltarem – escolhido |
| Bandeiras em todo o jogo | ✅ tabelas: ficha com cor da equipe + bandeira (escolhido): cronometragem, histórico (pilotos, equipes, corridas, testes, campeões, total), mercado (pilotos, chassis/motor, patrocinadores), escolha de equipe, pilotos da gestão, editor (todas as abas e prévia da importação). Rótulos: piloto no painel do evento, chassis/motor na gestão, pista no evento e no próximo evento, detalhes da equipe na escolha |
| Imagens de pasta local | ✅ os dois (escolhido): "Escolher arquivo..." em cada registro e "Imagens de pasta..." (associação pelo nome do arquivo) |

## 14. Rodada atual

| Item | Situação |
|---|---|
| Retas/curvas calculadas pelo mapa da pista | ✅ botão "Calcular retas e curvas pelo mapa da pista..." no calendário do editor (escolhido: só o botão), com mapa colorido e percentuais para confirmar antes de aplicar |
| Fonte do mapa | ✅ Wikipedia (artigo do circuito) ou imagem do computador / imagem da pista já cadastrada; OpenStreetMap descartado (pedido) |
| Escala | ✅ comprimento do quadro do artigo (length_km / length_mi) ou digitado |
| Critério | ✅ os dois (pedido): pelo raio (m) e pela velocidade estimada (km/h); a tela mostra os dois e aplica o escolhido; limites e aderência em Categoria > Mapa da pista e ajustáveis na própria tela |
| Reconhecimento automático | ⚠ funciona na maioria dos mapas (testados: Monza, Bahrein, Silverstone, Interlagos); falha em mapas com muitas linhas sobrepostas ou viadutos (Mônaco, Suzuka). Nesses casos: marcar o traçado clicando sobre o mapa (spline fechada) |
| Arquivos SVG do computador | ⚠ não suportados diretamente (o Tkinter/Pillow não desenham SVG): exporte como PNG. Os SVG da Wikipedia já chegam desenhados em PNG |

## 15. Rodada atual

| Item | Situação |
|---|---|
| Modo multijogador (comissário + jogadores por arquivos) | ✅ modo de jogo separado no menu inicial |
| Turno | ✅ 1 semana (escolhido) |
| O que o jogador decide | ✅ propostas a pilotos, rescisões, chassis/motor, patrocínios, empréstimos, desenvolvimento e o plano do evento |
| Plano do evento | ✅ completo (escolhido): por piloto, acerto, pneu, ordens para treinos, classificação e corrida; na corrida também combustível e paradas (automático ou stints). Se o clima pedir outro tipo de pneu, a equipe troca e assume |
| Arquivo sem ordens | ✅ o comissário escolhe a política (escolhido "as três"): IA joga o turno / repetir últimas ordens (desenvolvimento + plano) / bloquear (ou pular o jogador) |
| Segurança | ✅ senha por jogador (PBKDF2), ordens assinadas (HMAC); arquivo dos jogadores sem as chaves e sem as ordens dos outros |
| Mercado entre jogadores | ⚠ suposição: ações aplicadas em ordem sorteada a cada semana; disputa por piloto decidida pelas regras normais (salário × perspectivas) |
| Idiomas | ✅ inglês, português e espanhol no menu inicial; tudo o que a interface mostra (menus, telas, notícias, mensagens, editor, importador), além de países, pneus, clima e sessões. Nomes da database não são traduzidos |
| Notícias no multijogador | ✅ guardadas em português e traduzidas na hora de mostrar (cada jogador vê no próprio idioma) |

## 16. Rodada atual – modelo de volta e corrida mais realista

| Item | Situação |
|---|---|
| Dispersão por volta unilateral (consistência) | ✅ k·(1,5 − 0,316·√(cons/5))·acaso, só piora a volta; antes o piloto inconsistente era 0,12 s mais rápido no melhor de 3 voltas, agora é 0,22 s mais lento (0,32 s na média) |
| Forma por evento | ✅ |
| Chuva cúbica | ✅ diferença piloto/carro ruim (30) x bom (90): 1,5 s na chuva leve, 3,6 s na forte |
| Tráfego e limites de pista na classificação; menos erros na classificação | ✅ ~10 incidentes por sessão |
| Corrida: ar sujo, ultrapassagem pelo ritmo de fundo, custo da briga, bandeira azul | ✅ ~27 ultrapassagens em pista mista, ~9 em pista de rua |
| Dificuldade amplia sobretudo o piloto (pista de rua +10%) | ✅ |
| Dano persistente e reparo no box | ✅ |
| Safety car / VSC | ✅ ~0,4 por corrida em pista mista, ~1,0 em pista de rua; parada mais barata; equipes aproveitam |
| Emborrachamento pelas voltas dadas; chuva lava | ✅ |
| Acerto por componente (peso conforme a pista) | ✅ |
| Desgaste do motor, cota e punição de grid | ✅ cota desligada por padrão (vale quando a categoria define) |
| Lastro de sucesso | ✅ desligado por padrão (vale quando a categoria define) |
| Pole vence | ⚠ 68% em pista mista com a database de exemplo, que tem um carro/piloto dominante (vence 60%); era 23% |


## 17. Rodada atual – testes de integridade, evolução e regras de pneus

| Item | Situação |
|---|---|
| Mistura de atributos na corrida (corrida a corrida) | ✅ `tools/analise_atributos.py [n] [mista\|rua\|chuva]`: cada atributo de piloto, chassis e motor em 30 x 90, mesmas sementes. Maiores efeitos: seco – pneus do chassis, potência, condução, consistência; rua – pneus, consistência, potência, aceleração, freio; chuva – chuva do piloto (+7 posições), consistência, chuva do chassis |
| Largada sem efeito | ✅ corrigido: a 1ª volta usa a diferença da largada nas disputas e permite até 3 tentativas |
| Classificação (piloto/chassis) | ⚠ ganha 5–6 posições no grid e pouco no final para o piloto analisado: os carros mais rápidos de trás passam sobretudo no ciclo de paradas (ar limpo/undercut), não na pista. No pelotão todo, cada posição de grid vale ~0,55 posição no final (com o mesmo ritmo) |
| Evolução em várias temporadas | ✅ `tools/analise_temporadas.py [n]`: curva de idade, aposentadorias, estreias, chassis/motor por categoria, caixa, campeões |
| Variáveis entre eventos e constantes | ✅ `tests/test_entre_eventos.py`: forma, uso/cota de motor (zera na virada), punição de grid, lastro, contratos por corrida (só diminuem em corrida), pontos, caixa = lançamentos, constantes da categoria inalteradas, o que zera a cada evento |
| Integridade do arquivo de ordens | ✅ formato v2 só com o necessário (ações, planos da semana normalizados, resumo do resultado), checksum SHA-256 + assinatura HMAC, campos extras recusados, reprodução das ações no jogo do comissário com conferência do resumo; checksum do arquivo da liga (`tests/test_integridade.py`) |
| Multijogador em várias temporadas | ✅ 2 temporadas, 3 jogadores com ações e planos aleatórios toda semana, tudo por arquivos em disco |
| Troca de pneus conforme a categoria | ✅ `troca_de_pneus: false` = só troca se o clima obrigar; `compostos_disponiveis` vale para IA, box manual e plano do multijogador (`tests/test_pneus_box.py`) |
| Box manual a qualquer momento (jogo individual) | ✅ qualquer composto disponível (incluindo chuva leve/intermediário e chuva pesada); no multijogador vale o plano de stints |

## 18. Rodada atual – estratégia e ultrapassagem

| Item | Situação |
|---|---|
| Estratégia variada | ✅ o motor calcula a melhor estratégia; as equipes do PC sorteiam entre as opções perto da ótima (mais recursos = mais perto) e variam o tamanho dos stints (`variacao_estrategia_s` 6 s, `variacao_stint` 0,1). Ex.: 14–20 planos diferentes por corrida, maioria de 1 parada, alguns de 2. Estratégia automática do jogador = a ótima |
| Troca de pneus | ✅ cada parada coloca pneus novos (mesmo composto ou outro, conforme a estratégia); só a categoria com `troca_de_pneus: false` mantém os pneus (exceto troca forçada seco/chuva) |
| Ultrapassagem pela pista | ✅ fator = (retas/0,4)² (× 0,6 em pista de rua); diferença de ritmo pesa ao quadrado. Ultrapassagens/corrida: rua com 15% de retas ~2; mistas de 30–35% ~6–8; 40–60% ~11–17; oval ~42 (antes: 30% já tinha 10–13 e 60% só 14) |
| Regra dos dois compostos secos | ✅ opcional (`regras_pitstop.dois_compostos_secos`); desclassificação ou segundos de penalidade; IA cumpre; aviso no plano do multijogador; furo também conta o composto novo |
| Motores caindo com o tempo | ✅ (b) motores de fabricantes evoluem a cada temporada (verba calibrada × receita de fornecimento) e (c) calibração automática dos custos no início do jogo + correção suave por temporada; `tools/analise_temporadas.py` antes/depois |
| Verba de desenvolvimento perdida | ✅ corrigido: a verba semanal que não dava para um ponto (caro) se perdia; agora acumula na temporada |
| Teto de salário da IA | ✅ base = maior entre caixa e receita prevista (com a verba de desenvolvimento gasta, o caixa fica perto da reserva) |
| 3 pilotos principais numa equipe | ✅ corrigido: substituto contratado no meio da temporada com a próxima já fechada assina só até o fim desta |

## 19. Rodada atual – variedade e calendário

| Item | Situação |
|---|---|
| Corridas repetidas? | ✅ testado (`tests/test_variedade.py`): 0 resultados iguais em 1.338 pares, logs com 0,1% em comum |
| Carreiras iguais em todo jogo novo | ✅ corrigido: cada jogo novo tem semente própria (`st["semente"]`); `novo_jogo(..., semente=n)` reproduz um jogo |
| Mesma pista duas vezes na temporada | ✅ corrigido: corrida de reserva não entra se a pista já está no calendário; as reservas da Fórmula Alfa de exemplo ganharam pistas próprias (Montval, Bahía Serena) |
| Clima | ✅ corrigido: `prob_chuva` = fração das sessões com chuva; mudanças um passo por vez com equilíbrio garantido (corrida começa molhada: 8% → 10%, 30% → 35%, antes 18% e 50%) |
| Oval com chuva | ✅ bandeira vermelha e sessão suspensa até secar (relógio parado; início adiado se já chove; corrida relarga atrás do safety car) – `tests/test_oval_chuva.py` |
| Bandeira vermelha: opções da categoria | ✅ `regras.bandeira_vermelha`: relógio parado ou correndo durante a espera; limite de espera para treinos/classificação e para a corrida (encerra a sessão; corrida termina ou é cancelada sem pontos) |
| Batidas graves | ✅ vários carros abandonam; bandeira vermelha (relargada) ou fim antecipado da sessão; chances na categoria (`regras.batida_grave`) – `tests/test_batidas.py` |
| Pontuação de corrida interrompida | ✅ integral a partir de 50% (configurável); abaixo, metade ou proporcional (opção na categoria) |
| Lesões e mortes | ✅ chances pequenas na categoria; lesão = corridas fora + perda de atributos; PC substitui sozinho, jogador (individual e multijogador) precisa contratar ou o carro não corre. Padrões: em 10 temporadas, ~29 batidas graves, 8 lesões |
| Substituto na equipe do jogador | ✅ contrato vale; quando o titular volta, alerta para o jogador decidir quem dispensar (até lá correm os contratos mais antigos). Equipes do PC continuam com substituto automático |
| Carreiras e movimentação | ✅ `tools/analise_carreiras.py [temporadas] [--gama]`: evolução por idade, estreias, aposentadorias, nível por categoria e transferências (subir/descer de tier, mesmo tier). ✅ nível ancorado na database: tier mais alto estável (71–75 em 10–15 temporadas; antes subia a 78–79); tier 2 se estabiliza em 64–66 pelo mercado |
| Retorno de pilotos | ✅ aposentados podem voltar (chance pequena, `mobilidade.retorno`; ~0,5–0,7 por temporada); quem desce de categoria volta pelo mercado |
| Idade dos pilotos por categoria | ✅ `regras.idade_pilotos`: idade máxima (limite rígido) e preferência por jovens nas categorias de base (idade média dos titulares da Beta: ~26 → ~21–22) |
| Corridas em oval | ✅ pelotão/vácuo no superspeedway, intermediário, oval curto de contato; amarelas (sem VSC), detritos, Big One, largada lançada, relargada em fila dupla – `simulacao.oval`, `tests/test_ovais.py` |
| Oval: trocas de liderança e amarelas | ✅ relargada lado a lado (alcance 0,8 s), amarelas por corrida (6): superspeedway ~48 trocas / 6,5 amarelas, intermediário ~11 / 7, curto ~11–12 / 10. Corrigido: piloto podia 'passar' o mesmo carro duas vezes na mesma volta. Oval cumpre a distância (opção `respeitar_tempo_maximo`) |
| Multijogador: equipe criada do zero | ✅ o comissário só reserva a vaga ("Equipe nova – o jogador cria ao abrir a liga"); o jogador, ao abrir a liga, cria a equipe (nome, país, cores) e faz o desenvolvimento inicial ou contrata as peças, conforme a categoria – tudo nas ordens dele (`criar_equipe`, `dev_inicial`), reproduzido e conferido no comissário (orçamento sorteado com semente fixa da liga + jogador). Sem ordens, a vaga espera; criada a equipe, a IA faz o desenvolvimento inicial se o jogador faltar – `tests/test_mp_equipe_nova.py` |
| Ordens identificadas pela equipe | ✅ arquivo de ordens (versão 3) leva `equipe` {id, nome}, conferida no comissário; nome do arquivo: liga_ano_semana_jogador_equipe.ordens.json; a lista de importação mostra jogador (equipe) |
| Total do contrato | ✅ propostas a pilotos e contratos de chassis/motor mostram o total (valor/corrida × corridas cobertas), atualizado ao mudar valor, duração, unidade e início |
| Pretensão do piloto escondida | ✅ o Mercado mostra uma faixa estimada (erro de até ±20%, fixo por piloto/equipe/temporada); o valor real só pesa na resposta do piloto. Chassis/motor: o valor mostrado é o preço de tabela do fornecedor (sem negociação), que é o que se paga |
| Feedback do acerto | ✅ também na classificação (o acerto vale da 1ª sessão até a corrida – conferido em teste); frase do piloto traduzida por inteiro (inglês e espanhol). Painel de feedback na tela do evento (aprovado): acompanha a aba do piloto; nota do setup (estrelas, pela leitura do piloto) e, por ajuste, régua com o acerto testado e seta na direção pedida (curta = um pouco, longa = bem); frase do piloto |
| Traduções (inglês e espanhol) | ✅ varredura do motor (todos os formatos de classificação, chuva, oval, batidas, várias temporadas, multijogador) e das telas (menu, novo jogo, escolha de equipe, gestão, mercado, desenvolvimento, finanças, histórico, evento, editor, multijogador): sobram só nomes da database (pistas, equipes, patrocinadores), que não se traduzem. Corrigido: linhas com [V n]/[h:mm:ss]/[ano Ssemana]; listas longas ("Físico −5, Concentração −4, …"); rótulos com dois-pontos; títulos de grupo com espaços; modelos com valores grudados (contratações, grid pelo campeonato, jovens pilotos); fim de fase, progresso da sessão, notícia do teste, pódio (P2/P3 em inglês), lesão com nomes dos atributos, resumo do editor, ficha da equipe na escolha, "temp.." duplicado |
| Peças de fornecedor mudam a cada ano | ✅ `regras.evolucao_fornecedores`: atualização de −2 a +2 por atributo; modelo novo (−3 a +8, ~1 a cada 4 anos) com o ano trocado no nome; volta ao nível da database; preço acompanha – `tests/test_regulamento.py` |
| Negociação de chassis/motor | ✅ opção `regras.negociacao_partes` (padrão: preço de tabela). Pedido escondido (tabela ±15%), oferta respondida na semana seguinte; PC negocia; vai nas ordens do multijogador (e entra na impressão da equipe conferida pelo comissário) |
| Regulamento ao longo das temporadas | ✅ `categoria.regulamento`: grande mudança (perda extra do chassis + importância do carro sobe e volta aos poucos), limite de desenvolvimento (congelado ou pontos por temporada; carro passa sem perda e sem projeto novo), ajuste da importância; anúncio na semana 30; notícias, Histórico > Regulamento, tela de desenvolvimento; calibração automática de custos não reage durante o limite. Desligado em temporadas importadas, ligado na database de exemplo |
| Multijogador: simulação de liga | ✅ 6 jogadores (2 categorias, uma equipe criada pelo jogador, um que nunca manda ordens), 60 semanas por arquivos (liga exportada → jogadores entram → ordens salvas → comissário importa e roda): 300 arquivos importados sem divergência; arquivo adulterado e arquivo da semana anterior recusados; disputa de dois jogadores pelo mesmo piloto; negociação de motor com recusas até a oferta cobrir o pedido; regulamento anunciado e aplicado na virada |
| Chassis comprado em categoria com desenvolvimento (1b) | ✅ `regras.fontes_de_chassis_permitidas` + `clientes_por_chassis` (2): escolher desenvolver ou comprar no desenvolvimento inicial e para a próxima temporada; cliente pode voltar a fazer o próprio (do zero); vendedor continua fazendo o chassis enquanto tem clientes; IA escolhe comparando próxima temporada com próxima temporada; sem chassis à venda, a IA constrói o próprio. Preços de chassis de equipe definidos em pontos fixos (iguais no jogador e no comissário). Corrigido no i18n: texto de várias linhas perdia o ponto final da última linha antes da tradução por linha – `tests/test_regulamento.py` (TestChassisCliente) |
| Receita de quem vende chassis/motor | ✅ a equipe dona recebe por corrida o que o cliente paga ("Venda de chassis/motor" nas finanças; entra na receita prevista do PC e na calibração). `clientes_por_chassis: 2` escrito nos arquivos das categorias de exemplo |
