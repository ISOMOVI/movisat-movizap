-- ============================================================================
-- MoviZap — migração 012: o telefone que nasce no atendimento
--
-- O painel lateral deixa o atendente dizer "este número é deste cliente" no
-- meio da conversa. Esse telefone precisa de uma origem própria.
--
-- ----------------------------------------------------------------------------
-- POR QUE NÃO REUSAR `manual`
--
-- `manual` já existe e significa "não veio do sync". Serviria. Mas as duas
-- coisas têm confiança diferente:
--
--   `manual`       alguém digitou olhando para o cadastro;
--   `atendimento`  o atendente afirmou enquanto falava com a pessoa.
--
-- E há um motivo prático: `atendimento` é o único jeito de MEDIR se a gaveta
-- está consertando a base. 483 dos 944 clientes ativos (51%) estão fora do
-- alcance por cadastro incompleto; contar quantos telefones passaram a existir
-- pelo atendimento é o número que diz se o desenho funcionou.
--
-- 🚨 ORIGEM NÃO SE PREENCHE DEPOIS. Se os dois nascerem como `manual`, separá-
-- los em janeiro exige adivinhar quem digitou o quê -- e não vai dar. Por isso
-- o valor entra agora, antes do primeiro registro, e não quando a pergunta
-- aparecer.
--
-- ⚠️ Este CHECK é contrato, e foi ele que recusou o primeiro vínculo hoje --
-- corretamente. A tabela se defendeu de um valor que ninguém tinha combinado.
-- ============================================================================

ALTER TABLE contato_telefone DROP CONSTRAINT contato_telefone_origem_campo_check;

ALTER TABLE contato_telefone ADD CONSTRAINT contato_telefone_origem_campo_check
    CHECK (origem_campo = ANY (ARRAY[
        -- vindos do sync do Harmonit, com o nome do campo de lá
        'telefone', 'telefone2', 'celular',
        -- verificação de WhatsApp e digitação no cadastro
        'whatsapp', 'manual',
        -- vínculo feito na gaveta, durante a conversa (10/08)
        'atendimento'
    ]));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('012', now(), 'origem_campo aceita telefone nascido no atendimento')
ON CONFLICT (versao) DO NOTHING;
