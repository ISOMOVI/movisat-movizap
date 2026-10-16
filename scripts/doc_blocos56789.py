"""Documentacao dos Blocos 5 a 9 (15/10) — etapa 4 do ciclo.

Acrescenta secoes em docs/ligacoes.md e docs/06_Conteudo_das_Telas.md, e uma
linha em docs/02_Modelo_Dados.md sobre o agente de importacao.

Idempotente. Uso: ./venv/bin/python scripts/doc_blocos56789.py
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

LIGACOES = """

## A ficha e o import retroativo (Blocos 5, 6 e 9, 15/10/2026)

### O modal de 7 dias na conversa (Bloco 5)

🔵 *"aqui na conversa, o modal só trará ultimos 7 dias, para mais dias um botão
vai levar para a aba Ligações"* e *"importante a separação basica entre, feitas,
recebidas, etc"*.

Botão **Ligações** na gaveta da conversa (a ficha), abrindo
`GET /api/conversas/{id}/ligacoes?dias=7` — rota que já existia desde o Bloco 3
e não tinha quem a chamasse. Dentro: os três grupos do `CHECK` da 059
(`Feitas`, `Recebidas`, `Perdidas`), cada um com a contagem, e em cada linha a
hora, a duração, quem atendeu e, havendo gravação, **ouvir** e **baixar** (um
player por vez; o `object URL` é revogado ao trocar e ao sair da tela).

🚨 **A permissão é `ATD_1.2`, a da conversa — não a da aba.** Quem atende vê as
ligações do número que está atendendo. A aba `LIG_1.1` é outra coisa: o
histórico de todos.

🚨 **A linha de cobertura é o que impede o modal de mentir.** Ele diz quantos
atendentes têm agente instalado, porque "nenhuma ligação com este número" e
"aquele PC não manda ligação nenhuma" são respostas diferentes e a tela não
pode devolver a mesma frase para as duas.

⚠️ **O rodapé "Ver todas na aba Ligações" só aparece para quem tem `LIG_1.1`**
(hoje: owner, admin e `atendimento`). Para quem não tem, seria um botão que
termina em 403.

### Outros contatos da empresa (Bloco 6)

`GET /api/conversas/{id}/contatos-da-empresa`, sob **`ATD_1.2`**.

🚨 **Rota irmã, e não `/api/clientes/{id}`.** A rota de cadastro é `CAD_1.1`,
que o perfil `atendimento` não tem desde 10/08: a gaveta tomaria 403 justamente
para quem atende. É o mesmo motivo de `/api/conversas/buscar-empresa` existir.

- **Cada telefone é uma linha**, não cada contato: contato com dois números dá
  duas linhas, e contato **sem** número aparece mesmo assim, com `e164` nulo.
  Esconder quem não tem número faria a lista afirmar "a empresa tem 3 contatos"
  onde ela tem 5.
- **`tem_whatsapp` tem três valores** e eles não se confundem: `true`
  conferido e tem, `false` conferido e não tem, `null` nunca conferido. O botão
  **Mensagem** não aparece no `false` (mandar ali só produz 409) e **continua
  aparecendo** no `null` — recusar por falta de conferência seria inventar o
  `false`.
- **Lista vazia vem com `motivo`**: `sem_cadastro` (o número não está no
  cadastro) e `contato_sem_empresa` (a pessoa não tem empresa) são casos
  diferentes, e a tela diz qual é.
- **Pular para outra conversa reusa a receita do `?numero=`**: busca o número,
  um acerto abre a conversa, nenhum abre "Nova mensagem" preenchida. Não
  existe rota que apenas localize ou crie conversa sem enviar, e inventar uma
  seria um segundo caminho de conversa nascer.
- A ficha passou a mostrar **o telefone do contato** no `dt>Contato`, que nunca
  teve número nenhum — os dois primeiros, com `+N` quando há mais.

### Import retroativo (Bloco 9)

Para o PC que passou meses **sem** agente. Dois lados:

1. **No PC:** `movizap-ligacoes.ps1 -Exportar` (agente **v0.5**) grava um
   `.zip` na Área de Trabalho com `pacote.json` + `gravacoes/`. **Não precisa
   de chave, não precisa de config e não fala com a VPS** — é só leitura, que é
   o que permite rodar antes do alistamento. O pacote tem a **mesma forma do
   envio**, inclusive o `call_id` sintético `arquivo:<nome>` para gravação sem
   registro no histórico, e declara por escrito o que ficou de fora
   (`fora_do_padrao`, `em_uso_agora`).
2. **Na VPS:** `scripts/importar_ligacoes.py <pacote.zip> [--conferir]
   [--atendente <login|id>]`.

🚨 **Entra pelo mesmo `ligacoes.registrar()` do agente.** A idempotência é a
mesma (`UNIQUE (ramal, call_id)` e `arquivo_sha256` único): importar duas vezes
o mesmo pacote grava **zero** na segunda. Um `INSERT` próprio seria uma segunda
verdade.

🚨 **Recusa, e diz o que recusou:** linha sem `call_id` (sem ela não há
idempotência, e a mesma ligação voltaria a cada import); áudio que nenhuma
ligação do pacote reivindica (ele viraria ligação inventada, com data tirada do
nome do arquivo); `sha256` diferente do declarado; pacote de outra origem; e
versão de pacote mais nova do que o script entende.

🚨 **`--conferir` pergunta ao BANCO, não ao pacote.** Sem isso ele dizia "11
entrariam" num pacote cujas 11 já estavam todas na base — relatório que promete
mais do que vai acontecer é a mesma doença de tela que mente.

🚨 **De quem é a ligação importada**, nesta ordem: o agente **vivo** do ramal; o
último **revogado** dele; e só então, com `--atendente`, um **agente de
importação** novo — que nasce **já revogado**, com chave aleatória que ninguém
vê. Ele serve para carimbar de quem é a ligação, nunca para enviar. **Nunca
revoga o agente vivo de um ramal:** o PC que manda hoje não pode cair porque
alguém importou um arquivo velho.

⚠️ **Outra origem fica fora** (PABX, Intelbras, planilha à mão): muda a chave
de idempotência e precisa de desenho aprovado por ele.

⚠️ **O `pc` da linha importada vira `importado:<PC>`** — é como o grid
distingue retroativo de envio ao vivo.

🚨 **Armadilha medida em 15/10:** o `Compress-Archive` do **Windows PowerShell
5.1** grava os nomes dentro do zip com **barra invertida**
(`gravacoes\\x.mp3`). O importador aceita os dois separadores; procurar só por
`gravacoes/` fazia ele recusar 19 gravações boas dizendo que estavam "ausentes
do zip". O pacote vem do PC do operador, onde não se escolhe a versão do
PowerShell — quem tem de aceitar os dois é o lado da VPS.

**Provado em 15/10:** o pacote real deste PC (28 ligações, 19 gravações, 5,6 MB)
importado contra a base que já tinha tudo → **0 novas, 28 e 19 já estavam, 0
recusadas**, nos dois modos; e 12 testes em `tests/teste_importar_ligacoes.py`.

### A sessão do dia (Bloco 8)

🔵 Decisão dele: *"o login vale até a virada do dia; o rascunho morre com ele"*.

`auth.expira_na_virada()` devolve a meia-noite seguinte em
**`America/Sao_Paulo`** (em UTC a virada cairia às 21h de Brasília, em plena
tarde), com **piso de 2 horas**: quem entra às 23:30 vale até a virada do dia
**seguinte**. A resposta do login devolve `expira_em` (ISO) em vez de
`expira_em_horas`, e `/api/sessao/eu` devolve `sessao_expira_em` — é daí que a
barra funciona depois de um F5 e para quem entra pelo Google.

⚠️ **O que isso custa, por escrito:** quem entra às 08:00 passa a ter token de
**16 h** em vez de 10 h. Continuam valendo as travas que já existem:
`atendente.ativo = false` derruba na requisição seguinte, perda de permissão
vira 403 na hora, e rotação do `MOVIZAP_JWT_SECRET` invalida tudo.

**Dois defeitos existentes que isso obrigou a consertar:** o 401 limpava a
sessão e **não navegava** (a pessoa ficava olhando uma tela sem casca que não
respondia mais nada até tentar navegar) — agora a casca leva ao Login com a
frase *"Sua sessão do dia terminou. Entre de novo."*; e o texto digitado no
compositor **vazava** de uma conversa para a outra, o que o rascunho por
conversa resolve.
"""

TELAS_06 = """

## ATD_1.2 — Ligações, Outros contatos e rascunho (15/10)

**Botão `Ligações`** na ficha: modal com as ligações daquele número nos
**últimos 7 dias**, separadas em `Feitas`, `Recebidas` e `Perdidas`, com hora,
duração, quem atendeu, e ouvir/baixar a gravação na própria linha. O modal diz
**quantos atendentes têm agente instalado** — sem essa linha, "nenhuma ligação"
e "aquele PC não manda" ficam iguais na tela. O rodapé **Ver todas na aba
Ligações** aparece só para quem tem `LIG_1.1`.

**Botão `Outros contatos`** na ficha: os contatos da empresa vinculada, com
papel e telefone, o atual marcado como "este", chip `sem WhatsApp` para quem
foi conferido e não tem, e **Mensagem** por linha, que pula para a conversa
daquele número (ou abre "Nova mensagem" preenchida, se ela ainda não existe).
Vazio **diz por quê**: número sem cadastro é um caso, empresa com um contato só
é outro.

**O `dt>Contato` passou a mostrar o telefone** — os dois primeiros, com `+N`
quando há mais.

**Rascunho por conversa:** o que foi digitado e não enviado fica guardado
naquela conversa (`localStorage`, chave `movizap.rascunho.<id>`), sobrevive a
F5 e à troca de conversa, aparece como chip **rascunho** na lista, e morre em
três momentos: envio bem-sucedido, texto apagado, e fim da sessão do dia.
🚨 Antes disso o texto **vazava** para a conversa seguinte.

**A barra de status** passou a dizer `sessão do dia · até HH:MM`, em cor de
aviso nos últimos 15 minutos.
"""

MODELO_02 = """- **Agente de importação (15/10):** uma linha de `agente_ligacao` pode nascer
  **já revogada**, com `ultima_versao = 'import'` — é o dono que o import
  retroativo (`scripts/importar_ligacoes.py`) usa quando o ramal nunca teve
  agente. Ela existe para a ligação ter de quem ser, e **não** serve para
  enviar: a chave é aleatória e ninguém a vê. O import **nunca** revoga o
  agente vivo de um ramal.
"""


def juntar(rel: str, texto: str, marca: str, ancora: str | None = None):
    caminho = RAIZ / rel
    atual = caminho.read_text(encoding="utf-8")
    if marca in atual:
        print(f"ja documentado: {rel}")
        return
    if ancora:
        if atual.count(ancora) != 1:
            raise SystemExit(f"ancora {atual.count(ancora)}x em {rel}")
        novo = atual.replace(ancora, texto + ancora, 1)
    else:
        novo = atual.rstrip("\n") + "\n" + texto
    caminho.write_text(novo, encoding="utf-8")
    print(f"documentado: {rel}")


juntar("docs/ligacoes.md", LIGACOES, "A ficha e o import retroativo")
juntar("docs/06_Conteudo_das_Telas.md", TELAS_06,
       "Ligações, Outros contatos e rascunho")
juntar("docs/02_Modelo_Dados.md", MODELO_02, "Agente de importação (15/10)",
       ancora="- **Alerta:** `ligacoes.agentes_mudos()` lista quem está sem contato")
