-- ============================================================================
-- MoviZap — migração 084: a observação do painel (Bloco F, fase 1)
--
-- 🔵 Pedido dele no plano: *"observação do painel, com autor e hora, **no
-- MoviZap**. Não vai para a `solucaoTecnica` — aquele campo é da operação, e o
-- fluxo que está lá vai ser apagado"* (a decisão D10).
--
-- 🚨 POR QUE ELA NÃO VAI PARA O ERP, e isso é o ponto: a `solucaoTecnica` é da
-- operação técnica, e escrever recado de painel nela misturaria duas coisas num
-- campo que o cliente pode ler num relatório. E mais: escrever nela **grava a
-- OS inteira** (`SalvarOrdemServico`) a cada recado — risco sem ganho.
--
-- 🔵 E a régua dele vale aqui também: *"deve ter o log de quem faz o que
-- SEMPRE"*. Toda observação tem autor e hora, e **não se apaga** — editar ou
-- apagar recado é reescrever a história que a operação leu.
--
-- ⚠️ A CHAVE É O `numero_os` E NÃO A SOLICITAÇÃO: desde a D8 o card é a OS, de
-- qualquer origem, e a maioria não tem solicitação. Amarrar na solicitação
-- deixaria 10 dos 11 cards sem onde escrever.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS os_observacao (
    id           serial PRIMARY KEY,
    numero_os    integer NOT NULL,
    texto        text NOT NULL,
    atendente_id integer REFERENCES atendente(id) ON DELETE SET NULL,
    em           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT os_observacao_texto_check CHECK (btrim(texto) <> '')
);

COMMENT ON TABLE os_observacao IS
    'A observacao do painel sobre uma OS, com autor e hora. 🔵 Dele: "observacao '
    'do painel, com autor e hora, NO MOVIZAP". 🚨 NAO vai para a solucaoTecnica '
    'do Harmonit: aquele campo e da operacao tecnica, o cliente pode le-lo num '
    'relatorio, e escrever nele gravaria a OS INTEIRA a cada recado.';

COMMENT ON COLUMN os_observacao.numero_os IS
    'A OS, e nao a solicitacao: desde a D8 o card e a OS de qualquer origem, e '
    'a maioria nao tem solicitacao -- amarrar na solicitacao deixaria 10 dos 11 '
    'cards sem onde escrever.';

COMMENT ON COLUMN os_observacao.texto IS
    'O recado. 🚨 Nao ha coluna de "apagada" nem de "editada", de proposito: '
    'reescrever recado e reescrever a historia que a operacao leu.';

CREATE INDEX IF NOT EXISTS idx_observacao_os
    ON os_observacao (numero_os, em DESC);

-- 🔵 *"o log de quem faz o que"* -- tambem por pessoa.
CREATE INDEX IF NOT EXISTS idx_observacao_quem
    ON os_observacao (atendente_id, em DESC);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('084', now(), 'observacao do painel sobre a OS, com autor e hora (Bloco F fase 1)');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--   SELECT count(*) FROM os_observacao;      -- esperado agora: 0
--   SELECT indexname FROM pg_indexes WHERE tablename = 'os_observacao';
-- ----------------------------------------------------------------------------
