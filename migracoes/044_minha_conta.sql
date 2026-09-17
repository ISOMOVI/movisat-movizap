-- ============================================================================
-- MoviZap — migração 044: o 4º estado do atendente, e a foto dele
--
-- 🟢 Pedido do Rodrigo, trazido por ele em 15/09: status do atendente
-- (online / pausa / offline). 🔵 E o usuário em 17/09: *"central de perfil
-- 'minha conta' para foto de usuario, dados de perfil, tipo de envio"*.
--
-- 🚨 A COLUNA JÁ EXISTIA, E EU AFIRMEI DUAS VEZES QUE NÃO. O `atendente.estado`
-- nasceu na 001 com `disponivel`/`ausente`/`nao_perturbe` -- exatamente os três
-- valores que a memória dizia. Não apareceu nas minhas buscas porque se chama
-- `estado`, e eu procurei por `status`, `online`, `pausa` e `presenca`.
-- Fica a regra: **ausência se afirma lendo o `CREATE TABLE`, nunca por `grep`
-- de uma palavra que eu supus.**
--
-- 🚨 O QUE FALTAVA NÃO ERA A COLUNA, ERA O PRODUTO. Medido em 17/09: `estado`
-- aparece em UM lugar do código (`main.py`, modelo `AtendenteEntrada`), não
-- chega ao `/api/sessao/eu`, não é desenhado em tela nenhuma e não decide
-- nada. Coluna viva no banco e morta no produto -- por isso ele lembrava dela
-- e não a via.
--
-- ⚠️ `offline` É ESCOLHIDO, NÃO DEDUZIDO. Não é "sem sessão aberta": é a
-- pessoa dizendo "encerrei". Deduzir de atividade exigiria bater ponto por
-- requisição, e o painel fica aberto em aba esquecida o dia inteiro -- o
-- derivado mentiria mais do que informaria.
--
-- ⚠️ A FOTO GUARDA O CAMINHO, NUNCA OS BYTES. Mesma decisão da assinatura
-- (017) e da foto de contato (041): bytes no banco engordam backup e dump
-- para sempre. NULL = sem foto, e a tela cai nas iniciais do nome.
-- ============================================================================

BEGIN;

-- O CHECK é recriado, não alterado: Postgres não tem "ALTER CONSTRAINT" para
-- CHECK, e o nome é o que a 001 gerou por ser CHECK de coluna.
ALTER TABLE atendente DROP CONSTRAINT IF EXISTS atendente_estado_check;
ALTER TABLE atendente ADD CONSTRAINT atendente_estado_check
    CHECK (estado IN ('disponivel', 'ausente', 'nao_perturbe', 'offline'));

ALTER TABLE atendente ADD COLUMN IF NOT EXISTS foto TEXT;

COMMENT ON COLUMN atendente.estado IS
    'Presenca ESCOLHIDA pela pessoa: disponivel, ausente, nao_perturbe, '
    'offline. Nao e deduzida de sessao aberta.';

COMMENT ON COLUMN atendente.foto IS
    'Caminho do arquivo no disco, nunca os bytes. NULL = sem foto, a tela '
    'cai nas iniciais do nome.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('044', now(), 'atendente: 4o estado (offline) e foto de perfil');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d atendente
--   SELECT estado, count(*) FROM atendente GROUP BY estado;
--   -- aceita o novo:
--   --   UPDATE atendente SET estado='offline' WHERE id = <id>;  (e volta)
--   SELECT versao FROM schema_migracao WHERE versao = '044';   -- 044
--
-- DESFAZER:
--   UPDATE atendente SET estado='ausente' WHERE estado='offline';
--   ALTER TABLE atendente DROP CONSTRAINT atendente_estado_check;
--   ALTER TABLE atendente ADD CONSTRAINT atendente_estado_check
--       CHECK (estado IN ('disponivel','ausente','nao_perturbe'));
--   ALTER TABLE atendente DROP COLUMN foto;
--   DELETE FROM schema_migracao WHERE versao = '044';
-- ----------------------------------------------------------------------------
