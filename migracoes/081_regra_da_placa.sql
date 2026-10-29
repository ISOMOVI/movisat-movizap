-- ============================================================================
-- MoviZap — migração 081: o rastro da regra da placa
--
-- 🔵 Regra dele, 29/10: *"só é possível abrir chamados para placas ativas na
-- weso. o match é basicamente de 100% mesmo. essa é a regra"*.
--
-- A regra é cobrada na rota de envio: placa informada que não está ativa na
-- WESO é recusada, com frase que a pessoa lê.
--
-- 🚨 MAS A CONFERÊNCIA DEPENDE DE OUTRO SERVIÇO (a ponte do FPSL, que é quem
-- tem a base da WESO), e indisponibilidade NOSSA não pode barrar o chamado do
-- cliente. Quando a ponte não responde, o envio PASSA -- e é esta coluna que
-- registra que passou sem conferir, para quem atende saber que aquela placa
-- não foi verificada.
--
-- ⚠️ NULO TEM SIGNIFICADO, e são dois: a solicitação não informou placa, ou o
-- formulário não tem campo de placa. `true` = conferida e ativa.
-- `false` = **não deu para conferir**, e não "placa inativa" -- placa inativa
-- nunca é gravada, porque a rota recusa antes.
-- ============================================================================

BEGIN;

ALTER TABLE formulario_solicitacao
    ADD COLUMN IF NOT EXISTS placas_conferidas boolean;

COMMENT ON COLUMN formulario_solicitacao.placas_conferidas IS
    'A regra dele (29/10): chamado so para placa ativa na WESO. true = as '
    'placas desta solicitacao foram conferidas e estao ativas. false = a '
    'ponte do FPSL nao respondeu e o envio passou SEM conferir -- nao e '
    '"placa inativa", que a rota recusa antes de gravar. NULO = sem placa '
    'informada.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('081', now(), 'rastro da regra da placa: se as placas do chamado foram conferidas na WESO');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--   SELECT placas_conferidas, count(*) FROM formulario_solicitacao
--    GROUP BY 1;
--     -- esperado hoje: 1 linha, NULO (a solicitacao 39, de teste, sem placa)
-- ----------------------------------------------------------------------------
