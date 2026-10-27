-- ============================================================================
-- MoviZap — migração 078: de onde o agente lê as gravações, e o canal de volta
--
-- 🔵 Pedido dele em 26/10: *"veja se da para atualizar do lado de ca para os
-- computadores o local de coleta das ligações gravadas, por exemplo, da claudia
-- está em: REC da Claudia diz sem comunicação · Caminho de busca dela é: user,
-- lenovo, one drive, backups, área de trabalho"*. E o desenho que ele mandou
-- depois: *"que permita inserir mais endereços por aqui ou buscar pelo nome da
-- pasta, pedindo permissão ao instalar"*.
--
-- 🚨 O PONTO DE PARTIDA, MEDIDO EM 26/10:
--   · a pasta é **100% derivada** do `MicroSIP.ini` (`Settings.recordingPath`),
--     e se ele estiver vazio o agente CHUTA `Desktop\Recordings` -- um palpite
--     que o próprio código marca como *"HIPOTESE a medir no PC da Claudia"*,
--     porque com OneDrive a Área de Trabalho muda de lugar;
--   · **não existe canal de configuração VPS -> agente**: o batimento devolve
--     `{ok, ramal, servidor_em}` e o agente **descarta a resposta**;
--   · o aviso *"pasta de gravacoes ainda nao existe"* é gerado **no PC** e
--     **não diz ONDE procurou** -- por isso é impossível ver pelo painel que o
--     caminho calculado está errado;
--   · **6 dos 7 PCs** estavam com `gravacao automatica desligada`.
--
-- 🚨 AS DUAS COLUNAS DE DIAGNÓSTICO VÊM ANTES DO CANAL DE VOLTA, e a ordem é o
-- desenho: sem saber ONDE o agente procurou, mandar um caminho novo é adivinhar
-- duas vezes. `pasta` e `pasta_origem` são o que transforma "sem comunicação"
-- em diagnóstico.
--
-- ⚠️ `pasta_origem` é COMO a pasta foi decidida, não uma frase livre: é o que
-- distingue "ele leu do .ini" de "ele chutou". O CHECK abaixo é a lista
-- fechada, e nasce da ordem de precedência que o agente passa a seguir.
--
-- 🚨 `pastas_extra` É INSTRUÇÃO QUE SAI DAQUI E VIRA LEITURA DE DISCO ALHEIO.
-- O que impede estrago mora **no PC** (caminho só dentro do perfil do usuário
-- ou de uma raiz de OneDrive, e só `.mp3`/`.wav` sobem) -- aqui fica só o
-- pedido. É o oposto do padrão da casa ("quem barra é o backend"), e tem de
-- ser: o backend do risco, neste caso, é o agente.
--
-- ⚠️ NADA AQUI VALE NOS PCs ANTES DO AGENTE `0.7`. Os 7 rodam `0.4`, e o
-- agente **não se atualiza sozinho**. As colunas nascem agora porque o lado da
-- VPS (rota, tela, teste) é o que dá para fazer sem tocar em máquina nenhuma.
-- ============================================================================

BEGIN;

ALTER TABLE agente_ligacao
  -- O caminho que o agente está realmente observando, como ele o resolveu.
  ADD COLUMN IF NOT EXISTS pasta text,
  -- Como a pasta foi decidida. Lista fechada = a tela pode explicar cada caso
  -- em texto; frase livre viraria 7 variações do mesmo recado.
  ADD COLUMN IF NOT EXISTS pasta_origem text,
  -- Se a gravação automática do MicroSIP está ligada, dito pelo PC.
  -- ⚠️ Três estados, não dois: NULL = o PC não informou (agente velho).
  ADD COLUMN IF NOT EXISTS auto_gravacao boolean,
  -- 🚨 Os caminhos que a VPS manda tentar, em ordem. Vazio = não interfere.
  ADD COLUMN IF NOT EXISTS pastas_extra text[] NOT NULL DEFAULT '{}';

ALTER TABLE agente_ligacao
  DROP CONSTRAINT IF EXISTS ck_agente_pasta_origem;
ALTER TABLE agente_ligacao
  ADD CONSTRAINT ck_agente_pasta_origem CHECK (
    pasta_origem IS NULL OR pasta_origem IN (
      'vps',        -- veio de `pastas_extra`: alguém mandou daqui
      'escolhida',  -- a pessoa confirmou na instalação
      'ini',        -- `recordingPath` do MicroSIP.ini
      'relativa',   -- `recordingPath` relativo, resolvido contra o .ini
      'busca',      -- achada procurando pelo NOME da pasta
      'palpite'     -- o chute antigo. 🚨 Ver o aviso: é o que some no 0.7
    )
  );

COMMENT ON COLUMN agente_ligacao.pasta IS
  'Onde o agente procura as gravações, como ele resolveu no último batimento.';
COMMENT ON COLUMN agente_ligacao.pasta_origem IS
  'COMO a pasta foi decidida: vps > escolhida > ini > relativa > busca. '
  '"palpite" é o comportamento de até o agente 0.6 e sai no 0.7.';
COMMENT ON COLUMN agente_ligacao.auto_gravacao IS
  'Gravacao automatica do MicroSIP, dita pelo PC. NULL = nao informou.';
COMMENT ON COLUMN agente_ligacao.pastas_extra IS
  'Caminhos que a VPS manda o agente tentar, em ordem. Vencem o .ini. '
  'As travas (dentro do perfil, so mp3/wav) moram NO PC.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('078', now(), 'agente de ligacoes: onde procura a gravacao, e o canal de volta da VPS');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'agente_ligacao'
--      AND column_name IN ('pasta','pasta_origem','auto_gravacao','pastas_extra');
--     -- esperado: as quatro
--
--   SELECT ramal, pasta, pasta_origem, auto_gravacao, pastas_extra
--     FROM agente_ligacao WHERE revogado_em IS NULL ORDER BY ramal;
--     -- esperado HOJE: pasta/origem/auto nulos nos 7 e pastas_extra vazio --
--     -- os PCs rodam 0.4 e não sabem mandar isso. Nulo aqui significa
--     -- "agente velho", e a tela tem de dizer isso em vez de "sem pasta".
-- ----------------------------------------------------------------------------
