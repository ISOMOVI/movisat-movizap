-- ===========================================================================
-- 108 — `contato` e `ideias-sugestoes` passam a gerar card no Pós-venda
-- ===========================================================================
--
-- 🔵 12/11, dele: *"pode gerar card para Pós-venda"* e, confirmando a etapa,
-- *"isso, nova solicitação e pode seguir conforme a metodologia"*.
--
-- 📏 MEDIDO ANTES: eram os dois ÚNICOS formulários dos 16 com `painel` e
-- `etapa_destino_id` nulos. O envio deles entrava na lista de Solicitações e
-- não nascia card em painel nenhum -- ou seja, ninguém era avisado por uma
-- tela de que havia algo para fazer.
--
-- 🚨 A ETAPA É A 469, *Nova solicitação* da `PNL_1.3`, a MESMA do `ces` e do
-- `nps`. Não é descuido: a fila do Pós-venda começa ali, e inventar etapa
-- própria para dois formulários mexeria na lista de colunas, que é dele.
--
-- ⚠️ `gera_os` CONTINUA FALSO nos dois, como nos outros catorze. Sugestão de
-- melhoria e contato não abrem ordem de serviço no Harmonit; eles abrem CARD,
-- que é o que ele pediu em 12/11: *"a ideia é que os formulários virem cards
-- em todas as pipelines"*.
--
-- ⚠️ O `ideias-sugestoes` segue DESLIGADO (`ativo = false`), e esta migração
-- não o liga. Ligar é ato dele, e em 12/11 ele disse que não é demanda agora.
-- O destino fica pronto para quando for.
-- ===========================================================================

BEGIN;

UPDATE formulario
   SET painel = 'pos_venda',
       etapa_destino_id = 469,
       atualizado_em = now()
 WHERE slug IN ('contato', 'ideias-sugestoes')
   AND painel IS NULL
   AND etapa_destino_id IS NULL;

-- 🚨 A GUARDA: dois, e não um nem três. Se a etapa 469 deixar de existir ou
-- se alguém já tiver mexido num dos dois, a migração ABORTA em vez de deixar
-- metade feita.
DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n
      FROM formulario
     WHERE slug IN ('contato', 'ideias-sugestoes')
       AND painel = 'pos_venda'
       AND etapa_destino_id = 469;
    IF n <> 2 THEN
        RAISE EXCEPTION 'esperava 2 formularios apontando para a etapa 469, achei %', n;
    END IF;

    SELECT count(*) INTO n
      FROM pipeline_etapa
     WHERE id = 469 AND aba_id = 162 AND ativo;
    IF n <> 1 THEN
        RAISE EXCEPTION 'a etapa 469 (Nova solicitacao do pos-venda) nao esta ativa';
    END IF;
END $$;

-- ⚠️ `versao` é TEXTO nesta tabela, não inteiro, e o registro leva descrição:
-- é o padrão das 107 anteriores, conferido antes de escrever esta.
INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('108', now(),
        'contato e ideias-sugestoes geram card no pos-venda, etapa 469');

COMMIT;
