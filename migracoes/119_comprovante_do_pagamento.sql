-- ============================================================================
-- MoviZap — migração 119: o anexo do comprovante de pagamento (aba 2, PNL_1.6)
-- ============================================================================
--
-- 🔵 Pedido dele, 18/11: *"haverá campo para que em cada 1 dos artefatos de
-- pagamento seja inserido anexo que comprove o pagamento. Após o envio do
-- anexo, abre o campo que pede o valor inserido no documento."*
-- 🔵 E em 24/11, sobre o formato: o anexo é **do MoviZap, no padrão da
-- observação da Operação**, e é **anexo completo — não só PDF**.
--
-- 🚨 **O `artefato_id` NÃO TEM CHAVE ESTRANGEIRA, E ISSO É DESENHO.** O
-- artefato de pagamento vive no **SQLite do FPSL** (`pagamento_artefato`) e
-- esta tabela é **Postgres**: não existe FK possível entre os dois bancos.
-- Quem confere a existência é a rota, **pelo quadro da ponte** (404 quando o
-- artefato não está nele) — a mesma régua que a `/os/{artefato_id}` já usa.
-- Pôr `REFERENCES` aqui seria mentir sobre uma garantia que o banco não dá.
--
-- ⚠️ **ESTA PASTA NÃO TEM BACKUP**, como as outras três de anexo: o backup
-- leva o banco, então a linha sobrevive ao arquivo que o disco perdeu. Quem
-- baixa recebe **410** com a frase, nunca 500.
--
-- 🚨 A REFERÊNCIA NO FPSL É TEXTO, não bytes: o FPSL guarda `anexo:<id>` no
-- `comprovante_arquivo` que já existe, pelo `guardar_comprovante` que já
-- existe. Nenhum byte atravessa a ponte, que é JSON servidor-a-servidor.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS pagamento_comprovante_arquivo (
  id             bigserial PRIMARY KEY,
  artefato_id    integer NOT NULL,
  nome_original  varchar(255) NOT NULL,
  caminho        text NOT NULL,
  bytes          bigint NOT NULL DEFAULT 0,
  mime           varchar(100),
  criado_em      timestamptz NOT NULL DEFAULT now(),
  por            varchar(120)
);

CREATE INDEX IF NOT EXISTS idx_pagamento_comprovante_artefato
    ON pagamento_comprovante_arquivo (artefato_id);

COMMENT ON TABLE pagamento_comprovante_arquivo IS
  'Comprovante de pagamento anexado a um artefato da aba 2 do Financeiro '
  '(PNL_1.6). Molde do os_observacao_arquivo: pasta propria fora do '
  'repositorio, caminho no banco, lista BRANCA de extensao. Sem FK: o '
  'artefato vive no SQLite do FPSL, e quem confere e a rota, pelo quadro.';
COMMENT ON COLUMN pagamento_comprovante_arquivo.artefato_id IS
  'id do pagamento_artefato no fpsl.db. NAO e FK -- outro banco. A rota '
  'recusa com 404 o artefato que nao esta no quadro da ponte.';
COMMENT ON COLUMN pagamento_comprovante_arquivo.caminho IS
  'Caminho no disco, em /home/claude/movizap_pagamento_comprovantes. '
  'Esta pasta NAO tem backup: a linha sobrevive, o arquivo nao, e o download '
  'devolve 410 com a frase.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('119', now(), 'anexo do comprovante de pagamento da aba 2 (PNL_1.6): tabela pagamento_comprovante_arquivo, sem FK porque o artefato vive no SQLite do FPSL');

COMMIT;
