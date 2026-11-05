-- ============================================================================
-- MoviZap — migração 090: o checklist de cada etapa do painel da Operação
--
-- 🔵 Pedido dele em 04/11, com um print do Bitrix como referência: *"são itens
-- que vão ficar em um botão dentro do card, como mapa para o operador saber o
-- que fazer"*. E, sobre a lista: **"Modelo fixo + o operador pode acrescentar"**.
--
-- 🚨 NÃO É O CHECKLIST DO HARMONIT, e a diferença é de propósito. O ERP tem
-- checklist DE OS (`ObterCheckListOrdemServico`) e ele aparece no app do
-- técnico em campo. Os itens daqui são de ESCRITÓRIO -- *"Verificar DataScope"*,
-- *"Nota Fiscal (emitir e enviar)"*, *"Cadastrar cliente e veículos"* -- e no
-- app do técnico só fariam ruído. Decisão dele: nem um nem outro, é mapa do
-- operador no card.
--
-- ⚠️ E NADA DAQUI VAI PARA A OS. Ao sair da etapa o checklist vira **observação
-- do card** (`os_observacao`), que é do MoviZap. Decisão dele quando mostrei que
-- gravar `solucaoTecnica` exigiria reescrever a OS INTEIRA no Harmonit
-- (`SalvarOrdemServico`, a mesma armadilha do endereço): *"Só no MoviZap, como
-- observação"*.
--
-- 🚨 A CHAVE É `numero_os`, não a solicitação -- a mesma régua da 084:
-- *"amarrar na solicitação deixaria 10 dos 11 cards sem onde escrever"*, porque
-- a maioria dos cards vem do ERP e não nasceu de formulário nosso.
-- ============================================================================

BEGIN;

-- 1. O MODELO da etapa -------------------------------------------------------
--
-- A lista que **toda** OS daquela coluna recebe. Uma linha por item.
--
-- ⚠️ `situacao_id` SEM chave estrangeira, de propósito: as 17 situações vivem
-- em `movizap/paineis.py` (tupla `SITUACOES`), não em tabela. Inventar uma
-- tabela de situações aqui criaria uma segunda fonte para a mesma lista, e
-- duas listas da mesma coisa acabam discordando.
CREATE TABLE IF NOT EXISTS checklist_modelo (
  id          bigserial PRIMARY KEY,
  situacao_id integer NOT NULL,
  texto       varchar(200) NOT NULL CHECK (btrim(texto) <> ''),
  ordem       integer NOT NULL DEFAULT 0,
  -- Desativar, nunca apagar: `checklist_item.de_modelo_id` aponta para cá, e
  -- item marcado em 50 cards não pode perder o assunto porque alguém limpou a
  -- lista. É a régua do `servico_tecnico` e do `operacao.py`.
  ativo       boolean NOT NULL DEFAULT true,
  criado_em   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS checklist_modelo_etapa_idx
    ON checklist_modelo (situacao_id, ordem) WHERE ativo;

COMMENT ON TABLE checklist_modelo IS
  'A lista de tarefas de cada etapa do painel da Operação -- o "mapa para o '
  'operador saber o que fazer" (decisão dele, 04/11). Vira itens no card na '
  'primeira abertura daquela etapa.';

-- 2. O ITEM do card ----------------------------------------------------------
--
-- 🚨 O ITEM É CÓPIA, NÃO REFERÊNCIA. O `texto` é gravado aqui no momento em que
-- o card abre a etapa pela primeira vez. Ler do modelo por referência faria uma
-- edição de hoje reescrever o que alguém marcou semana passada -- e o card é
-- registro do que foi feito, não espelho da configuração atual. É o mesmo
-- desenho do `tipo_nome` do agendamento (072) e do `origem_endereco` (077):
-- retrato, não ponteiro.
--
-- ⚠️ `de_modelo_id` NULO = item avulso, que o operador acrescentou naquele card
-- (*"Modelo fixo + o operador pode acrescentar"*). É esta coluna que decide
-- quem pode ser removido: item de modelo não se apaga do card.
CREATE TABLE IF NOT EXISTS checklist_item (
  id            bigserial PRIMARY KEY,
  numero_os     integer NOT NULL,
  situacao_id   integer NOT NULL,
  texto         varchar(200) NOT NULL CHECK (btrim(texto) <> ''),
  ordem         integer NOT NULL DEFAULT 0,
  de_modelo_id  bigint REFERENCES checklist_modelo(id) ON DELETE SET NULL,

  -- 🚨 DESMARCAR NÃO APAGA: vira `feito = false` com `feito_em` novo. Quem
  -- marcou e desmarcou fez duas coisas, e as duas são informação.
  feito         boolean NOT NULL DEFAULT false,
  feito_por     bigint REFERENCES atendente(id) ON DELETE SET NULL,
  feito_em      timestamptz,

  criado_por    bigint REFERENCES atendente(id) ON DELETE SET NULL,
  criado_em     timestamptz NOT NULL DEFAULT now(),

  -- Um item de modelo entra UMA vez por OS e etapa. É esta restrição que torna
  -- a cópia idempotente: abrir o card duas vezes não duplica a lista.
  -- ⚠️ Não alcança item avulso (`de_modelo_id` nulo), e é o certo: o operador
  -- pode escrever dois avulsos com o mesmo texto se quiser.
  CONSTRAINT checklist_item_modelo_uma_vez
      UNIQUE (numero_os, situacao_id, de_modelo_id)
);

CREATE INDEX IF NOT EXISTS checklist_item_card_idx
    ON checklist_item (numero_os, situacao_id, ordem);
-- O selo "2 de 3" de 50 cards numa consulta só (o molde é
-- `passagem.quantas_observacoes`).
CREATE INDEX IF NOT EXISTS checklist_item_os_idx
    ON checklist_item (numero_os);

COMMENT ON TABLE checklist_item IS
  'O checklist daquele card naquela etapa. Cópia do modelo (de_modelo_id) ou '
  'item avulso do operador (de_modelo_id nulo). Desmarcar não apaga.';
COMMENT ON COLUMN checklist_item.texto IS
  'Cópia do texto no momento em que o card abriu a etapa. Editar o modelo '
  'depois NÃO reescreve isto -- o card é registro, não espelho.';

-- 3. O SEED: as três etapas que ele detalhou ---------------------------------
--
-- 🔵 As listas são dele, literais. As outras seis etapas que ele citou
-- (15747, 15797, 890, 16489, 1316, 15696) ficaram **sem itens** -- ele não os
-- escreveu, e inventar tarefa de operação seria adivinhar o trabalho de quem
-- faz. Etapa sem modelo simplesmente não mostra o botão.
--
-- ⚠️ "Nota Fiscal (emitir e enviar)" é item de MARCAR, e só: **não existe nada
-- de nota fiscal no FPSL** (medido em 04/11 -- nenhuma emissão, nenhum envio,
-- nenhuma integração fiscal). O item registra que alguém fez, fora do sistema.
INSERT INTO checklist_modelo (situacao_id, texto, ordem) VALUES
  -- 251 — Configurar equipamentos e Sistemas
  (251,   'Informação do contrato sobre os equipamentos', 1),
  (251,   'Cadastrar cliente e veículos',                 2),
  (251,   'Registrar posicionamento e dados',             3),
  -- 16488 — Entrega de materiais prontos
  (16488, 'Verificar DataScope',                          1),
  (16488, 'Verificar Dados OS',                           2),
  (16488, 'Nota Fiscal (emitir e enviar)',                3),
  (16488, 'Itens',                                        4),
  -- 677 — Enviar por correio/transportadora
  (677,   'Enviar material',                              1),
  (677,   'Inserir código de rastreio',                   2)
ON CONFLICT DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('090', now(), 'checklist por etapa do painel da Operacao: modelo da etapa e item do card');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT situacao_id, count(*) FROM checklist_modelo GROUP BY situacao_id
--    ORDER BY situacao_id;
--     -- esperado: 251 -> 3 | 677 -> 2 | 16488 -> 4
--
--   SELECT count(*) FROM checklist_item;
--     -- esperado: 0 -- item nasce quando um card abre a etapa
--
--   SELECT conname FROM pg_constraint
--    WHERE conrelid = 'checklist_item'::regclass AND contype = 'u';
--     -- esperado: checklist_item_modelo_uma_vez
--
-- DESFAZER:
--
--   BEGIN;
--   DROP TABLE IF EXISTS checklist_item;
--   DROP TABLE IF EXISTS checklist_modelo;
--   DELETE FROM schema_migracao WHERE versao = '090';
--   COMMIT;
--     -- ⚠️ Isto apaga o que foi marcado nos cards. As observações já gravadas
--     --    ao sair das etapas continuam em `os_observacao` -- elas são texto,
--     --    e não dependem destas tabelas.
-- ----------------------------------------------------------------------------
