-- ============================================================================
-- MoviZap — migração 087: sai a `tecnico_origem`, a memória que virou cadastro
--
-- 🔵 04/11, decisão dele em duas partes. Primeiro: *"o cadastro alimenta
-- alimenta a memória, pode tirá-la. Caso mudem na hora só servirá para aquele
-- orçamento. Os demais ja vem com o do cad."* Depois, à proposta P1 do
-- fechamento: **"1 ok"**.
--
-- 🚨 A TABELA SAI PORQUE NINGUÉM A LÊ MAIS, e isso foi medido NA HORA de
-- escrever esta migração, não copiado da sessão da manhã:
--   · `SELECT count(*) FROM tecnico_origem` -> **0**
--   · `grep -rn 'tecnico_origem' movizap/*.py frontend/src/` -> **nenhuma
--     ocorrência em código**; só comentários que contam a história, e o
--     `tests/teste_rotas.py` tem um teste que REPROVA se
--     `rotas.lembrar_origem`/`rotas.origem_do_tecnico` voltarem a existir.
--
-- ⚠️ TABELA SEM LEITOR NÃO É INOFENSIVA. Ela é a próxima a ser preenchida por
-- engano, e enquanto existe o `docs/02` descreve um bloco que a tela não tem --
-- a mesma razão pela qual os quatro campos bancários saíram na 086 em vez de
-- ficarem órfãos.
--
-- 🔵 O que substituiu: `tecnico_ficha` (migração 085) guarda o endereço FIXO,
-- que é cadastro e tem quem mantenha -- a tela `TEC_1.1`. O retrato do que foi
-- cobrado em cada compromisso continua em `agendamento.origem_endereco` e
-- `agendamento.km`, que **não são tocados aqui**.
--
-- ⚠️ `rota_cache` TAMBÉM NÃO É TOCADA. Ela nasceu na mesma 077 e continua
-- válida: é cache de consulta paga, e não tem nada a ver com de quem é a
-- origem.
-- ============================================================================

BEGIN;

DROP TABLE IF EXISTS tecnico_origem;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('087', now(), 'sai a tecnico_origem: a origem do KM virou cadastro na ficha do tecnico (085)');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT table_name FROM information_schema.tables
--    WHERE table_name = 'tecnico_origem';
--     -- esperado: nenhuma linha
--
--   SELECT table_name FROM information_schema.tables
--    WHERE table_name IN ('rota_cache','tecnico_ficha');
--     -- esperado: as duas continuam
--
--   SELECT count(*) FROM information_schema.columns
--    WHERE table_name = 'agendamento'
--      AND column_name IN ('origem_endereco','km');
--     -- esperado: 2 -- o retrato não foi mexido
--
-- DESFAZER:
--
--   BEGIN;
--   CREATE TABLE IF NOT EXISTS tecnico_origem (
--     tecnico_contato_id bigint PRIMARY KEY REFERENCES contato(id) ON DELETE CASCADE,
--     cep varchar(8), logradouro varchar(80), numero varchar(10),
--     bairro varchar(60), cidade varchar(50), uf varchar(2),
--     complemento varchar(40),
--     atualizado_em timestamptz NOT NULL DEFAULT now()
--   );
--   DELETE FROM schema_migracao WHERE versao = '087';
--   COMMIT;
--     -- ⚠️ Volta VAZIA, e voltar o esquema não basta: quem escrevia nela eram
--     --    `rotas.lembrar_origem` e `rotas.origem_do_tecnico`, que saíram do
--     --    código em 04/11. Desfazer de verdade é desfazer a decisão D5.
-- ----------------------------------------------------------------------------
