-- ===========================================================================
-- MoviZap — migração 114: divergência não é uma coisa só, e reescrever
--                         às cegas desfaria trabalho de gente
-- ===========================================================================
--
-- 🚨 ESTA MIGRAÇÃO NASCEU DO ENSAIO A SECO DO AUDITOR, em 18/11, e corrige um
-- furo no desenho que eu só vi porque rodei contra a produção antes de ligar
-- a escrita.
--
-- O auditor leu 22 OS e achou duas divergências REAIS:
--
--     OS 17054: o painel diz 251   e o Harmonit diz 16490
--     OS 17114: o painel diz 15696 e o Harmonit diz 16490
--
-- E o histórico de passagens mostra o que elas são:
--
--     OS 17054: nós escrevemos 251   em 29/10, e NADA depois
--     OS 17114: nós escrevemos 15696 em 12/11, e NADA depois
--     16490 ("Analise de Equipamentos Retornados") NUNCA foi escrito por nós
--
-- 🚨 Ou seja: ALGUÉM AVANÇOU ESSAS OS DENTRO DO HARMONIT, depois da nossa
-- passagem. O ERP está certo e o nosso card está velho.
--
-- ⚠️ **E O ESCRITOR, COMO ESTAVA, IRIA REESCREVER A NOSSA COLUNA POR CIMA.** Ele
-- puxaria a OS 17054 de *"Analise de Equipamentos Retornados"* de volta para
-- *"Configurar equipamentos e Sistemas"* -- desfazendo, numa OS de cliente,
-- semanas de trabalho de uma pessoa que fez a coisa certa no sistema dela.
--
-- 🚨 A DIFERENÇA QUE FALTAVA, e ela é simples de dizer: **o valor que o ERP
-- mostra é um valor que NÓS já escrevemos, ou não?**
--
--   · é um valor NOSSO       -> a nossa escrita não chegou, ou a leitura dele
--                               atrasou. Aqui faz sentido reescrever.
--   · é um valor que nunca   -> alguém mexeu lá. **Nada a reescrever.** O card
--     escrevemos                é que tem de seguir o ERP, e o aviso serve
--                               para a pessoa saber que o painel estava atrás.
--
-- 🔵 E o que separa "atraso" de "escrita perdida" é TEMPO, com o número dele:
-- **1 hora**. O atraso medido na OS 17133 foi de ≈1h54 e se resolveu sozinho,
-- então abaixo de 1h não se mexe; acima, a escrita se perdeu de verdade.

BEGIN;

ALTER TABLE auditoria_os DROP CONSTRAINT auditoria_os_veredito;

ALTER TABLE auditoria_os ADD CONSTRAINT auditoria_os_veredito CHECK (
    veredito IN (
        -- ainda sendo avaliada nesta rodada
        'aberta',
        -- 🚨 o ERP mostra um valor NOSSO e a nossa escrita é recente (< 1h):
        -- é a leitura dele atrasada (OS 17133, 18/11). Não se mexe.
        'atraso',
        -- 🚨 o ERP mostra um valor NOSSO e a nossa escrita é ANTIGA (> 1h): a
        -- escrita se perdeu. É A ÚNICA QUE VAI PARA O ESCRITOR.
        'escrita_perdida',
        -- 🚨 o ERP mostra um valor que NUNCA escrevemos: alguém mexeu lá, e o
        -- ERP é quem está certo. Vira AVISO, nunca reescrita.
        'mudou_no_erp',
        -- as duas leituras discordaram entre si: leitura instável
        'nao_confirmada',
        -- o escritor tentou e o auditor releu e fechou verde
        'resolvida',
        -- os 3 grupos estouraram, ou recusa de negócio
        'desistiu'
    ));

COMMENT ON COLUMN auditoria_os.veredito IS
    'aberta = em avaliacao; atraso = o ERP mostra valor NOSSO e a escrita e '
    'recente (<1h), a leitura dele atrasou (OS 17133); escrita_perdida = valor '
    'NOSSO e escrita antiga (>1h), a UNICA que o escritor reescreve; '
    'mudou_no_erp = valor que nunca escrevemos, alguem mexeu la e o ERP esta '
    'certo -- vira aviso, nunca reescrita; nao_confirmada = as duas leituras '
    'discordaram; resolvida = o auditor releu e fechou verde; desistiu = 3 '
    'grupos estouraram ou recusa de negocio.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('114', now(), 'divergencia deixa de ser uma coisa so: valor que nunca escrevemos e mudanca de terceiro no ERP e NAO se reescreve -- o ensaio a seco mostrou que o escritor iria desfazer trabalho real em duas OS de cliente');

COMMIT;
