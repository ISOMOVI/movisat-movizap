-- ============================================================================
-- MoviZap — migração 077: o KM do técnico (origem, distância e o cache da rota)
--
-- 🔵 Pedido dele em 26/10: *"na parte de agendamento do tecnico: proponha no
-- deslocamento uma calculadora km técnico que pode abrir outro modal para
-- calcular, dai o endereço do tecnico sempre fica preenchido conforme o
-- ultimo -- Por exemplo, na primeira vez colocamos o KM de origem e fica salvo
-- para proximas, se for alterado, permanece alterado"*. E, quando perguntado
-- de onde sai a distância: *"o km é o calculo a ser feito, é a informação a
-- ser encontrada. Hoje é feita na mão via 'rotas' do google e dai esse KM é
-- inserido manualmente"*.
--
-- 🚨 O PONTO DE PARTIDA, MEDIDO EM 26/10: o KM já é a linha que paga o
-- deslocamento (`KM DESLOCAMENTO`, unidade `km`, R$ 1,00/km), e os três
-- orçamentos emitidos têm 77, 77 e 15 km -- **digitados à mão**. Não existia
-- cálculo de distância em lugar nenhum do projeto, nem endereço de técnico em
-- tabela nenhuma: no `information_schema`, as únicas colunas `cep`/`logradouro`
-- do schema eram as de `agendamento`. E a ponte do FPSL expõe do técnico só
-- `{tecnico_id, nome, email, excluido, chave}` -- o Harmonit também não dá.
--
-- 🚨 AS TRÊS COISAS AQUI TÊM TEMPOS DE VIDA DIFERENTES, e é por isso que são
-- três e não uma:
--
--   1. `tecnico_origem` é MEMÓRIA, e vale "agora". Uma linha por técnico,
--      sobrescrita. É a frase dele ao pé da letra: *"fica salvo para
--      proximas, se for alterado, permanece alterado"* -- ou seja, um
--      sobrescrever, não um histórico.
--      ⚠️ NÃO É CADASTRO. Ninguém digita isto num formulário de cadastro:
--      ela é escrita pelo uso, quando a calculadora roda. Cadastro é coisa
--      que alguém tem de manter, e o projeto já tem 117 contatos de técnico
--      sem cadastro no Harmonit para provar o que acontece quando ninguém
--      mantém.
--
--   2. `agendamento.origem_endereco` e `agendamento.km` são RETRATO, e valem
--      "naquele dia". Se o técnico mudar de endereço, a memória muda e o
--      compromisso antigo continua dizendo de onde se cobrou. É o mesmo
--      desenho do `tipo_nome` da migração 072 (*"retrato do momento do
--      agendamento"*).
--      ⚠️ Aqui é a LINHA de texto, não sete colunas: a origem estruturada
--      vive na memória, e o compromisso só precisa do que foi cobrado --
--      sete colunas aqui seriam a terceira cópia do mesmo endereço.
--
--   3. `rota_cache` é CACHE DE CONSULTA PAGA, e vale por um prazo.
--
-- 🚨 E O CACHE EM TABELA CONTRARIA UM PRINCÍPIO ESCRITO DA CASA, então a
-- objeção se responde aqui. O `movizap/cep.py` diz: *"Memória de processo, e
-- de propósito (...) Não vira tabela porque cache que sobrevive a deploy é
-- cache que guarda erro para sempre"*. Vale para o CEP, que é grátis. Aqui
-- muda o que importa:
--   · cada consulta de rota CUSTA, e o mesmo técnico vai ao mesmo cliente
--     muitas vezes -- cache de processo pagaria de novo a cada deploy;
--   · **só resultado BOM entra aqui.** Falha não é gravada, nunca: é
--     exatamente o "guardar erro para sempre" que o `cep.py` teme;
--   · `consultado_em` fica À VISTA, e quem lê aplica prazo. Rota muda (obra,
--     estrada nova), e cache sem data é mentira com cara de fato -- a mesma
--     razão pela qual a migração 076 guardou a situação COM a hora da leitura.
--
-- ⚠️ NADA AQUI É ESCRITO POR NINGUÉM ANTES DA TELA. A calculadora e a rota
-- são da mesma volta, mas as colunas nascem agora porque acrescentá-las depois
-- obrigaria a mexer em quem lê.
-- ============================================================================

BEGIN;

-- 1. A MEMÓRIA do endereço de origem de cada técnico ------------------------
--
-- A chave é o `contato` (o técnico, do lado do MoviZap), e não o
-- `harmonit_tecnico_id`: o vínculo com o Harmonit pode não existir, e técnico
-- sem vínculo também tem de onde sair. ⚠️ `ON DELETE CASCADE` porque sem o
-- contato esta linha não tem sujeito.
CREATE TABLE IF NOT EXISTS tecnico_origem (
  tecnico_contato_id bigint PRIMARY KEY
      REFERENCES contato(id) ON DELETE CASCADE,
  -- Os mesmos sete campos do endereço de destino (migração 073), com os mesmos
  -- limites: duas réguas para o mesmo endereço é uma delas mentindo.
  cep          varchar(8),
  logradouro   varchar(80),
  numero       varchar(10),
  bairro       varchar(60),
  cidade       varchar(50),
  uf           varchar(2),
  complemento  varchar(40),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tecnico_origem IS
  'Memória do último endereço de origem de cada técnico, escrita pelo uso da '
  'calculadora de KM. Uma linha por técnico, sobrescrita -- não é histórico '
  'nem cadastro.';

-- 2. O RETRATO no compromisso ------------------------------------------------
ALTER TABLE agendamento
  ADD COLUMN IF NOT EXISTS origem_endereco text,
  -- numeric(12,3) igual ao `orcamento_item.quantidade`: o km vai para lá como
  -- quantidade, e arredondar diferente nos dois lados faria o compromisso e o
  -- orçamento discordarem do mesmo deslocamento.
  ADD COLUMN IF NOT EXISTS km numeric(12,3);

COMMENT ON COLUMN agendamento.origem_endereco IS
  'De onde o técnico saiu, como linha de texto, no momento do agendamento. '
  'Retrato: a memória atual está em tecnico_origem.';
COMMENT ON COLUMN agendamento.km IS
  'Distância cobrada neste compromisso. Vai ao orçamento como quantidade da '
  'linha KM DESLOCAMENTO.';

-- 3. O CACHE da consulta paga -----------------------------------------------
--
-- A chave é o PAR de endereços normalizados (minúsculas, sem acento, sem
-- pontuação), não o texto cru: "Rua X, 123" e "rua x 123" são a mesma consulta,
-- e pagar duas vezes por isso seria desperdício silencioso.
CREATE TABLE IF NOT EXISTS rota_cache (
  origem_norm   text NOT NULL,
  destino_norm  text NOT NULL,
  km            numeric(12,3) NOT NULL CHECK (km >= 0),
  segundos      integer CHECK (segundos IS NULL OR segundos >= 0),
  -- 🚨 A HORA DA LEITURA, À VISTA. Ver o aviso do topo: cache sem data é
  -- mentira com cara de fato.
  consultado_em timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (origem_norm, destino_norm)
);

COMMENT ON TABLE rota_cache IS
  'Distância já consultada no serviço de rotas, por par de endereços '
  'normalizados. Só resultado bom entra; falha nunca. Quem lê aplica prazo '
  'sobre consultado_em.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('077', now(), 'km do tecnico: memoria da origem, retrato no compromisso e cache da rota');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT table_name FROM information_schema.tables
--    WHERE table_name IN ('tecnico_origem','rota_cache');
--     -- esperado: as duas
--
--   SELECT column_name, data_type FROM information_schema.columns
--    WHERE table_name = 'agendamento' AND column_name IN ('origem_endereco','km');
--     -- esperado: origem_endereco text, km numeric
--
--   SELECT count(*) FROM tecnico_origem;
--     -- esperado hoje: 0 -- a memória se escreve pelo USO da calculadora
--
--   SELECT count(*) FROM rota_cache;
--     -- esperado hoje: 0 -- e continua 0 enquanto não houver chave da API
-- ----------------------------------------------------------------------------
