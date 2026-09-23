-- ============================================================================
-- MoviZap — migração 047: anexo no chat interno
--
-- 🔵 Pedido dele (22/09): "sobre envio de anexos no chat interno, igual no
-- aberto". Teto de 25 MB e áudio gravado junto, decididos por ele no mesmo
-- dia.
--
-- 🚨 UMA PASTA SÓ, UMA TABELA SÓ, UMA ROTA DE SERVIR SÓ. A tentação era dar
-- ao chat a sua própria tabela de mídia. Seriam duas pastas, dois dedupes,
-- duas rotas de download e duas regras de permissão para manter em dia -- e a
-- segunda sempre esquece o que a primeira aprendeu (gravar em `.parcial` e só
-- então renomear, conferir que o arquivo continua no disco antes de servir).
-- A `midia` passa a atender os dois mundos, e a COLUNA DIZ DE QUEM É.
--
-- 🚨 O `CHECK` É A REGRA DE PERMISSÃO, NÃO ENFEITE. É ele que garante que
-- toda linha pertence a exatamente um dono -- ou uma conversa, ou uma sala,
-- nunca os dois e nunca nenhum. A rota de servir decide quem pode ver LENDO
-- essa coluna; sem a garantia do banco, uma linha órfã viraria mídia que
-- ninguém sabe de quem é, e "não sei de quem é" acaba virando "deixa ver".
--
-- ⚠️ AS 2.586 LINHAS DE HOJE PASSAM SEM TOQUE. `conversa_id` era `NOT NULL`,
-- então todas já satisfazem "conversa preenchida, sala vazia". Conferido
-- antes de escrever, não depois de aplicar.
--
-- ⚠️ O DEDUPE MUDA DE CHAVE, e isso é código, não banco. Hoje o
-- `midia.guardar` procura por `hash + conversa_id`; com dois donos possíveis
-- a busca passa a ser por `hash + dono`. O índice abaixo existe para as duas
-- formas.
-- ============================================================================

BEGIN;

-- ── a mídia ganha um segundo dono possível ──────────────────────────────────
ALTER TABLE midia ALTER COLUMN conversa_id DROP NOT NULL;

ALTER TABLE midia ADD COLUMN sala_id BIGINT REFERENCES chat_sala(id);

ALTER TABLE midia ADD CONSTRAINT midia_tem_um_dono
    CHECK ((conversa_id IS NULL) <> (sala_id IS NULL));

-- O dedupe procura por hash DENTRO de um dono. Um índice por dono.
CREATE INDEX IF NOT EXISTS midia_hash_conversa ON midia (hash, conversa_id);
CREATE INDEX IF NOT EXISTS midia_hash_sala     ON midia (hash, sala_id);

-- ── a mensagem do chat ganha o anexo ────────────────────────────────────────
-- ⚠️ NULO É O NORMAL: a esmagadora maioria das mensagens é só texto.
ALTER TABLE chat_mensagem ADD COLUMN midia_id BIGINT REFERENCES midia(id);

-- 🚨 MENSAGEM PODE SER SÓ ANEXO, SEM TEXTO. Quem manda um print raramente
-- escreve legenda, e exigir texto obrigaria a tela a inventar um. O `texto`
-- continua `NOT NULL` no schema; o que se grava é string vazia -- e é a
-- presença do `midia_id` que diz que há algo para mostrar.
CREATE INDEX IF NOT EXISTS chat_mensagem_midia ON chat_mensagem (midia_id)
    WHERE midia_id IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('047', now(), 'chat interno: anexo (midia com dois donos possiveis)');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d midia
--   SELECT count(*) FROM midia WHERE sala_id IS NOT NULL;      -- 0
--   SELECT count(*) FROM midia WHERE conversa_id IS NULL;      -- 0
--   SELECT count(*) FROM chat_mensagem WHERE midia_id IS NOT NULL;  -- 0
--   SELECT versao FROM schema_migracao WHERE versao = '047';   -- 047
--
-- DESFAZER:
--   ALTER TABLE chat_mensagem DROP COLUMN midia_id;
--   ALTER TABLE midia DROP CONSTRAINT midia_tem_um_dono, DROP COLUMN sala_id;
--   ALTER TABLE midia ALTER COLUMN conversa_id SET NOT NULL;
--   DROP INDEX IF EXISTS midia_hash_conversa, midia_hash_sala, chat_mensagem_midia;
--   DELETE FROM schema_migracao WHERE versao = '047';
-- ----------------------------------------------------------------------------
