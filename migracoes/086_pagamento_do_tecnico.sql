-- ============================================================================
-- MoviZap — migração 086: os dados de PAGAMENTO do técnico (TED, PIX ou boleto)
--
-- 🔵 Pedido dele em 04/11, na segunda volta da tela: *"Banco ajuste para dados
-- de pagamento, pode ser TED, PIX, ou boleto, oopção por lista e campo com os
-- dados"*. E, sobre os quatro campos bancários que o formulário de
-- credenciamento pergunta: *"ajuste no formulario tbm, o mesmo formato. ai
-- amarra eles"*.
--
-- 🚨 O QUE SAI, E POR QUE SAIR É SEGURO AGORA. A migração 085 criou `banco`,
-- `agencia`, `conta` e `titular_tipo` — o espelho dos quatro campos do
-- formulário. Medido antes de escrever, em 04/11:
--   · `tecnico_ficha`: **0 linhas**
--   · fichas com qualquer dado bancário: **0**
--   · solicitações do formulário `CREDENCIAMENTO`: **0**
-- Não há dado a migrar porque não há dado. Se houvesse, esta migração copiaria
-- antes de derrubar — apagar coluna com conteúdo é outra conversa, e exigiria a
-- palavra dele sobre o que fazer com o conteúdo.
--
-- ⚠️ E AS QUATRO COLUNAS NÃO FICAM ÓRFÃS NO BANCO. Deixá-las sem uso seria pior
-- que removê-las: coluna que ninguém lê nem escreve é a próxima a ser
-- preenchida por engano, e o `docs/02` passaria a descrever um bloco que a tela
-- não tem. `grep` do que sai, feito antes: `movizap/tecnico_ficha.py`
-- (`CAMPOS_TEXTO`, `DE_PARA`, `titular_tipo`), `frontend/src/telas/*.vue`,
-- `tests/teste_tecnico_ficha.py`, `docs/02` e `docs/06`.
--
-- 🚨 DUAS COLUNAS, E NÃO UMA POR FORMA DE PAGAMENTO. "PIX" e "TED" não pedem
-- tabelas diferentes: pedem a MESMA pergunta ("para onde vai o dinheiro?") com
-- conteúdo diferente. Uma coluna por forma criaria três campos sempre vazios
-- menos um, e a primeira consulta que somasse "quem não tem dados de pagamento"
-- teria de conhecer as três.
--
-- ⚠️ `pagamento_dados` É TEXTO LIVRE, de propósito. Chave PIX é CPF, CNPJ,
-- telefone, e-mail ou chave aleatória; conta bancária é banco + agência +
-- conta + titular; boleto é um e-mail ou um combinado. Validar formato aqui
-- recusaria o que o técnico mandou do jeito que ele tem — e quem confere é
-- quem credencia.
-- ============================================================================

BEGIN;

ALTER TABLE tecnico_ficha
  -- Os valores são NOSSOS e em slug, não ids de ninguém: é deste campo que a
  -- tela e o formulário leem a mesma coisa. Mesmo princípio dos `value` do
  -- SUPORTE em 29/10 ("ler 'rastreamento' numa decisão é melhor que ler 1348").
  ADD COLUMN IF NOT EXISTS pagamento_forma varchar(10)
      CHECK (pagamento_forma IS NULL
             OR pagamento_forma IN ('ted', 'pix', 'boleto')),
  ADD COLUMN IF NOT EXISTS pagamento_dados text;

COMMENT ON COLUMN tecnico_ficha.pagamento_forma IS
  'Como se paga este técnico: ted, pix ou boleto. As mesmas três opções que o '
  'formulário de credenciamento oferece, com os mesmos valores — é o que amarra '
  'os dois lados (decisão dele, 04/11).';
COMMENT ON COLUMN tecnico_ficha.pagamento_dados IS
  'Para onde vai o dinheiro, como o técnico informou: chave PIX, ou banco/'
  'agência/conta, ou o combinado do boleto. Texto livre de propósito.';

-- As quatro que o bloco "Banco" tinha. Ver o aviso do topo: 0 linhas, 0 dados.
ALTER TABLE tecnico_ficha
  DROP COLUMN IF EXISTS banco,
  DROP COLUMN IF EXISTS agencia,
  DROP COLUMN IF EXISTS conta,
  DROP COLUMN IF EXISTS titular_tipo;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('086', now(), 'dados de pagamento do tecnico: forma (ted/pix/boleto) e os dados, no lugar dos 4 campos bancarios');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'tecnico_ficha'
--      AND column_name IN ('pagamento_forma','pagamento_dados',
--                          'banco','agencia','conta','titular_tipo');
--     -- esperado: só as duas primeiras
--
--   SELECT conname FROM pg_constraint
--    WHERE conrelid = 'tecnico_ficha'::regclass AND contype = 'c';
--     -- esperado: o CHECK de estado e o de pagamento_forma
--
-- DESFAZER:
--
--   BEGIN;
--   ALTER TABLE tecnico_ficha
--     DROP COLUMN IF EXISTS pagamento_forma,
--     DROP COLUMN IF EXISTS pagamento_dados,
--     ADD COLUMN IF NOT EXISTS banco varchar(60),
--     ADD COLUMN IF NOT EXISTS agencia varchar(20),
--     ADD COLUMN IF NOT EXISTS conta varchar(30),
--     ADD COLUMN IF NOT EXISTS titular_tipo varchar(1)
--         CHECK (titular_tipo IS NULL OR titular_tipo IN ('F','J'));
--   DELETE FROM schema_migracao WHERE versao = '086';
--   COMMIT;
--     -- ⚠️ Volta o ESQUEMA, não o conteúdo: o que tiver sido digitado em
--     --    pagamento_dados até lá é perdido. Conferir antes.
-- ----------------------------------------------------------------------------
