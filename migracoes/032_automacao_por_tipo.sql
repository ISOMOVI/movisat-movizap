-- ============================================================================
-- MoviZap — migração 032: automação por tipo de contato
--
-- Pedido do usuário em 25/08: *"terá um interruptor nela que aciona IA ou bot,
-- por tipo de contato, então quando a mensagem chegar, será um filtro de uso
-- ou não, assim evitamos desgaste"*.
--
-- ----------------------------------------------------------------------------
-- 🚨 O QUE ESTA MIGRAÇÃO **NÃO** FAZ: PROMETER IA
--
-- `docs/09_Auditoria_Escopo.md`, item 4: *"Configuração não afirma o que o
-- código não faz. `avaliacao_ativa = true` sem implementação é defeito, não
-- preparação."*
--
-- Medido antes de escrever isto: `canal.ia_ligada` é LIDO em quatro lugares e
-- **nenhum age sobre ele**. Não existe motor de IA no painel -- o
-- `services/llm/` do `IA_agente_Movichat` nunca migrou -- e não existe bot.
--
-- Por isso:
--   - `boas_vindas_ligado` ACIONA DE VERDADE, e nasce desligado;
--   - `ia_ligada` existe na tabela e a tela o mostra DESLIGADO E TRAVADO, com
--     o motivo escrito. Guardar o valor é barato; o que não se pode é oferecer
--     um botão que não faz nada e deixar alguém confiar nele.
--
-- ----------------------------------------------------------------------------
-- POR QUE UMA LINHA POR RELAÇÃO, E NÃO UMA COLUNA EM `contato`
--
-- A decisão é sobre o TIPO, não sobre a pessoa: "todo fornecedor recebe boas
-- vindas" é uma linha, não 200 marcações. E é o que permite mudar de ideia
-- sobre um tipo inteiro sem tocar em cadastro nenhum.
--
-- 🚨 `sem_cadastro` É UMA LINHA AQUI, e não é valor de `contato.relacao`.
-- 64% das conversas (211 de 332, medido em 25/08) chegam de número que não
-- tem contato nenhum -- é o caso MAIS COMUM, e é exatamente onde uma
-- mensagem automática ajuda ou atrapalha mais. Sem esta linha, o caso
-- majoritário não teria como ser configurado.
--
-- ⚠️ `relacao` aqui é texto livre com CHECK próprio, não FK: os valores vivem
-- no CHECK de `contato.relacao`, mais o `sem_cadastro`, que não é relação.
-- ============================================================================

CREATE TABLE IF NOT EXISTS relacao_automacao (
    relacao             text PRIMARY KEY
                        CHECK (relacao IN ('cliente', 'fornecedor', 'parceiro',
                                           'tecnico', 'lead', 'colaborador',
                                           'teste', 'sem_identificacao',
                                           'sem_cadastro')),
    -- Aciona de verdade. Nasce desligado: automação que nasce ligada manda
    -- mensagem para cliente antes de alguém decidir que devia.
    boas_vindas_ligado  boolean NOT NULL DEFAULT false,
    boas_vindas_texto   text,
    -- 🚨 GUARDADO, NÃO ACIONADO. Não há motor de IA no painel. A tela mostra
    -- travado, com o motivo -- ver o cabeçalho desta migração.
    ia_ligada           boolean NOT NULL DEFAULT false,
    atualizado_em       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE relacao_automacao IS
    'O que roda sozinho quando chega mensagem, por tipo de contato. '
    'A linha sem_cadastro cobre quem não tem contato nenhum -- 64% das '
    'conversas em 25/08.';

-- Uma linha por valor possível, todas desligadas. Sem isto, "tipo sem linha"
-- e "tipo desligado" seriam estados diferentes na leitura, e alguém teria de
-- lembrar de criar a linha antes de poder ligar.
INSERT INTO relacao_automacao (relacao)
VALUES ('cliente'), ('fornecedor'), ('parceiro'), ('tecnico'), ('lead'),
       ('colaborador'), ('teste'), ('sem_identificacao'), ('sem_cadastro')
ON CONFLICT (relacao) DO NOTHING;

-- 🚨 A TRAVA DE "UMA VEZ SÓ" É DO BANCO, NÃO DA LÓGICA. O Evolution reentrega
-- webhook, e a conversa pode ser tocada por dois processos ao mesmo tempo.
-- Sem uma marca gravada, o cliente receberia "olá, seja bem-vindo" duas ou
-- três vezes -- que é pior do que não receber.
ALTER TABLE conversa ADD COLUMN IF NOT EXISTS boas_vindas_em timestamptz;

COMMENT ON COLUMN conversa.boas_vindas_em IS
    'Quando a mensagem automática de boas-vindas foi enviada nesta conversa. '
    'NULL = nunca. É a trava de idempotência: o UPDATE condicional só passa '
    'uma vez.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('032', now(), 'automacao por tipo de contato: boas-vindas por relacao');
