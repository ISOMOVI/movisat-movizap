-- ============================================================================
-- MoviZap — migração 072: o TIPO da OS no compromisso
--
-- 🔵 Ponta 1 do plano de Agendamentos (§7.4): o cabeçalho da mensagem imprime
-- hoje a palavra `(SERVIÇO)` literal, onde o plano pede `(TIPO DA OS)`. 🚨 É a
-- ÚNICA das quatro pontas que sai para o cliente.
--
-- 🚨 RETRATO, COMO A PLACA DO LADO. O nome do tipo é gravado aqui no momento
-- do agendamento, e não consultado quando a mensagem é montada. Três razões,
-- todas medidas:
--   · a mensagem sai de uma tela que o operador está olhando, e o nome do tipo
--     não vale uma ida ao FPSL + Harmonit no meio do clique;
--   · a `agendamento_os` já guarda a placa pelo mesmo motivo desde a 069 --
--     fazer diferente com o tipo criaria duas políticas na mesma tabela;
--   · a OS pode ser reclassificada depois, e a mensagem que já saiu falava do
--     tipo de então. Retrato é o dado honesto.
--
-- 🚨 NULO É O CASO COMUM, E É RESPOSTA, NÃO FALHA. A lista de tipos do
-- Harmonit (`/TipoOrdemServico/ObterListaTipoOrdemServico`) tem **5 tipos**,
-- que cobrem **374 das 547** OS não excluídas do FPSL. As outras **173** estão
-- em **nove** ids fora da lista (57, 76, 73, 72, 55, 77, 75, 576, 814) --
-- tipos que o Harmonit removeu ou renomeou; o FPSL já registrava o caso do 55
-- desde 14/08 (`os_router._resolver_cabecalho_por_nome`: *"id fixo em código
-- apodrece em silêncio"*). Medido em 21/10, antes de escrever.
--
-- ⚠️ Para essas, o cabeçalho **OMITE o segmento** em vez de imprimir número ou
-- rótulo inventado. Tela que mente é defeito, e o cliente não sabe o que é
-- "tipo 57".
--
-- ⚠️ SEM `NOT NULL` e SEM DEFAULT: o compromisso não deixa de existir por
-- falta do nome do tipo, e as linhas que já estão no ar não têm esse dado --
-- preencher retroativamente seria inventar retrato de uma data em que o
-- dicionário não existia.
-- ============================================================================

BEGIN;

ALTER TABLE agendamento_os ADD COLUMN IF NOT EXISTS tipo_nome text;

COMMENT ON COLUMN agendamento_os.tipo_nome IS
    'Nome do tipo da OS no Harmonit, RETRATO do momento do agendamento. '
    'Nulo quando o tipo nao esta na lista de tipos do Harmonit (173 de 547 OS '
    'em 21/10, nove ids fora da lista) -- e nesse caso o cabecalho da mensagem '
    'OMITE o segmento, em vez de imprimir numero ou rotulo inventado.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('072', now(), 'tipo da OS no compromisso, para o cabecalho da mensagem');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT column_name, data_type, is_nullable
--     FROM information_schema.columns
--    WHERE table_name = 'agendamento_os' AND column_name = 'tipo_nome';
--     -- esperado: text, YES
--
--   SELECT count(*) FILTER (WHERE tipo_nome IS NULL) AS sem_nome, count(*)
--     FROM agendamento_os;
--     -- esperado hoje: as 3 linhas existentes sem nome (nasceram antes disto)
-- ----------------------------------------------------------------------------
