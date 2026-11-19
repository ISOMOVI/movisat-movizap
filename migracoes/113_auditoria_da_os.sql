-- ===========================================================================
-- MoviZap — migração 113: a auditoria da coluna do card contra a OS do Harmonit
-- ===========================================================================
--
-- 🔵 Desenho dele, 18/11: *"uma pode verificar e levantar, indicar os erros, e
-- disparar por outro que só vai reescrever, daí guardar os logs juntos para
-- evitar perca e depois devolve ao primeiro para validar e passar verde.
-- Assim podemos ter intervalo de escrita e tolerância maior de erros, pois não
-- estarão usando o pool, mas precisamos de uma red flag para as tentativas e
-- informação."*
--
-- 🚨 UMA TABELA, NÃO DUAS, e é a parte do pedido dele que mais importa:
-- *"guardar os logs juntos para evitar perca"*. O auditor levanta a
-- divergência e o escritor anota as tentativas **na mesma linha**. Log separado
-- por agente seriam duas metades de uma história, e a pergunta real -- *"esta
-- OS foi tentada quantas vezes e com que resposta?"* -- exigiria juntar as
-- duas à mão, todas as vezes.
--
-- 📏 MEDIDO EM 18/11, e os números do plano estavam velhos:
--     OS que são card ............ 633  (o plano dizia 505)
--     cache com mais de 1 dia .... 224  (o plano dizia 136)
--     leitura de OS, hoje ........ 151 a 296 ms de média por hora
--     chamadas por hora, de noite. 171, TODAS as horas
--
-- 🚨 A MADRUGADA NÃO ESTÁ LIVRE: a varredura do FPSL roda 24h por dia. O
-- auditor não encontra um ERP ocioso -- entra ao lado de um tráfego constante
-- que é, em sua maioria, sondas de número de OS que não existe. 🔵 Por isso a
-- hora escolhida por ele (03:00) é a hora com menos GENTE trabalhando, não com
-- menos tráfego.
--
-- ⚠️ E o auditor é barato: 633 OS × 2 leituras = 1.266 chamadas, ~3,4 min de
-- ERP. Cabe dentro do desperdício que já existe.

BEGIN;

CREATE TABLE auditoria_os (
    id              bigserial PRIMARY KEY,
    rodada          timestamptz NOT NULL DEFAULT now(),
    numero_os       bigint NOT NULL,

    -- Os dois lados, e a idade de cada um. 🚨 A IDADE ENTRA porque divergência
    -- entre um dado de agora e um de ontem não é divergência: é dado velho.
    coluna_nossa    integer,
    situacao_do_erp integer,
    lido_em         timestamptz,
    cache_de        timestamptz,

    -- 🚨 `atraso` É UM VEREDITO, NÃO UM ERRO, e esta coluna existe por causa da
    -- OS 17133 (18/11). Naquele dia a mesma rota do Harmonit devolveu 251 e,
    -- 31 segundos depois, 16488, sem nenhuma escrita no meio: das 11:17 às
    -- 11:42 ela respondia o valor que escrevemos às 09:42, ignorando o de
    -- 09:49. Um atraso de ≈1h54 que se resolveu sozinho.
    --
    -- ⚠️ Sem separar isto, o escritor reescreveria situação correta por cima de
    -- situação correta -- gastando exatamente o pool que a madrugada deveria
    -- poupar -- e a red flag avisaria sobre um problema que não existe.
    veredito        text NOT NULL DEFAULT 'aberta',

    -- O log do escritor, na mesma linha (o pedido dele).
    tentativas      integer NOT NULL DEFAULT 0,
    grupos          integer NOT NULL DEFAULT 0,
    ultimo_erro     text,
    escrito_em      timestamptz,

    -- O fechamento, que é SEMPRE do auditor relendo.
    fechada_em      timestamptz,
    fechada_como    text,

    CONSTRAINT auditoria_os_veredito CHECK (veredito IN (
        -- o auditor achou e a 2ª leitura confirmou: vai para o escritor
        'aberta',
        -- 🚨 o ERP devolveu um valor que NÓS escrevemos antes: é atraso de
        -- leitura, não erro. NÃO vai ao escritor e NÃO vira red flag.
        'atraso',
        -- a 2ª leitura não confirmou a 1ª: era leitura instável, não divergência
        'nao_confirmada',
        -- o escritor tentou e o auditor releu e fechou verde
        'resolvida',
        -- os 3 grupos estouraram, ou recusa de negócio: vira red flag
        'desistiu'
    )),
    CONSTRAINT auditoria_os_fechada_como CHECK (
        fechada_como IS NULL OR fechada_como IN ('igual', 'ainda_diferente'))
);

-- Uma linha ABERTA por OS: a rodada de amanhã não abre uma segunda para a
-- mesma divergência que ninguém fechou. 🚨 Sem isto, uma OS parada criaria uma
-- linha por noite e a red flag contaria o mesmo problema várias vezes.
CREATE UNIQUE INDEX auditoria_os_uma_aberta
    ON auditoria_os (numero_os)
 WHERE fechada_em IS NULL;

CREATE INDEX auditoria_os_rodada_idx ON auditoria_os (rodada DESC);
CREATE INDEX auditoria_os_veredito_idx ON auditoria_os (veredito)
 WHERE fechada_em IS NULL;

COMMENT ON TABLE auditoria_os IS
    'Divergencia entre a coluna do card e a situacao da OS no Harmonit. O '
    'auditor levanta e fecha; o escritor so anota tentativas na mesma linha '
    '(pedido dele: guardar os logs juntos para evitar perca).';
COMMENT ON COLUMN auditoria_os.veredito IS
    'aberta = confirmada em 2 leituras, vai ao escritor; atraso = o ERP '
    'devolveu valor que NOS escrevemos antes (OS 17133, 18/11), nao e erro; '
    'nao_confirmada = a 2a leitura discordou da 1a; resolvida = o auditor '
    'releu e fechou verde; desistiu = 3 grupos estouraram ou recusa de negocio.';
COMMENT ON COLUMN auditoria_os.cache_de IS
    'Quando o nosso lado foi lido. Divergencia entre um dado de agora e um de '
    'ontem nao e divergencia: e dado velho -- 224 das 633 OS estavam assim.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('113', now(), 'auditoria da coluna do card contra a situacao da OS no Harmonit: o auditor levanta e fecha, o escritor anota na mesma linha, e atraso de leitura e veredito proprio');

COMMIT;
