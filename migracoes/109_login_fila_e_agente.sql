-- ============================================================================
-- MoviZap — migração 109: o LOGIN do dia manda na fila, o estado ganha hora,
--                         a cadeia de distribuição vira lista, e o agente de
--                         ligações passa a ter memória
--
-- 🔵 DECISÕES DELE, 13/11:
--   · *"a regra precisa verificar se está logada de fato. Online só fica
--     logado dentro da jornada"* e *"o foco é evitar enviar conversa para
--     operadora que não logou hoje"*;
--   · *"logar fora do turno não disponibiliza status e nem conversas"*;
--   · a fila em cadeia: Ludmila -> Erika -> Claudia;
--   · no chat interno, *"status a x minutos"* na frente do nome;
--   · no agente do MicroSIP, *"coletar IP e quando eles atualizarem ou mudar
--     a pasta não perdermos de vista"*, com senha padrão `movicall`.
--
-- 📏 MEDIDO ANTES (13/11), e é o que torna esta migração necessária:
--   · a Ludmila apareceu DISPONÍVEL sem ter logado, porque a borda das 08:00
--     põe `disponivel` em todo mundo que tem jornada;
--   · o único sinal de presença era `painel_visto_em`, que prova ABA ABERTA e
--     não pessoa: às 15:12 o carimbo dela era de um minuto antes, AFASTADA;
--   · não existe registro de login em lugar nenhum -- o token é JWT e morre na
--     virada do dia, e não há tabela de sessão;
--   · 7 dos 8 agentes de ligação estão na versão 0.4 e por isso não mandam
--     pasta nem `auto_gravacao`.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. A HORA EM QUE O ESTADO MUDOU
-- ----------------------------------------------------------------------------
--
-- 🚨 POR QUE COLUNA NOVA, E NÃO `atualizado_em`: aquela coluna é carimbada por
-- nome, foto, times e afastamento. Usá-la faria o chat interno dizer "online há
-- 2min" porque alguém salvou o cadastro da pessoa -- tela que mente (`M12`).
ALTER TABLE atendente ADD COLUMN IF NOT EXISTS estado_em timestamptz;

-- O retrato de agora é o melhor palpite que existe: ninguém sabe quando o
-- estado de cada um mudou, e `atualizado_em` é o limite superior.
-- ⚠️ Isso vale UMA vez, na migração. Daqui em diante quem carimba é o código.
UPDATE atendente SET estado_em = COALESCE(estado_em, atualizado_em, criado_em);

-- ----------------------------------------------------------------------------
-- 2. O LOGIN DE VERDADE
-- ----------------------------------------------------------------------------
--
-- 🚨 NULO QUER DIZER "NÃO LOGOU DESDE ESTA MIGRAÇÃO", e a régua da fila trata
-- isso como "não logou hoje". É deliberado: não dá para inventar um login que
-- ninguém registrou, e o preço de errar para o lado seguro é a fila pular quem
-- não logar hoje -- que é exatamente o que ele pediu.
ALTER TABLE atendente ADD COLUMN IF NOT EXISTS logou_em timestamptz;

COMMENT ON COLUMN atendente.logou_em IS
  'Último login de verdade (migração 109). A fila só entrega para quem logou hoje.';
COMMENT ON COLUMN atendente.estado_em IS
  'Quando o estado mudou (migração 109). Alimenta o "ausente há 30min" do chat interno.';

-- ----------------------------------------------------------------------------
-- 3. A CADEIA DA FILA VIRA LISTA ORDENADA
-- ----------------------------------------------------------------------------
--
-- 🚨 AS CHAVES ANTIGAS FICAM. `distribuicao_primeiro` e `distribuicao_reserva`
-- continuam gravadas e continuam sendo escritas pela tela de hoje; a lista
-- nasce DELAS. Apagar aqui deixaria a configuração órfã se o código novo
-- precisasse voltar atrás -- e voltar atrás com dado perdido não é voltar.
--
-- 🔵 O terceiro nome é decisão dele de 13/11: *"se ela tiver conversas e não
-- logar, nada muda ... mas se não logar, as novas conversas precisam seguir
-- para Erika, se a mesma logar e se não, para a Claudia"*.
--   28581 Ludmila · 123 Erika · 124 Claudia
INSERT INTO config (chave, valor, descricao)
VALUES ('distribuicao_ordem', '28581,123,124',
        'A cadeia da fila, em ordem: tenta um por um e para no primeiro que pode receber.')
ON CONFLICT (chave) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. A SENHA FIXA DO ALISTAMENTO
-- ----------------------------------------------------------------------------
--
-- 🔵 Dele: *"deixar senha padrão de 'movicall' (essa senha não há muita
-- exigência de segredo)"*.
--
-- 🚨 O QUE ISSO CUSTA, POR ESCRITO: quem souber `movicall` e um ramal alista um
-- PC naquele ramal. A senha derivada por HMAC continua existindo e continua
-- valendo -- esta é um ATALHO, não uma substituição --, e as outras travas
-- ficam de pé: limite de tentativas por IP e certificado de cliente no PC.
--
-- ⚠️ E ela NÃO queima janela: senão o primeiro PC a usar `movicall` trancaria
-- todos os outros, que é o oposto do pedido.
INSERT INTO config (chave, valor, descricao)
VALUES ('ligacoes_senha_fixa', 'movicall',
        'Senha fixa de alistamento do agente do MicroSIP. Vazio desliga o atalho.')
ON CONFLICT (chave) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. A MEMÓRIA DO AGENTE DE LIGAÇÕES
-- ----------------------------------------------------------------------------
--
-- 🚨 HOJE SÓ EXISTE O ÚLTIMO VALOR: `agente_ligacao` guarda `ultimo_ip`,
-- `pasta`, `ultima_versao` e `ultimo_pc`, e cada batimento sobrescreve. Quando
-- alguém troca a pasta de gravação, o caminho antigo some -- e com ele a
-- chance de achar as gravações que ficaram lá.
--
-- ⚠️ ESTA TABELA SÓ RECEBE MUDANÇA, nunca batimento. São 8 agentes falando de
-- 12 em 12 horas; gravar todo batimento seria um log de ruído que esconde as
-- poucas linhas que interessam.
CREATE TABLE IF NOT EXISTS agente_ligacao_evento (
    id            bigserial PRIMARY KEY,
    agente_id     bigint NOT NULL REFERENCES agente_ligacao(id) ON DELETE CASCADE,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    campo         text NOT NULL,
    valor_antes   text,
    valor_depois  text,
    CONSTRAINT ck_agente_evento_campo
        CHECK (campo IN ('versao', 'pasta', 'ip', 'pc'))
);

CREATE INDEX IF NOT EXISTS idx_agente_evento_agente
    ON agente_ligacao_evento (agente_id, criado_em DESC);

COMMENT ON TABLE agente_ligacao_evento IS
  'Mudanças de versão, pasta, IP e PC do agente do MicroSIP (migração 109). Só mudança, nunca batimento.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('109', now(), 'login do dia manda na fila, estado com hora, cadeia de distribuicao em lista e memoria do agente de ligacoes');

COMMIT;
