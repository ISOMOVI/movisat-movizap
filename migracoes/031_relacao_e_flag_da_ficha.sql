-- ============================================================================
-- MoviZap — migração 031: `relacao` é flag da ficha, e o sync não escreve nela
--
-- Decisão do usuário em 25/08: *"o sync não usará esse campo, o sync usa o
-- número; o que pedi foi um flag de tipo no cadastro, somente será usado para
-- regra de automação boas vindas"*.
--
-- ----------------------------------------------------------------------------
-- 🚨 O SYNC ESCREVIA, E ERA DAÍ QUE VINHA O NÚMERO QUE NÃO MEDIA NADA
--
-- `sync._gravar_contato` tinha `'cliente'` LITERAL na lista de valores do
-- INSERT. Não era regra de negócio: era uma constante escrita no código em
-- 06/08, quando `relacao` ainda não tinha dono. Resultado medido em 25/08:
-- 1.750 dos 1.754 contatos dizem "cliente" sem que ninguém tenha classificado
-- nenhum deles.
--
-- ⚠️ O `ON CONFLICT DO UPDATE` já NÃO tocava em `relacao`, e continua assim --
-- é o que faz a marcação de uma pessoa sobreviver ao sync de amanhã. O que
-- muda é só a criação: agora ela nasce com o DEFAULT.
--
-- ----------------------------------------------------------------------------
-- O DEFAULT PASSA A SER `sem_identificacao`
--
-- Era `'lead'` desde a migração 001. `lead` é uma AFIRMAÇÃO -- "é alguém que
-- ainda não comprou" --, e contato que acabou de nascer não sustenta
-- afirmação nenhuma. `sem_identificacao` é a ausência de afirmação, e é o que
-- o usuário chamou de "como ele vem nativo".
--
-- ----------------------------------------------------------------------------
-- 🚨 OS 1.750 QUE JÁ ESTÃO LÁ NÃO SÃO TOCADOS
--
-- Reclassificar 1.754 linhas de cadastro é mexer em dado, e o usuário não
-- pediu. O que ele pediu foi o flag e o fim da escrita pelo sync -- é isso que
-- esta migração faz.
--
-- ⚠️ A CONSEQUÊNCIA, PARA QUEM FOR LIGAR A AUTOMAÇÃO: enquanto esses 1.750
-- disserem "cliente", ligar boas-vindas para `cliente` alcança praticamente a
-- base inteira. Por isso a marcação em lote (CAD_1.2) vem ANTES do
-- interruptor por tipo, e não depois. Está na ordem dos blocos.
-- ============================================================================

ALTER TABLE contato ALTER COLUMN relacao SET DEFAULT 'sem_identificacao';

COMMENT ON COLUMN contato.relacao IS
    'Flag de tipo na ficha da pessoa. Marcado por gente, na CAD_1.2. O sync '
    'NÃO escreve nem atualiza: ele casa por número. Consumido pela regra de '
    'automação (IA/bot/boas-vindas) por tipo de contato.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('031', now(), 'relacao e flag da ficha: default sem_identificacao');
