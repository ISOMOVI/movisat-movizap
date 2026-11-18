-- ============================================================================
-- MoviZap — migração 110: os serviços da ficha do técnico passam a ser os
--                         nomes dele, e as variantes de instalação entram
--
-- 🔵 DECISÕES DELE, 17/11: *"considere tbm inserir na ficha dos tecnicos"*,
--   com a lista em dez linhas (INSTALAÇÃO SIMPLES, COM BLOQUEIO, COM LEITOR
--   RFID, COM LEITOR BUTTON, CÂMERA, RETIRADA SIMPLES, RETIRADA COM ACESSORIO,
--   MANUTENÇÃO COM TROCA, MANUTENÇÃO SEM TROCA, SUBSTITUIÇÃO VEÍCULO PARA
--   OUTRO), *"e tirar as redundantes"*, com as *"mesmas regras das demais
--   sobre o valor zero"*. Perguntado sobre os três pontos que a lista deixava
--   em aberto, ele decidiu no mesmo dia:
--     · os quatro sem equivalente (Socorro, Laudo Técnico, Treinamento,
--       Acompanhamento) **ficam**;
--     · a substituição **mantém as duas pernas**, porque o FPSL gera DUAS OS
--       por placa e o orçamento precisa precificar cada uma;
--     · as cinco variantes de instalação **entram**, mesmo RFID e i-BUTTON já
--       existirem como MATERIAL da OS no Harmonit (6991 e 6984) -- as duas
--       coisas passam a conviver, por decisão dele.
--   Resultado: 15 serviços.
--
-- 🚨 RENOMEIA, NÃO RECRIA, e é isto que torna esta migração segura:
--   `tecnico_preco` aponta para `servico_tecnico(id)`. Renomear preserva o
--   preço; apagar e inserir de novo o perderia, porque o preço mora no id e
--   não no nome. A régua da casa já era *"desativar, nunca apagar"* (085).
--
-- 📏 MEDIDO ANTES (17/11), e é o que define o de-para abaixo:
--   · os dez do catálogo estão nos ids 1..10, com `ordem` igual ao id;
--   · existem SEIS preços em `tecnico_preco`, todos de UM técnico (contato
--     91041): ids 1=10000, 2=6000, 3=5000, 4=10000, 5=6000, 6=10000;
--   · `Socorro`, `Laudo Técnico`, `Treinamento` e `Acompanhamento` nunca
--     receberam um único preço -- e por isso mantê-los não custa nada;
--   · nenhum `tecnico_preco` tem valor 0 hoje.
--
-- ⚠️ A GRAFIA É A DELE, LITERAL, em maiúsculas. Isso deixa a tabela com caixa
-- mista ao lado dos quatro que ficaram (`Socorro`), e é de propósito:
-- "melhorar" o nome que ele escreveu é adivinhação, e a ficha mostra o nome
-- cru. Normalizar os quatro é decisão dele, não minha.
--
-- ⚠️ AS REGRAS DE VALOR ZERO NÃO MUDAM, e os novos entram nelas sem nada aqui:
-- linha ausente ≡ nulo ≡ *"não oferece"*; zero ≡ *"cobra zero"*, que é
-- cortesia e é um fato diferente de vazio; negativo continua recusado pelo
-- CHECK de 085; `precos_para_orcamento` leva só o que tem valor, e zero entra.
-- Serviço novo nasce SEM LINHA em `tecnico_preco`, que é exatamente
-- *"não oferece"* -- nenhum técnico ganha preço por esta migração.
-- ============================================================================

BEGIN;

-- ── 1. os seis que viram os nomes dele (o preço vai junto, pelo id) ─────────
-- 🚨 O NOME ANTIGO VAI NO `WHERE`: se o dado não for o que eu medi, o UPDATE
-- não acha a linha, e a guarda do fim derruba a transação inteira. Migração
-- que escreve no escuro é a que descobre o estrago depois.
UPDATE servico_tecnico SET nome = 'INSTALAÇÃO SIMPLES'
 WHERE id = 1 AND nome = 'Instalação';
UPDATE servico_tecnico SET nome = 'RETIRADA SIMPLES'
 WHERE id = 2 AND nome = 'Retirada';
UPDATE servico_tecnico SET nome = 'MANUTENÇÃO SEM TROCA'
 WHERE id = 3 AND nome = 'Manutenção Local';
UPDATE servico_tecnico SET nome = 'MANUTENÇÃO COM TROCA'
 WHERE id = 4 AND nome = 'Manutenção Troca';
-- As duas pernas da troca entre veículos, com o nome dele por extenso na
-- frente: na ficha elas aparecem lado a lado, e "Retirada"/"Instalação" soltas
-- seriam confundidas com os serviços de contrato que ficam logo acima.
UPDATE servico_tecnico SET nome = 'SUBSTITUIÇÃO VEÍCULO PARA OUTRO - RETIRADA'
 WHERE id = 5 AND nome = 'Substituição Retirada';
UPDATE servico_tecnico SET nome = 'SUBSTITUIÇÃO VEÍCULO PARA OUTRO - INSTALAÇÃO'
 WHERE id = 6 AND nome = 'Substituição Instalação';

-- ── 2. as cinco variantes novas ─────────────────────────────────────────────
-- ⚠️ `ON CONFLICT (nome) DO NOTHING` como em 085: migração que roda duas vezes
-- não pode criar serviço duplicado, e `nome` é UNIQUE.
-- ⚠️ `unidade` nasce 'un' pelo DEFAULT da 089. Nenhum destes é por km --
-- deslocamento continua sendo o `tecnico_ficha.km_valor_centavos`, que não é
-- um serviço do catálogo.
INSERT INTO servico_tecnico (nome, ordem) VALUES
    ('INSTALAÇÃO COM BLOQUEIO',      2),
    ('INSTALAÇÃO COM LEITOR RFID',   3),
    ('INSTALAÇÃO COM LEITOR BUTTON', 4),
    ('INSTALAÇÃO CÂMERA',            5),
    ('RETIRADA COM ACESSORIO',       7)
ON CONFLICT (nome) DO NOTHING;

-- ── 3. a ordem da tela, que é a ordem em que ele escreveu ───────────────────
-- As cinco instalações, as duas retiradas, as duas manutenções (COM antes de
-- SEM, como ele listou), as duas pernas da substituição, e por último os
-- quatro que ficaram.
UPDATE servico_tecnico SET ordem = CASE nome
    WHEN 'INSTALAÇÃO SIMPLES'                            THEN 1
    WHEN 'INSTALAÇÃO COM BLOQUEIO'                       THEN 2
    WHEN 'INSTALAÇÃO COM LEITOR RFID'                    THEN 3
    WHEN 'INSTALAÇÃO COM LEITOR BUTTON'                  THEN 4
    WHEN 'INSTALAÇÃO CÂMERA'                             THEN 5
    WHEN 'RETIRADA SIMPLES'                              THEN 6
    WHEN 'RETIRADA COM ACESSORIO'                        THEN 7
    WHEN 'MANUTENÇÃO COM TROCA'                          THEN 8
    WHEN 'MANUTENÇÃO SEM TROCA'                          THEN 9
    WHEN 'SUBSTITUIÇÃO VEÍCULO PARA OUTRO - RETIRADA'    THEN 10
    WHEN 'SUBSTITUIÇÃO VEÍCULO PARA OUTRO - INSTALAÇÃO'  THEN 11
    WHEN 'Socorro'                                       THEN 12
    WHEN 'Laudo Técnico'                                 THEN 13
    WHEN 'Treinamento'                                   THEN 14
    WHEN 'Acompanhamento'                                THEN 15
    ELSE ordem END;

-- ── 4. a guarda: ou o estado é o esperado, ou nada disto aconteceu ──────────
-- 🚨 RAISE DENTRO DA TRANSAÇÃO DESFAZ TUDO. É a diferença entre uma migração
-- que falha e uma que deixa o catálogo metade novo e metade velho -- e esta
-- mexe no nome de serviço que já tem preço gravado.
DO $$
DECLARE
    faltando text;
    sobrando text;
    n_precos integer;
BEGIN
    SELECT string_agg(e.nome, ', ') INTO faltando
      FROM (VALUES
        ('INSTALAÇÃO SIMPLES'), ('INSTALAÇÃO COM BLOQUEIO'),
        ('INSTALAÇÃO COM LEITOR RFID'), ('INSTALAÇÃO COM LEITOR BUTTON'),
        ('INSTALAÇÃO CÂMERA'), ('RETIRADA SIMPLES'),
        ('RETIRADA COM ACESSORIO'), ('MANUTENÇÃO COM TROCA'),
        ('MANUTENÇÃO SEM TROCA'),
        ('SUBSTITUIÇÃO VEÍCULO PARA OUTRO - RETIRADA'),
        ('SUBSTITUIÇÃO VEÍCULO PARA OUTRO - INSTALAÇÃO'),
        ('Socorro'), ('Laudo Técnico'), ('Treinamento'), ('Acompanhamento')
      ) AS e(nome)
     WHERE NOT EXISTS (SELECT 1 FROM servico_tecnico s WHERE s.nome = e.nome);
    IF faltando IS NOT NULL THEN
        RAISE EXCEPTION 'migração 110: ficaram faltando os serviços: %', faltando;
    END IF;

    -- Nenhum nome velho pode ter sobrado: sobrar significa que um UPDATE não
    -- achou a linha, e aí a ficha mostraria o serviço duas vezes com nomes
    -- diferentes.
    SELECT string_agg(nome, ', ') INTO sobrando
      FROM servico_tecnico
     WHERE nome IN ('Instalação', 'Retirada', 'Manutenção Local',
                    'Manutenção Troca', 'Substituição Retirada',
                    'Substituição Instalação');
    IF sobrando IS NOT NULL THEN
        RAISE EXCEPTION 'migração 110: nome antigo sobrou (UPDATE não achou): %', sobrando;
    END IF;

    -- 🚨 O PREÇO É O QUE NÃO PODE SE PERDER. Seis linhas medidas antes; o
    -- renomear não toca em `tecnico_preco`, então seis têm de continuar lá.
    SELECT count(*) INTO n_precos FROM tecnico_preco;
    IF n_precos < 6 THEN
        RAISE EXCEPTION 'migração 110: tinham 6 preços e sobraram % -- algo apagou preço', n_precos;
    END IF;
END $$;

COMMENT ON TABLE servico_tecnico IS
  'Catálogo de serviços do técnico, igual para todos. Os nomes são os dele (17/11, migração 110): 5 variantes de instalação, 2 de retirada, 2 de manutenção, as 2 pernas da substituição entre veículos, mais Socorro, Laudo Técnico, Treinamento e Acompanhamento. Desativar, nunca apagar.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('110', now(), 'servicos da ficha do tecnico com os nomes dele: 5 instalacoes, 2 retiradas, 2 manutencoes, 2 pernas da substituicao e os 4 que ficaram');

COMMIT;
