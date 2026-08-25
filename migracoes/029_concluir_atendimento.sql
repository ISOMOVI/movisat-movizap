-- ============================================================================
-- MoviZap — migração 029: concluir atendimento
--
-- Decisões do usuário em 25/08:
--   1. "encerrar" passa a se chamar CONCLUIR ATENDIMENTO;
--   2. ao concluir, a conversa VOLTA PARA "SEM DONO";
--   3. concluir vale mesmo com outras pessoas dentro -- sair da conversa é
--      que deixa ela só com quem estiver nela;
--   4. quem foi convidado SAI JUNTO no fechamento;
--   5. a tela inicial passa a mostrar "concluídos por mim" e "pela equipe",
--      por período.
--
-- ----------------------------------------------------------------------------
-- 🚨 SOLTAR O DONO SEM GRAVAR QUEM CONCLUIU APAGARIA O DESFECHO
--
-- Hoje `encerrar()` deixa `atendente_id` como está, e é dele que sai o nome de
-- quem atendeu. Se a conversa passa a voltar para "sem dono" (decisão 2) e não
-- houver outro lugar guardando o autor do fechamento, "concluídos por mim"
-- deixa de ser calculável -- e o mini-CRM da decisão 5 nasce sem dado.
--
-- Por isso as duas coisas são UMA migração só: `resolvida_por` é a condição de
-- soltar o dono, não um extra.
--
-- ⚠️ ON DELETE não se aplica: atendente nunca é apagado, é desativado. A FK
-- é sem cláusula de propósito -- se um dia alguém tentar apagar a linha, o
-- banco recusa, que é o comportamento certo.
--
-- ⚠️ AS 3 CONVERSAS JÁ RESOLVIDAS FICAM COM `resolvida_por` NULO. Não dá para
-- descobrir quem fechou: a informação nunca foi gravada. Preencher com o
-- `atendente_id` atual seria chute -- o dono da conversa não é necessariamente
-- quem a concluiu. A tela lê NULL como "não registrado", que é a verdade.
--
-- ----------------------------------------------------------------------------
-- `sem_identificacao` ENTRA NO VOCABULÁRIO (decisão do usuário em 25/08)
--
-- Pedido: classificar contato em Clientes, Fornecedores, Técnicos, Teste e
-- Sem-identificação, para o interruptor de IA/bot por tipo. Os quatro
-- primeiros já existiam (001 e 023); faltava o quinto.
--
-- 🚨 NÃO CONFUNDIR COM A CONVERSA SEM CADASTRO. São 211 conversas com
-- `contato_id IS NULL` -- essas não têm linha em `contato` para receber
-- marcação nenhuma, e continuam sendo tratadas à parte. `sem_identificacao` é
-- para o contato que EXISTE na base e ninguém sabe o que é.
--
-- ⚠️ NINGUÉM É RECLASSIFICADO AQUI. Como na 023: o vocabulário cresce, a base
-- não se mexe. Hoje são 1.750 `cliente` e 4 `lead`, e o 1.750 mede uma
-- constante no `sync._gravar_contato`, não a realidade. Quem classifica é
-- gente, na CAD_1.2.
-- ============================================================================

ALTER TABLE conversa ADD COLUMN IF NOT EXISTS resolvida_por bigint
    REFERENCES atendente(id);

COMMENT ON COLUMN conversa.resolvida_por IS
    'Quem concluiu o atendimento. Gravado ANTES de soltar atendente_id, que '
    'volta a NULL no fechamento. NULL nas conversas fechadas antes de 25/08.';

-- A tela inicial conta desfecho por pessoa e por período: sem índice, isso
-- vira varredura da tabela inteira a cada 60 s (o intervalo do relógio da INI).
CREATE INDEX IF NOT EXISTS ix_conversa_desfecho
    ON conversa (resolvida_por, resolvida_em DESC)
    WHERE resolvida_em IS NOT NULL;

ALTER TABLE contato DROP CONSTRAINT IF EXISTS contato_relacao_check;
ALTER TABLE contato ADD CONSTRAINT contato_relacao_check
    CHECK (relacao IN ('cliente', 'fornecedor', 'parceiro', 'tecnico',
                       'lead', 'colaborador', 'teste', 'sem_identificacao'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('029', now(), 'conversa.resolvida_por e relacao sem_identificacao');
