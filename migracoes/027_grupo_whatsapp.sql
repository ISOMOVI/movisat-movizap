-- ============================================================================
-- MoviZap — migração 027: a conversa deixa de ser sempre um telefone
--
-- Grupo do WhatsApp não tem telefone: tem JID `1203...@g.us`. A `conversa` foi
-- construída inteira em cima de telefone -- coluna obrigatória, índice único
-- por (canal, telefone), e `tel.normalizar` como porta de entrada de tudo.
--
-- 🚨 O QUE ESTA MIGRAÇÃO NÃO FAZ: ligar grupo. O `groupsIgnore = true` do
-- Evolution continua onde está até alguém desligá-lo de propósito. Aqui só se
-- prepara o modelo -- e é assim porque assim que os grupos começarem a chegar
-- não haverá tempo de discutir esquema.
--
-- ⚠️ NADA MUDA PARA CONVERSA EXISTENTE. `tipo` nasce 'direta' com DEFAULT, e o
-- CHECK novo é satisfeito por toda linha atual (todas têm telefone e nenhuma
-- tem JID). Conferido antes de escrever: 165 conversas, todas com telefone.
-- ============================================================================

ALTER TABLE conversa ADD COLUMN tipo text NOT NULL DEFAULT 'direta'
    CHECK (tipo IN ('direta', 'grupo'));

ALTER TABLE conversa ADD COLUMN grupo_jid  text;
ALTER TABLE conversa ADD COLUMN grupo_nome text;

-- 🚨 A CHAVE DA "OPÇÃO B", decidida pelo usuário. Ligar grupo faz TODO grupo
-- de que o número participa virar conversa de uma vez -- inclusive grupo
-- pessoal, de condomínio e de fornecedor. Com `atender = false`, o grupo chega
-- e fica numa aba separada até alguém dizer que quer atendê-lo. A caixa de
-- entrada não é invadida no primeiro dia.
--
-- ⚠️ Conversa direta nasce `true`: nada muda para quem já existe.
ALTER TABLE conversa ADD COLUMN atender boolean NOT NULL DEFAULT true;

-- Grupo não tem telefone. A coluna deixa de ser obrigatória, e o CHECK passa a
-- garantir que cada tipo tem a SUA identidade -- sem isso, uma linha poderia
-- nascer sem telefone e sem JID, e não haveria como saber com quem se fala.
ALTER TABLE conversa ALTER COLUMN telefone_e164 DROP NOT NULL;

ALTER TABLE conversa ADD CONSTRAINT ck_conversa_identidade CHECK (
    (tipo = 'direta' AND telefone_e164 IS NOT NULL AND grupo_jid IS NULL)
 OR (tipo = 'grupo'  AND grupo_jid     IS NOT NULL AND telefone_e164 IS NULL));

-- 🚨 O ÍNDICE ÚNICO É O QUE FAZ O CLIENTE QUE VOLTA REABRIR EM VEZ DE
-- DUPLICAR. Ele era por telefone; passa a ser pela IDENTIDADE, seja qual for.
-- `COALESCE` porque exatamente uma das duas está preenchida -- garantido pelo
-- CHECK acima.
DROP INDEX ux_conversa_aberta;
CREATE UNIQUE INDEX ux_conversa_aberta
    ON conversa (canal_id, COALESCE(grupo_jid, telefone_e164))
    WHERE estado <> 'resolvida';

-- A caixa de entrada e a fila passam a filtrar por `atender`; sem índice, a
-- consulta mais frequente do painel faria varredura.
CREATE INDEX ix_conversa_atender ON conversa (atender, estado);

-- ── quem falou dentro do grupo ──────────────────────────────────────────────
-- 🚨 NUMA CONVERSA DIRETA O REMETENTE É A PRÓPRIA CONVERSA; num grupo, não.
-- Sem guardar isto, o balão de entrada de um grupo de quinze pessoas não sabe
-- dizer quem falou -- e o histórico vira um monólogo de autor desconhecido.
-- O Evolution manda em `data.key.participant`.
ALTER TABLE mensagem ADD COLUMN remetente_jid  text;
ALTER TABLE mensagem ADD COLUMN remetente_nome text;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('027', now(), 'conversa aceita grupo do WhatsApp (jid, atender, remetente)');
