-- ============================================================================
-- MoviZap — migração 085: a ficha do técnico, os serviços e o preço de cada um
--
-- 🔵 Pedido dele em 04/11: *"no Movizap, abaixo de 'orçamentos' vamos propor
-- uma tela CRUD dos tecnicos. Sabemos que o acesso de fato deles ao harmonit é
-- feito como usuario do sistema, então esses dados só vamos trazer mesmo. mas
-- vamos, nessa aba ter uma ficha de cada 1. como no formulario de
-- credenciamento (...) Também ali que iremos colocar o endereço fixo que
-- aparecerá na tela de calculo de KM (...) Dentro vamos colocar uma tabela de
-- preço por serviços que ele oferece, padrão a todos (...) Dai o cadastro do
-- tecnico e validação dele passará por essa tela."*
--
-- 🚨 ESTA MIGRAÇÃO CONTRARIA, DE PROPÓSITO, O AVISO DA 077. Lá está escrito:
-- *"⚠️ NÃO É CADASTRO. Ninguém digita isto num formulário de cadastro: ela é
-- escrita pelo uso (...) Cadastro é coisa que alguém tem de manter, e o
-- projeto já tem 117 contatos de técnico sem cadastro no Harmonit para provar
-- o que acontece quando ninguém mantém."* O aviso continua verdadeiro: é a
-- razão pela qual a 077 não inventou cadastro sozinha. O que mudou em 04/11 é
-- que ELE pediu o cadastro e disse quem mantém — a validação do técnico passa
-- por esta tela. Decisão dele (D5 do plano): *"o cadastro alimenta a memória,
-- pode tirá-la. Caso mudem na hora só servirá para aquele orçamento. Os demais
-- ja vem com o do cad."*
--
-- 🚨 O ESTADO MEDIDO ANTES DE ESCREVER (04/11), e nenhum número foi copiado de
-- lembrança:
--   · `contato` com `relacao = 'tecnico'`: **303**
--   · `tecnico_origem`: **0 linhas** — a calculadora nunca foi usada em
--     produção, porque a chave da API de rotas ainda não existe. A cópia do
--     passo 4 abaixo portanto move ZERO linhas hoje; ela está aqui porque a
--     migração não sabe quando vai rodar, e perder o único endereço de um
--     técnico por causa de uma ordem de execução seria um defeito silencioso.
--   · formulário `CREDENCIAMENTO` (id 335): **ativo**, 34 campos, e
--     **0 solicitações recebidas**. Ninguém se credenciou ainda — logo não há
--     passivo de dado a traduzir, e é por isso que o de-para dos serviços
--     (abaixo) não precisa converter nada.
--
-- 🚨 TRÊS TABELAS, PORQUE SÃO TRÊS COISAS COM DONOS DIFERENTES:
--   1. `servico_tecnico` é CATÁLOGO, e é **igual para todos** ("padrão a
--      todos", palavra dele). Vive em tabela e não em constante no código
--      porque serviço novo é dado: entra sem deploy.
--   2. `tecnico_ficha` é CADASTRO de uma pessoa jurídica prestadora, uma linha
--      por técnico, mantida à mão.
--   3. `tecnico_preco` é o cruzamento, e é o que muda com mais frequência —
--      *"com campo de valor por serviço que será atualizado na ficha de cada 1
--      manualmente"*.
--
-- ⚠️ A FICHA NÃO CRIA UMA ENTIDADE NOVA. A chave é o `contato` (o mesmo
-- `tecnico_contato_id` da 077 e o mesmo `tecnico_contato_id` que `agendamento`
-- e `orcamento` já apontam). Técnico virar uma segunda identidade faria o
-- orçamento emitido e a ficha falarem de dois sujeitos diferentes.
--
-- ⚠️ NADA AQUI NASCE PREENCHIDO para os 303 técnicos que já existem. Contato
-- de técnico sem ficha continua funcionando como hoje — a tela o lista e diz,
-- em texto, que ele não tem ficha. Criar 303 fichas vazias seria inventar 303
-- cadastros que ninguém conferiu.
-- ============================================================================

BEGIN;

-- 1. O CATÁLOGO de serviços ---------------------------------------------------
--
-- 🔵 Os dez nomes e a ordem são dele (04/11): *"Instalação, Retirada,
-- Manutenção Local, Manutenção Troca, Socorro, Laudo Técnico, Treinamento,
-- Acompanhamento"*, mais *"insira 'Substituição R.' e 'Substituição I.'"* —
-- confirmado por ele no mesmo dia como **Retirada** e **Instalação**, as duas
-- pernas da troca entre veículos. Ficam escritos por extenso: abreviação em
-- rótulo de tela é adivinhação para quem lê depois.
--
-- ⚠️ O de-para com o formulário de credenciamento NÃO EXISTE de propósito. As
-- seis perguntas que o formulário faz hoje (instalação simples / com bloqueio
-- / manutenção-correção / substituição no mesmo veículo / entre veículos /
-- remoção) não são estes dez, e ele decidiu que **os dez mandam**. Com zero
-- solicitação recebida, não há valor a converter; o que chegar aparece na
-- ficha como "o que ele respondeu", para quem credencia digitar o preço.
CREATE TABLE IF NOT EXISTS servico_tecnico (
  id     bigserial PRIMARY KEY,
  nome   varchar(60) NOT NULL UNIQUE,
  ordem  integer NOT NULL DEFAULT 0,
  -- Desativar, nunca apagar: `tecnico_preco` aponta para cá, e serviço
  -- apagado faria o preço antigo perder o assunto. É a régua do `operacao.py`.
  ativo  boolean NOT NULL DEFAULT true,
  criado_em timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE servico_tecnico IS
  'Catálogo de serviços que um técnico pode oferecer. Igual para todos os '
  'técnicos, por decisão dele em 04/11. Desativa-se, não se apaga.';

INSERT INTO servico_tecnico (nome, ordem) VALUES
  ('Instalação',               1),
  ('Retirada',                 2),
  ('Manutenção Local',         3),
  ('Manutenção Troca',         4),
  ('Substituição Retirada',    5),
  ('Substituição Instalação',  6),
  ('Socorro',                  7),
  ('Laudo Técnico',            8),
  ('Treinamento',              9),
  ('Acompanhamento',          10)
ON CONFLICT (nome) DO NOTHING;

-- 2. A FICHA ------------------------------------------------------------------
--
-- Os blocos e os campos seguem o formulário de credenciamento
-- (`forms.movisat.com.br/f/credenciamento-tecnico`), que é o que ele mandou
-- espelhar. O que o formulário pergunta e NÃO está aqui: as seis linhas de
-- preço (viraram `tecnico_preco`) e os quatro campos de página.
--
-- ⚠️ O ENDEREÇO SÃO SETE COLUNAS, com os MESMOS limites da 073 e da 077 —
-- duas réguas para o mesmo endereço é uma delas mentindo. O formulário de
-- credenciamento, ao contrário, pergunta o endereço como **uma linha** mais
-- cidade/estado/CEP; quem credencia é que distribui nos sete. É por isso que o
-- pré-preenchimento vindo da solicitação é conferido, não aceito no escuro.
CREATE TABLE IF NOT EXISTS tecnico_ficha (
  contato_id bigint PRIMARY KEY REFERENCES contato(id) ON DELETE CASCADE,

  -- 🔵 *"Dai o cadastro do tecnico e validação dele passará por essa tela."*
  -- Três estados e não dois: recusado é diferente de nunca ter existido, e
  -- apagar a ficha de quem foi recusado faria o mesmo CNPJ voltar amanhã sem
  -- ninguém lembrar por que saiu.
  estado varchar(12) NOT NULL DEFAULT 'candidato'
         CHECK (estado IN ('candidato', 'credenciado', 'recusado')),
  estado_em   timestamptz NOT NULL DEFAULT now(),
  estado_por  bigint REFERENCES atendente(id),
  estado_nota text,

  -- bloco EMPRESA
  nome_fantasia varchar(120),
  razao_social  varchar(120),
  cnpj          varchar(14),
  telefone_fixo varchar(20),
  email_geral   varchar(120),

  -- bloco RESPONSÁVEL
  responsavel_nome      varchar(80),
  responsavel_sobrenome varchar(80),
  cpf                   varchar(11),
  responsavel_celular   varchar(20),
  responsavel_email     varchar(120),

  -- bloco ENDEREÇO FIXO — os sete da 073/077, nos mesmos limites
  cep         varchar(8),
  logradouro  varchar(80),
  numero      varchar(10),
  bairro      varchar(60),
  cidade      varchar(50),
  uf          varchar(2),
  complemento varchar(40),

  -- bloco BANCO
  banco        varchar(60),
  agencia      varchar(20),
  conta        varchar(30),
  titular_tipo varchar(1) CHECK (titular_tipo IS NULL OR titular_tipo IN ('F', 'J')),

  -- bloco DESLOCAMENTO
  ponto_fixo         boolean,
  vai_ao_cliente     boolean,
  area_cobertura     varchar(120),
  cobra_deslocamento boolean,
  -- ⚠️ Em CENTAVOS e inteiro, como `orcamento.total_centavos`. Dinheiro em
  -- float é diferença de um centavo que ninguém explica.
  km_valor_centavos  integer CHECK (km_valor_centavos IS NULL OR km_valor_centavos >= 0),

  observacao text,

  -- 🔵 D3 dele: o formulário alimenta a tela *"mas não de forma exclusiva.
  -- Ainda é permitido fazer a mão."* NULL = ficha feita à mão, e é por isso
  -- que a coluna é anulável em vez de a tela ter dois caminhos de código.
  solicitacao_id bigint REFERENCES formulario_solicitacao(id) ON DELETE SET NULL,

  criado_em     timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tecnico_ficha IS
  'Cadastro do técnico prestador, no espelho do formulário de credenciamento. '
  'Uma linha por contato de técnico; contato sem linha é técnico sem ficha, e '
  'isso é estado válido. A validação (candidato/credenciado/recusado) é desta '
  'tela, por decisão dele em 04/11.';
COMMENT ON COLUMN tecnico_ficha.cep IS
  'Endereço FIXO, de cadastro. É a origem que a calculadora de KM abre '
  'preenchida. Alteração feita dentro do modal vale só para aquele cálculo.';
COMMENT ON COLUMN tecnico_ficha.solicitacao_id IS
  'A solicitação de credenciamento que originou a ficha, quando houve. NULL = '
  'cadastrada à mão.';

CREATE INDEX IF NOT EXISTS tecnico_ficha_estado_idx ON tecnico_ficha (estado);

-- 3. O PREÇO de cada serviço, por técnico -------------------------------------
--
-- 🔵 D2 dele: o valor é **CUSTO** — o que o técnico cobra da Movisat. O nome
-- da coluna diz isso, para que ninguém a leia um dia como preço de venda.
--
-- 🚨 LINHA AUSENTE E VALOR NULO SIGNIFICAM A MESMA COISA: ele não oferece
-- aquele serviço. É deliberado não ter um booleano "oferece" ao lado: dois
-- campos para o mesmo fato acabam discordando, e o que a tela precisa dizer é
-- *"não oferece"*, nunca R$ 0,00. Preço zero continua sendo possível e
-- diferente de ausente — serviço de cortesia é um fato, não um vazio.
CREATE TABLE IF NOT EXISTS tecnico_preco (
  contato_id     bigint NOT NULL REFERENCES contato(id) ON DELETE CASCADE,
  servico_id     bigint NOT NULL REFERENCES servico_tecnico(id),
  custo_centavos integer CHECK (custo_centavos IS NULL OR custo_centavos >= 0),
  atualizado_em  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (contato_id, servico_id)
);

COMMENT ON TABLE tecnico_preco IS
  'O que ESTE técnico cobra da Movisat por ESTE serviço, em centavos. Linha '
  'ausente ou custo nulo = não oferece o serviço; zero = cobra zero.';

-- 4. A MEMÓRIA DA 077 PASSA A SER ALIMENTADA PELO CADASTRO --------------------
--
-- 🔵 D5 dele: *"o cadastro alimenta a memória, pode tirá-la."* O `DROP TABLE
-- tecnico_origem` fica numa migração SEPARADA, depois de ele validar a tela:
-- derrubar aqui a tabela que `movizap/rotas.py`, a rota `/api/rotas/origem` e
-- o `ModalKm.vue` ainda leem deixaria a calculadora em erro entre esta
-- migração e o deploy do código. Enquanto isso, o que já estava gravado vira
-- ficha — como **candidato**, porque endereço escrito pelo uso é exatamente o
-- que ninguém conferiu ainda.
--
-- ⚠️ Hoje isto move 0 linhas (medido acima). Está escrito para o caso de não
-- mover.
INSERT INTO tecnico_ficha (contato_id, cep, logradouro, numero, bairro,
                           cidade, uf, complemento, observacao)
SELECT o.tecnico_contato_id, o.cep, o.logradouro, o.numero, o.bairro,
       o.cidade, o.uf, o.complemento,
       'Endereço herdado da memória da calculadora de KM (migração 077), '
       'gravado pelo uso em ' || to_char(o.atualizado_em, 'DD/MM/YYYY HH24:MI')
       || '. Confira antes de credenciar.'
  FROM tecnico_origem o
 WHERE EXISTS (SELECT 1 FROM contato c WHERE c.id = o.tecnico_contato_id)
ON CONFLICT (contato_id) DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('085', now(), 'ficha do tecnico: cadastro, catalogo de 10 servicos e preco de custo por servico');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT versao FROM schema_migracao WHERE versao = '085';
--     -- esperado: uma linha
--
--   SELECT nome, ordem FROM servico_tecnico ORDER BY ordem;
--     -- esperado: os 10, de Instalação a Acompanhamento
--
--   SELECT count(*) FROM tecnico_ficha;
--     -- esperado hoje: 0 (tecnico_origem estava vazia)
--
--   SELECT count(*) FROM contato WHERE relacao = 'tecnico';
--     -- 303 em 04/11, e nenhum ganhou ficha automaticamente
--
-- DESFAZER:
--
--   BEGIN;
--   DROP TABLE IF EXISTS tecnico_preco;
--   DROP TABLE IF EXISTS tecnico_ficha;
--   DROP TABLE IF EXISTS servico_tecnico;
--   DELETE FROM schema_migracao WHERE versao = '085';
--   COMMIT;
--     -- ⚠️ Isto apaga as fichas digitadas. `tecnico_origem` continua intacta
--     --    até a migração que a derruba, então o KM volta a funcionar como
--     --    hoje sem nenhum passo extra.
-- ----------------------------------------------------------------------------
