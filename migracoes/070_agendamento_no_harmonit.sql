-- ============================================================================
-- MoviZap — migração 070: o agendamento também vai para o Harmonit
--
-- 🔵 Decisão 7 dele (19/10): o MoviZap é o dono do agendamento, e a escrita no
-- Harmonit é **2º passo, testada antes na Velasco**. Em 21/10 ele mandou
-- *"pode deixar ligado e seguir com o plano"*, depois do relatório.
--
-- 🚨 O QUE O TESTE NA OS 16991 MEDIU, e que desenha estas colunas:
--   · `POST /OrdemServico/AgendarTecnico` com `id: 0` **CRIA** -- nasceu o
--     agendamento 944767 (Aline, 23/10 09:00-11:00), conferido relendo a OS;
--   · com o `id` de um agendamento que já existe, a rota **RECUSA** com
--     `Erro ao alterar Evento: TecnicoJaAgendado`, e nada muda;
--   · `agendado` continua `false` depois de agendar -- esse campo NÃO quer
--     dizer "tem compromisso";
--   · a data vai em ISO e volta em `dd/mm/aaaa`.
--
-- 🚨 A ESCRITA NÃO PODE DERRUBAR O AGENDAMENTO. O dono é o MoviZap: se o
-- Harmonit recusar, o compromisso continua valendo aqui e o erro fica
-- GRAVADO, legível, na própria linha. Falha silenciosa viraria "achei que
-- tinha ido" -- que é o mesmo defeito do "Não perturbe" que não perturbava.
-- ============================================================================

BEGIN;

ALTER TABLE agendamento
    -- O id do compromisso DO LADO DE LÁ (o `agendamentoId` do Harmonit).
    -- Nulo = não foi (ou não tentou ainda).
    ADD COLUMN harmonit_agendamento_id bigint,
    -- Quando a escrita deu certo. Nulo com `harmonit_erro` preenchido é o
    -- caso "tentou e não foi".
    ADD COLUMN harmonit_em             timestamptz,
    -- A mensagem crua da recusa. ⚠️ Fica em texto porque a rota é crua: a
    -- única forma de descobrir um motivo novo é lê-lo.
    ADD COLUMN harmonit_erro           text;

-- 🚨 AS OS DO ORÇAMENTO NÃO ESTAVAM SENDO GUARDADAS. O PDF imprime
-- "Ordem(ns) de serviço(s)", e os números só existiam no pedido que gerou o
-- documento -- então remontar o mesmo orçamento (para reenviar, quando o
-- envio falha) produziria um papel DIFERENTE, com o mesmo número. Documento
-- numerado que muda de conteúdo é pior que documento que não sai.
-- Achado no primeiro uso real dele, em 21/10.
ALTER TABLE orcamento ADD COLUMN ordens_os bigint[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN orcamento.ordens_os IS
    'Os numeros de OS impressos neste orcamento. Guardados para o documento '
    'poder ser remontado identico -- ver reenviar() em movizap/orcamento.py.';

COMMENT ON COLUMN agendamento.harmonit_agendamento_id IS
    'agendamentoId no Harmonit, criado por POST /OrdemServico/AgendarTecnico. '
    'Nulo nao e defeito: o MoviZap e o dono do compromisso (decisao dele, 19/10).';

-- 🚨 O INTERRUPTOR DO SISTEMA MORA NO `config` (regra dele, CFG_7.1 Geral).
-- Nasce LIGADO porque foi isso que ele mandou em 21/10, depois do relatório
-- do teste na OS 16991 -- e não porque recurso novo nasça ligado: a régua
-- desta casa é o contrário.
INSERT INTO config (chave, valor, descricao, atualizado_em)
VALUES (
    'agendamento_escreve_harmonit', 'true',
    'Agendar no MoviZap tambem cria o compromisso na OS do Harmonit '
    '(POST /OrdemServico/AgendarTecnico, pela ponte do FPSL). 🔵 Ligado por '
    'decisao dele em 21/10. Desligado, o compromisso vive so no MoviZap e a '
    'OS e citada pelo numero -- que era o comportamento ate aqui.',
    now()
)
ON CONFLICT (chave) DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('070', now(), 'agendamento no Harmonit (rastro e interruptor) e as OS do orcamento');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'agendamento' AND column_name LIKE 'harmonit%';
--     -- esperado: harmonit_agendamento_id, harmonit_em, harmonit_erro
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'orcamento' AND column_name = 'ordens_os';  -- existe
--
--   SELECT valor FROM config WHERE chave = 'agendamento_escreve_harmonit';
--     -- esperado: true
--   SELECT versao FROM schema_migracao WHERE versao = '070';   -- 070
--
-- DESFAZER, se precisar:
--   ALTER TABLE agendamento DROP COLUMN harmonit_agendamento_id,
--                           DROP COLUMN harmonit_em,
--                           DROP COLUMN harmonit_erro;
--   ALTER TABLE orcamento DROP COLUMN ordens_os;
--   DELETE FROM config WHERE chave = 'agendamento_escreve_harmonit';
--   DELETE FROM schema_migracao WHERE versao = '070';
-- ----------------------------------------------------------------------------
