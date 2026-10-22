-- ============================================================================
-- MoviZap — migração 073: o endereço do compromisso, em campos separados
--
-- 🔵 Pedido dele, 21/10: *"a tela 3 precisa ter o campo com os dados de
-- endereço separados, para enviar sem erros no harmonit... sem os campos,
-- podem inserir de qqer jeito"*.
--
-- 🚨 OS CAMPOS SÃO OS DO HARMONIT, UM A UM, e não um desenho nosso. A OS do
-- Harmonit guarda o endereço em sete campos -- `cep`, `endereco`, `numero`,
-- `bairro`, `cidade`, `uf`, `complemento` (medido na OS 16991 em 21/10) --, e
-- a rota de escrita espera exatamente esses nomes. Inventar um formato aqui
-- obrigaria uma tradução no caminho, e tradução é onde o endereço se perde.
--
-- ⚠️ UMA DIFERENÇA DE NOME, DELIBERADA: o que o Harmonit chama de `endereco`
-- (a rua) aqui é `logradouro`, porque `agendamento.endereco` já existe desde a
-- 069 e é a LINHA MONTADA que sai na mensagem do cliente. As duas coisas
-- convivem: os campos são o dado, a linha é o texto.
--
-- 🚨 `endereco` CONTINUA SENDO A FONTE DA MENSAGEM, e segue preenchida: ela é
-- montada a partir dos campos quando eles existem. Trocar a mensagem para ler
-- os sete campos faria os compromissos antigos -- que só têm a linha --
-- saírem sem endereço, e eles são o único histórico que existe.
--
-- ⚠️ NADA É OBRIGATÓRIO. Em 30 OS amostradas no Harmonit em 21/10, **7 têm os
-- oito campos em branco**: exigir endereço estruturado impediria de agendar
-- justamente onde o cadastro está pior.
--
-- 🚨 OS TAMANHOS SÃO ESCOLHA NOSSA, e o teto do Harmonit NÃO é documentado. O
-- que se mediu nas 30 OS é o PISO -- logradouro 41, bairro 54, cidade 21,
-- número 4, complemento 9 --, e piso prova que cabe, não prova o limite. Estes
-- são folgados sobre o medido; se o Harmonit recusar, a recusa chega por
-- extenso e o número muda aqui.
-- ============================================================================

BEGIN;

ALTER TABLE agendamento
    ADD COLUMN IF NOT EXISTS cep         varchar(8),
    ADD COLUMN IF NOT EXISTS logradouro  varchar(80),
    ADD COLUMN IF NOT EXISTS numero      varchar(10),
    ADD COLUMN IF NOT EXISTS bairro      varchar(60),
    ADD COLUMN IF NOT EXISTS cidade      varchar(50),
    ADD COLUMN IF NOT EXISTS uf          varchar(2),
    ADD COLUMN IF NOT EXISTS complemento varchar(40);

COMMENT ON COLUMN agendamento.cep IS
    'CEP com 8 digitos, SEM mascara -- e como a OS do Harmonit o guarda '
    '(medido em 30 OS, 21/10). A doc deles mostra com mascara; o dado real '
    'vem sem, e gravar das duas formas criaria dois CEPs iguais e diferentes.';
COMMENT ON COLUMN agendamento.logradouro IS
    'A rua. 🚨 No Harmonit este campo chama-se `endereco`; aqui nao pode, '
    'porque `agendamento.endereco` e a LINHA MONTADA que sai na mensagem do '
    'cliente desde a migracao 069.';

-- 🚨 O RASTRO DA ESCRITA NA OS fica na mesma linha, como o do agendamento no
-- Harmonit (migração 070): sem isto, "o endereço foi para a OS?" só se
-- responderia abrindo o Harmonit.
ALTER TABLE agendamento
    ADD COLUMN IF NOT EXISTS endereco_os_em   timestamptz,
    ADD COLUMN IF NOT EXISTS endereco_os_erro text;

COMMENT ON COLUMN agendamento.endereco_os_erro IS
    'Por que o endereco NAO foi para a OS do Harmonit. 🚨 Nulo com '
    '`endereco_os_em` nulo quer dizer "nao tentou"; nulo com data quer dizer '
    '"foi". Os dois estados precisam ser distinguiveis -- um compromisso que '
    'nao tentou e um que conseguiu nao sao a mesma coisa.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('073', now(), 'endereco do compromisso em campos separados, e o rastro da escrita na OS');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT column_name, data_type, character_maximum_length
--     FROM information_schema.columns
--    WHERE table_name = 'agendamento'
--      AND column_name IN ('cep','logradouro','numero','bairro','cidade','uf',
--                          'complemento','endereco_os_em','endereco_os_erro');
--     -- esperado: as nove, todas anulaveis
--
--   SELECT count(*) FROM agendamento WHERE endereco IS NOT NULL;
--     -- a linha montada dos compromissos que ja existem continua intacta
-- ----------------------------------------------------------------------------
