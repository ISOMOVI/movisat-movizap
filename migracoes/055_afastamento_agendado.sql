-- ============================================================================
-- MoviZap — migração 055: afastamento com saída e volta
--
-- 🔵 Decisão dele em 25/09: *"ao definir o motivo, um calendário já indica a
-- saída e a volta, daí volta"* -- e as conversas passam ao substituto *"no dia
-- da saída"*. E *"ela loga e vai na configuração dela e coloca o dia de
-- ontem"*: a própria pessoa encerra, mudando a volta.
--
-- ----------------------------------------------------------------------------
-- POR QUE O AGENDAMENTO TEM COLUNAS PRÓPRIAS (`afasta_*`)
--
-- `afastamento_motivo` preenchido quer dizer "afastado AGORA" em seis lugares
-- (`presenca.pode_receber`, `conversas.transferir`, a lista de quem recebe,
-- a tela...). Gravar ali um afastamento de semana que vem afastaria a pessoa
-- hoje. O agendado mora em `afasta_*` até o dia da saída; nesse dia o laço de
-- `presenca` transfere as conversas e o passa para as colunas de sempre.
--
-- ⚠️ `afastado_ate` continua sendo o dia da VOLTA do afastamento em curso, e
-- agora vale: nesse dia o laço encerra o afastamento sozinho.
--
-- ⚠️ `max_conversas` sai na 056, DEPOIS do backend novo no ar: apagar aqui
-- quebraria o backend antigo (que ainda a lê) entre a migração e o reinício.
-- ============================================================================

BEGIN;

-- O dia em que o afastamento em curso começou (só para mostrar).
ALTER TABLE atendente ADD COLUMN afastado_de date;

-- O afastamento agendado.
ALTER TABLE atendente ADD COLUMN afasta_em date;
ALTER TABLE atendente ADD COLUMN afasta_ate date;
ALTER TABLE atendente ADD COLUMN afasta_motivo text;
ALTER TABLE atendente ADD COLUMN afasta_substituto_id bigint
    REFERENCES atendente(id) ON DELETE SET NULL;

-- Tudo ou nada: agendamento sem data ou sem motivo não sabe o que fazer.
ALTER TABLE atendente ADD CONSTRAINT ck_afasta_completo CHECK (
    (afasta_em IS NULL AND afasta_ate IS NULL AND afasta_motivo IS NULL
     AND afasta_substituto_id IS NULL)
    OR
    (afasta_em IS NOT NULL AND afasta_ate IS NOT NULL
     AND length(btrim(COALESCE(afasta_motivo, ''))) > 0)
);
ALTER TABLE atendente ADD CONSTRAINT ck_afasta_volta_depois
    CHECK (afasta_ate IS NULL OR afasta_ate > afasta_em);


INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('055', now(), 'afastamento agendado com saida e volta');

COMMIT;
