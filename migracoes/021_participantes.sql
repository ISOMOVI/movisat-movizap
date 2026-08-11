-- ============================================================================
-- MoviZap — migração 021: participantes na conversa
--
-- Decisão do usuário em 2026-08-11: dá para convidar outro atendente para uma
-- conversa; o convidado responde à vontade ("como um convidado mesmo"); sair é
-- do próprio ou do dono; e **quando o DONO sai, a posse passa para quem ficou**.
--
-- ----------------------------------------------------------------------------
-- 🚨 CONVIDAR NÃO DÁ ACESSO — O ACESSO JÁ EXISTIA
--
-- A auditoria de 11/08 mostrou que **não há isolamento por conversa**: as 13
-- rotas de atendimento exigem só a tela `ATD_1.2`, e nenhuma pergunta quem é o
-- dono. Qualquer atendente já abria, lia, respondia e vinculava qualquer
-- conversa.
--
-- Então esta tabela responde outra pergunta: **quem está acompanhando**. Serve
-- para a conversa APARECER NA LISTA de quem foi chamado, e para a tela mostrar
-- quem mais está ali. Chamar isso de "permissão" seria mentir sobre o que o
-- sistema faz.
--
-- ⚠️ Se o isolamento por conversa passar a existir um dia, esta tabela vira a
-- lista de quem tem acesso além do dono -- e aí ela muda de significado. Está
-- dito aqui para ninguém supor que já é isso.
--
-- ----------------------------------------------------------------------------
-- POR QUE `saiu_em` EM VEZ DE APAGAR A LINHA
--
-- Quem entrou na conversa leu o que estava escrito nela. Apagar a linha faria
-- o sistema esquecer que aquela pessoa viu -- e "quem teve acesso a esta
-- conversa" é exatamente a pergunta que se faz depois, não antes.
--
-- ⚠️ A chave primária composta tem uma consequência assumida: reconvidar quem
-- saiu REABRE a mesma linha (`saiu_em = NULL`), em vez de criar outra. Perde-se
-- o histórico de idas e vindas. É a troca escolhida: para auditoria importa se
-- a pessoa esteve, não quantas vezes -- e uma PK serial deixaria a porta aberta
-- para duas participações ativas do mesmo atendente, que é o defeito pior.
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversa_participante (
    conversa_id   bigint NOT NULL REFERENCES conversa(id) ON DELETE CASCADE,
    atendente_id  bigint NOT NULL REFERENCES atendente(id),
    -- quem chamou. NULL quando a pessoa entrou por conta própria.
    convidado_por bigint REFERENCES atendente(id),
    entrou_em     timestamptz NOT NULL DEFAULT now(),
    saiu_em       timestamptz,
    PRIMARY KEY (conversa_id, atendente_id),
    -- 🚨 CHECK é contrato (docs/02): sair antes de entrar é impossível, e não
    -- "improvável". Sem isto, um relógio errado ou um UPDATE torto gravaria
    -- uma participação negativa que nenhuma tela saberia mostrar.
    CONSTRAINT ck_participante_saida CHECK (saiu_em IS NULL OR saiu_em >= entrou_em)
);

-- 🚨 É POR AQUI QUE A LISTAGEM ENTRA: "quais conversas eu acompanho?" roda a
-- cada carregamento da caixa de entrada. Parcial porque quem já saiu não entra
-- em lista nenhuma -- o índice não carrega o que nunca será consultado.
--
-- ⚠️ Postgres NÃO indexa FK sozinho (metodologia, e migração 002 existe por
-- isso). Sem este índice, cada abertura da caixa varreria a tabela inteira.
CREATE INDEX IF NOT EXISTS ix_participante_atendente
    ON conversa_participante (atendente_id) WHERE saiu_em IS NULL;

-- A outra direção: "quem está nesta conversa?", para o cabeçalho da tela.
CREATE INDEX IF NOT EXISTS ix_participante_conversa
    ON conversa_participante (conversa_id) WHERE saiu_em IS NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('021', now(), 'participantes na conversa (convidar, sair, herdar posse)');
