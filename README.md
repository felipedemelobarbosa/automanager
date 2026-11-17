# AutoManager

Jogo manager simples de automobilismo, com interface no estilo Windows 9x (Python + Tkinter).

## Requisitos

- Python 3.10 ou superior, com Tkinter (no Windows já vem junto; no Linux: `sudo apt install python3-tk`)
- Pillow (`pip install pillow`) para as imagens (fotos, logotipos e pistas). Sem ela o jogo funciona, mas só
  mostra imagens PNG sem redimensionar e o editor não converte as fotos da Wikipedia (que vêm em JPG)

## Como executar

```bash
python main.py               # o jogo
python evento_prototipo.py   # protótipo da tela de evento (isolado do jogo)
python -m unittest discover tests
```

O importador da Wikipedia (Editor > Importar da Wikipedia) e a busca de imagens precisam de acesso à internet.
O jogo em si só usa arquivos locais.

## Instaladores (.exe, .dmg, .deb)

Gerados no GitHub Actions (`.github/workflows/build.yml`), com PyInstaller, nas máquinas Windows, macOS e Linux
do GitHub:

- Manualmente: aba **Actions** > **Build** > **Run workflow**. Ao terminar, os arquivos ficam em **Artifacts**, na
  página da execução.
- Criando uma tag `v*` (ex.: `v0.1` em Releases > Draft a new release): além disso, publica uma Release com os três
  arquivos.

Os testes rodam antes; se falharem, nada é gerado. No programa instalado, jogos salvos, ligas, configurações, a
database editada e as imagens baixadas ficam na pasta do usuário (Windows: `%APPDATA%\AutoManager`; macOS:
`~/Library/Application Support/AutoManager`; Linux: `~/.local/share/automanager`); a database que vem com o jogo
é copiada para lá na 1ª execução (numa versão nova, só os arquivos novos). Rodando pelo código (`python main.py`),
tudo continua na pasta do jogo. Os programas não são assinados: o Windows (SmartScreen) e o macOS (Gatekeeper)
avisam na 1ª vez (no macOS: botão direito no app > Abrir). O `.dmg` é para Macs com chip Apple (M1 ou mais novo).

## Idiomas

Português, inglês e espanhol: escolha no menu inicial ("Idioma / Language / Idioma"). A escolha fica em
`config.json`. As traduções estão em `lang/en.json` e `lang/es.json` ({"texto em português": "tradução"});
mensagens com valores usam modelos (`"{0} vence o {1}."`). Nomes da database (pilotos, equipes, pistas) não
são traduzidos; países, pneus, clima e sessões são.

## Multijogador (por arquivos)

Um **comissário** e vários **jogadores**; cada semana é um turno.

1. Comissário: menu inicial > *Multijogador – comissário* > *Criar uma liga nova*: escolhe as categorias,
   cadastra os jogadores (nome, equipe, senha) e a política para quem não mandar o arquivo (IA joga o turno /
   repetir as últimas ordens / bloquear o turno). São gravados, em `ligas/<nome>/`, o arquivo do comissário
   (`…_comissario.json`, não distribuir) e o arquivo para os jogadores (`…_<ano>_sNN_liga.json`).
2. Jogador: *Multijogador – jogador* > abre o arquivo da liga > escolhe o nome e digita a senha. Toma as
   decisões da semana como no jogo de um jogador (propostas a pilotos, chassis/motor, patrocínios, empréstimos,
   desenvolvimento) e, se houver evento, define o *Plano do evento* (acerto, pneus, ordens e paradas por piloto,
   para treinos, classificação e corrida). *Salvar ordens* gera o arquivo assinado com a senha para mandar ao
   comissário (pode salvar de novo; vale o último importado).
3. Comissário: *Importar ordens...*, eventualmente *Pular jogador*, e *Rodar semana*. A liga é salva e o novo
   arquivo para os jogadores é gerado na pasta da liga.

Ordens alteradas, de outra liga/semana ou de outro jogador são recusadas. A ordem em que os jogadores agem no
mercado é sorteada a cada semana. Equipes sem jogador ficam com a IA.

## Estrutura

```
main.py                     jogo
evento_prototipo.py         protótipo do evento
database/<ano>/*.json       categorias (uma por arquivo: <categoria>_<ano>.json)
database/<ano>/novos_pilotos_<ano>.json   pilotos que entram no mercado naquele ano (opcional)
database/nomes.json         nomes para pilotos e patrocinadores fictícios
database/imagens/           fotos de pilotos, logotipos (equipes, chassis, motores), pistas e bandeiras (PNG)
lang/                       traduções (en, es)
ligas/                      ligas multijogador (criadas pelo comissário)
saves/                      jogos salvos
docs/CONTROLE.md            o que já está definido, feito, suposto ou pendente
tests/                      testes automáticos (inclui uma página da Wikipedia salva para o importador)
docs/DATABASE.md            referência de todos os campos da database
automanager/
  db.py                     leitura, busca e validação da database
  state.py                  estado do jogo, criação de equipe, save/load
  routines.py               rotinas semanais (corridas, finanças, nova temporada)
  mercado.py                pilotos (tiers), chassis/motores, patrocinadores
  desenvolvimento.py        carro desta temporada / da próxima, IA
  campeonato.py             resultados, classificação e histórico
  carreira.py               curva de habilidades, aposentadoria e novos pilotos
  imagens.py                leitura das imagens (database/imagens) e importação de pasta local
  multiplayer.py            liga, senhas, arquivos de ordens, rodar semana, políticas de ausência
  acoes.py                  ações de gestão (gravadas no arquivo de ordens do jogador)
  i18n.py                   idiomas (tradução de tudo o que a interface mostra)
  paises.py                 nomes de países (inglês/português) e bandeiras
  economia.py               orçamento do PC, empréstimos e falência
  contratos.py              contratos por temporadas ou por corridas
  editor/                   leitura de tabelas HTML e importador da Wikipedia
  ratings.py                notas de piloto/chassis/motor pela matriz de ponderação
  event/                    simulação de evento (clima, modelo de volta, sessões)
  ui/                       telas (tema Win9x, menu, novo jogo, gestão, evento, mercado,
                            desenvolvimento, histórico, editor)
tools/gerar_db_exemplo.py   gera as categorias fictícias de exemplo
```

As duas categorias de exemplo (Fórmula Alfa e Fórmula Beta) são fictícias e têm regras diferentes:
chassis próprio × chassis comprado, pilotos de teste, reabastecimento, formato do evento.
Elas servem para testar a maleabilidade da estrutura.
