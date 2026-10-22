"""Patch: a documentação e os dois guardas de registro.

O doc é o TERCEIRO LUGAR (`telas.py`, `router/index.js`, doc) e três testes o
conferem. Aqui entram:

  · `docs/03_Registro_Telas.md`  -- a FRM_1.1 na tabela do registro e na dos
                                    ícones;
  · `docs/06_Conteudo_das_Telas.md` -- o que a tela FAZ (o teste cobra seção
                                    por código);
  · `docs/02_Modelo_Dados.md`    -- a migração 074, com as cinco tabelas pelo
                                    nome (o `teste_modelo_documentado` cobra);
  · `tests/teste_telas.py`       -- os dois conjuntos FECHADOS que a tela nova
                                    estourou, de propósito: o prefixo de
                                    módulo e o que o admin vê.
"""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def emendar(caminho: Path, ancora: str, novo: str, marca: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if marca in texto:
        print(f"{caminho.name}: {marca!r} ja estava")
        return
    if texto.count(ancora) != 1:
        sys.exit(f"{caminho.name}: ancora de {marca!r} aparece "
                 f"{texto.count(ancora)} vezes -- nada escrito")
    caminho.write_text(texto.replace(ancora, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} emendado")


# ======================================================== docs/03 — registro
D03 = RAIZ / "docs" / "03_Registro_Telas.md"
emendar(D03,
        "| `CAD_1.1` | Clientes | `/cadastro/clientes` | `cadastro` | 1 |",
        "| `FRM_1.1` | Solicitações | `/solicitacoes` | `equipe` | 1 |\n"
        "| `CAD_1.1` | Clientes | `/cadastro/clientes` | `cadastro` | 1 |",
        "| `FRM_1.1` | Solicitações |")

emendar(D03,
        "| `CAD_1.1` Clientes | `bi-building` | menu |",
        "| `FRM_1.1` Solicitações | `bi-ui-checks` | menu |\n"
        "| `CAD_1.1` Clientes | `bi-building` | menu |",
        "| `FRM_1.1` Solicitações | `bi-ui-checks` | menu |")

# ⚠️ A tabela de perfis do fim do doc também cita códigos por perfil. O teste
# não a mede, mas doc que lista cinco telas de `equipe` e esconde a sexta é
# doc que mente -- `M12` não depende de haver teste.
texto = D03.read_text(encoding="utf-8")
velho_perfil = "`CAD_2.1` `CAD_2.2`"
if "FRM_1.1`" in texto.split("| Perfil |")[-1]:
    print("docs/03: tabela de perfis ja citava a FRM_1.1")
elif texto.count(velho_perfil) >= 1:
    D03.write_text(texto.replace(velho_perfil, velho_perfil + " `FRM_1.1`", 1),
                   encoding="utf-8")
    print("docs/03: FRM_1.1 citada tambem na tabela de perfis")
else:
    print("docs/03: NAO achei a tabela de perfis -- confira a mao")

# ======================================================== docs/06 — conteúdo
D06 = RAIZ / "docs" / "06_Conteudo_das_Telas.md"
SECAO = '''
## 22/10 — Formulários próprios: a FRM_1.1 e o link público

🔵 Decisão dele: *"nenhuma possibilidade irá usar o bitrix, esse projeto é
movizap"*. Os 15 formulários de `solicite.movisat.com.br` eram **Bitrix24 CRM
Webforms** e concentravam toda a entrada de demanda da Movisat. Eles passam a
viver aqui; o Bitrix fica no ar só até ele desligar.

**O que entrou nesta primeira volta (Etapa 1):**

- **`forms.movisat.com.br/f/<slug>`** — o formulário aberto, sem login. Nesta
  volta no ar **só o CES** (5 campos); os outros 14 entram como DADO, depois
  que ele validar este no navegador.
- **`FRM_1.1` Solicitações** — a tela que recebe. Lista à esquerda, ficha à
  direita, três estados (`nova`, `em_andamento`, `concluida`), anexo para
  baixar. Grupo **Atendimento**, permissão **`equipe`** (owner e admin, a
  mesma régua da Fila e do Histórico).
- **o selo no menu** — o quarto, ao lado de WhatsApp, Chat interno e E-mail, e
  somado no grupo fechado. Conta as solicitações `nova` **pela mesma coluna
  que a tela filtra**.
- **o interruptor por pessoa**, na `CFG_11.1` — pedido dele: *"controle de
  notificações no 'minha conta' de cada usuário, igual as demais"*. Nasce
  LIGADO, e só aparece para quem tem a FRM_1.1.
- **o interruptor do sistema**, na `CFG_7.1` › Geral — pedir a conta de somar
  em TODO envio. Nasce desligado, e fica **no fim da tela** (dois testes da
  Geral escolhem a caixa pelo índice).

🚨 **A definição do formulário é DADO, não arquivo.** `formulario`,
`formulario_campo` e `formulario_regra` (migração 074) guardam campos,
rótulos, opções com os IDs do Bitrix e as regras condicionais; **uma** tela os
desenha (`CamposDoFormulario.vue`). Formulário novo é linha em tabela.

🚨 **A validação é NOSSA, no servidor.** Medido em 22/10: o Bitrix aceitou
`values=[]` vazio e criou o registro `15620` — toda a validação dos 239 campos
era no navegador, e navegador é do cliente.

🚨 **Campo escondido por regra SOME do registro**, não vira vazio: *"a pessoa
não respondeu"* e *"a pergunta não foi feita"* são coisas diferentes.

🚨 **Alvo de regra `show` nasce escondido, e isso foi medido:** nos 15
formulários **nenhum** campo vem com `visible: false` no loader do Bitrix, e
há **60 ações `show`**. Quem traduz é a carga. Confiar no `visible` faria todo
campo condicional aparecer sempre.

🚨 **O bundle público é separado** (`frontend/dist_publico`, servido em
`/pub/assets` e `/f/{slug}`). Pergunta dele: *"qual a mais segura para os
links que terão acesso externos"*. O bundle do painel publica `sourcemap:
true` — uma rota pública dentro dele entregaria o código-fonte do painel a
qualquer anônimo.

**As defesas do envio, nesta ordem:** isca invisível → tempo mínimo de 3 s
entre abrir e enviar (token assinado, sem sessão) → contagem de envios por IP
→ e **só então** a conta de somar, servida por nós. Decisão dele: *"captcha no
final pode se legal, mas tbm usam pelo cel então não pode virar entrave de
processo"*.

**Os anexos ficam isolados** em `/home/claude/movizap_formularios_anexos`,
fora do projeto e fora do `dist` (*"isolar os anexos sem perder controle na
VPS"*), com lista branca de extensão, 10 MB por arquivo e 25 MB por envio.
⚠️ **O host público nunca serve anexo** — baixar é rota autenticada do painel.

🔴 **O que ainda espera ele:** apagar os 14 registros de teste no Bitrix24
(`resultId` 15620–15646) · dizer para onde cada formulário cai no CRM hoje ·
confirmar o mapa formulário → `problemaId` · o texto dos nossos termos de uso
(o do Bitrix é *boilerplate* em inglês) · revisar os `nosso_nome` dos 239
campos.
'''
texto = D06.read_text(encoding="utf-8")
if "FRM_1.1" in texto:
    print("docs/06: ja tinha a FRM_1.1")
else:
    D06.write_text(texto.rstrip("\n") + "\n" + SECAO, encoding="utf-8")
    print("docs/06: secao da FRM_1.1 no fim do arquivo")

# ======================================================== docs/02 — modelo
D02 = RAIZ / "docs" / "02_Modelo_Dados.md"
MODELO = '''
## Migração 074 — os formulários próprios, e eles são DADO

🔵 22/10, decisão dele: *"nenhuma possibilidade irá usar o bitrix, esse
projeto é movizap"*. Cinco tabelas novas.

**`formulario`** — um por formulário: `codigo`, `slug` (o que aparece em
`/f/<slug>`), `titulo`, `setor`, `botao`, `descricao`, `ativo`, `ordem`,
`gera_os`, `problema_id`, `tipo_os_id`, `prioridade_id`, `bitrix_id`,
`bitrix_sec`, `criado_em`, `atualizado_em`.
🚨 `ativo` **nasce falso**: enquanto for, o link público responde 404. Quem
liga é o owner, pela tela.
🚨 `bitrix_id`/`bitrix_sec` são **procedência**, não destino — dizem de onde a
definição foi lida em 22/10 (`dados/formularios_bitrix/mapa_bruto.json`).
Nada neste projeto escreve no Bitrix.

**`formulario_campo`** — `formulario_id`, `nome` (o nome de ORIGEM, ilegível
de propósito: `DEAL_UF_CRM_DEAL_1649449139431` é campo personalizado do
Bitrix, e o número é o timestamp em que alguém o criou), **`nosso_nome`** (o
nome legível, derivado do rótulo e único por formulário), `rotulo`, `tipo`,
`obrigatorio`, `multiplo`, `visivel`, `ordem`, `opcoes` (jsonb, com o `value`
numérico do Bitrix — é ele que as regras comparam), `ajuda`.
O CHECK de `tipo` tem os **15 tipos** medidos nos 239 campos: tipo
desconhecido para na CARGA, não na tela do cliente.

**`formulario_regra`** — `formulario_id`, `ordem`, `logica`, `lista` (jsonb,
a estrutura do Bitrix como veio: `condition` → `action`, `show`/`hide`).
🚨 Fica em UMA forma porque os DOIS lados a avaliam: o servidor
(`movizap/formularios.py:visiveis`, que é a autoridade) e o navegador
(`frontend/src/util/regras_formulario.js`). As duas suítes leem o mesmo
arquivo de casos, `tests/casos_regras_formulario.json`.

**`formulario_solicitacao`** — `formulario_id`, `criada_em`, `ip`, `valores`
(jsonb, pela chave de ORIGEM), `estado` (`nova`/`em_andamento`/`concluida`),
`lida_por`, `lida_em`, e já anuláveis para a Etapa 2/3: `conversa_id`,
`contato_id`, `cliente_id`, `os_id`, `numero_ordem`.
🚨 **É RETRATO**: não se reescreve quando a definição muda, e campo escondido
por regra **não entra, nem vazio**.
⚠️ A FK para `formulario` **não** é `ON DELETE CASCADE`, de propósito: apagar
um formulário com solicitação recebida é recusado pelo banco. Campo e regra,
que são definição, saem em cascata.

**`formulario_arquivo`** — `solicitacao_id`, `campo`, `nome_original`,
`caminho`, `bytes`, `mime`, `criado_em`.
🚨 O arquivo fica **fora do projeto**, em
`/home/claude/movizap_formularios_anexos`, como o anexo de e-mail: dentro, ele
entraria no git e no `dist` — e o `dist` é servido. `nome_original` é texto
para ler, **nunca** caminho.
'''
texto = D02.read_text(encoding="utf-8")
if "Migração 074" in texto:
    print("docs/02: ja tinha a 074")
else:
    D02.write_text(texto.rstrip("\n") + "\n" + MODELO, encoding="utf-8")
    print("docs/02: secao da migracao 074 no fim do arquivo")

# ================================================ tests/teste_telas.py
TESTE = RAIZ / "tests" / "teste_telas.py"
emendar(
    TESTE,
    '        assert modulo in {"INI", "EML", "ATD", "CAD", "CFG", "LIG", "REL"}, t["codigo"]',
    '''        # FRM entrou em 22/10 com os formulários próprios: formulário não é
        # conversa de WhatsApp nem cadastro -- tem definição, campo
        # obrigatório e anexo, e nenhuma das três existe numa mensagem.
        # Pendurá-lo em ATD misturaria "cliente escreveu" e "cliente
        # preencheu".
        assert modulo in {"INI", "EML", "ATD", "CAD", "CFG", "LIG", "REL",
                          "FRM"}, t["codigo"]''',
    '"FRM"}, t["codigo"]')

emendar(
    TESTE,
    '''        esperado = de_atendimento | {"ATD_1.3", "ATD_5.1",
                                     "CAD_2.1", "CAD_2.2", "CFG_10.1", "CFG_11.1",
                                     "CFG_12.1"}''',
    '''        # 🔵 22/10: a FRM_1.1 (Solicitações) nasceu `equipe`, pela mesma
        # régua da Fila e do Histórico -- a solicitação traz dado de cadastro
        # (CNPJ, endereço, valor) de quem ainda não é cliente. O admin a vê
        # porque tem `equipe`, e por isso vem nomeada aqui: o conjunto segue
        # FECHADO, e é esta linha que muda quando a decisão dele muda.
        esperado = de_atendimento | {"ATD_1.3", "ATD_5.1", "FRM_1.1",
                                     "CAD_2.1", "CAD_2.2", "CFG_10.1", "CFG_11.1",
                                     "CFG_12.1"}''',
    '"ATD_5.1", "FRM_1.1"')

print("\\npronto")
