-- ============================================================================
-- MoviZap — migração 091: anexo na observação do card (painel da Operação)
--
-- 🔵 Pedido dele em 04/11: *"Card OBS anexos, texto, format conve -- exibir em
-- modal"*. A observação existe desde a 084 e é só texto; o modal passa a
-- aceitar arquivo.
--
-- 🚨 POR QUE UMA TABELA NOVA, E NÃO A `midia`: o banco PROÍBE. A `midia` tem
-- `CHECK midia_tem_um_dono` (migração 047):
--     CHECK ((conversa_id IS NULL) <> (sala_id IS NULL))
-- -- ou-exclusivo, exatamente um dono, nunca nenhum. Observação de card não é
-- conversa nem sala de chat, então não há linha possível ali. ⚠️ E não se
-- afrouxa o CHECK: ele é o que impede mídia órfã, e órfã é mídia que ninguém
-- acha para apagar.
--
-- ⚠️ O MOLDE É O `formulario_arquivo` (074), não a `midia`: pasta própria fora
-- do repositório, caminho no banco, nome original preservado e lista branca de
-- extensão no código. Mesmo desenho, mesmo lugar conceitual.
--
-- 🚨 ESTE ANEXO NÃO TEM BACKUP, e isso precisa estar escrito onde alguém lê. A
-- pasta vive fora do `movizap_painel` de propósito (como as outras duas), e o
-- `scripts/backup_db.py` leva o BANCO -- a linha com o caminho sobrevive, o
-- arquivo não. A tela diz isso.
--
-- ⚠️ `ON DELETE CASCADE` na observação: a `os_observacao` não se apaga por
-- desenho ("não se apaga" está escrito na tela), então o CASCADE é uma rede
-- para o caso de alguém apagar à mão no banco -- e não um caminho oferecido.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS os_observacao_arquivo (
  id             bigserial PRIMARY KEY,
  observacao_id  integer NOT NULL
                 REFERENCES os_observacao(id) ON DELETE CASCADE,
  nome_original  varchar(255) NOT NULL,
  caminho        text NOT NULL,
  bytes          bigint NOT NULL DEFAULT 0,
  mime           varchar(100),
  criado_em      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_observacao_arquivo
    ON os_observacao_arquivo (observacao_id);

COMMENT ON TABLE os_observacao_arquivo IS
  'Anexo de uma observação do card (painel da Operação). Molde do '
  'formulario_arquivo: pasta própria fora do repositório, caminho no banco. '
  'NÃO usa a tabela midia -- o CHECK midia_tem_um_dono exige conversa ou sala.';
COMMENT ON COLUMN os_observacao_arquivo.caminho IS
  'Caminho no disco, em /home/claude/movizap_observacao_anexos. ⚠️ Esta pasta '
  'NÃO tem backup: o backup leva o banco, então a linha sobrevive e o arquivo '
  'não. A tela avisa.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('091', now(), 'anexo na observacao do card do painel da Operacao');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT table_name FROM information_schema.tables
--    WHERE table_name = 'os_observacao_arquivo';
--     -- esperado: uma linha
--
--   SELECT count(*) FROM os_observacao_arquivo;
--     -- esperado hoje: 0
--
--   SELECT conname FROM pg_constraint WHERE conrelid = 'midia'::regclass
--     AND conname = 'midia_tem_um_dono';
--     -- esperado: continua lá, intacto -- esta migração NÃO o afrouxa
--
-- DESFAZER:
--
--   BEGIN;
--   DROP TABLE IF EXISTS os_observacao_arquivo;
--   DELETE FROM schema_migracao WHERE versao = '091';
--   COMMIT;
--     -- ⚠️ Os arquivos no disco NÃO são apagados por isto. Quem desfizer
--     --    precisa decidir o que fazer com /home/claude/movizap_observacao_anexos.
-- ----------------------------------------------------------------------------
