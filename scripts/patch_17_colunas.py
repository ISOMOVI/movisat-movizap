# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 10): o painel passa a ter EXATAMENTE as 17 colunas dele.

🔵 *"eis as situacoes que precisamos manter"* (17, na ordem dele) + *"as colunas
do painel do Movizap devem ser ajustadas -- qualquer aba fora dessas nao deve
estar no painel"*.

🚨 SAEM AS DUAS COLUNAS QUE NAO SAO SITUACAO -- "Sem OS" e "Sem situacao".
Elas existiam por um motivo que esta escrito no modulo, e o motivo mudou:
  · "Sem OS" existia porque a OS nascia por BOTAO. Ele mudou isso em 29/10
    (*"todo chamado de suporte abrira uma OS"*, automatico no envio), entao a
    coluna nunca mais recebe card;
  · "Sem situacao" existia porque 164 das 574 OS do cache tinham situacao 0 ou
    nula -- mas aquelas sao OS de OUTRAS origens, nao solicitacoes deste
    painel. As daqui nascem com 38.

🚨 MAS DADO NAO DESAPARECE DA TELA EM SILENCIO (`M12`). Se uma solicitacao
ficar sem OS (a escrita no Harmonit falhou) ou com situacao fora das 17, ela
nao tem coluna -- e sumiria. Entao o quadro passa a devolver `fora_do_quadro`,
e a tela escreve UMA linha quando houver algo a dizer. Com zero, nao escreve
nada: hoje a tela fica limpa, que e o que ele pediu.
"""
import pathlib
import sys

MOVI = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo and novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


p = MOVI / "movizap" / "paineis.py"
print(p.name)

trocar(p, '''# ----------------------------------------------------------------------------
# As 11 situações da OS do Harmonit
# ----------------------------------------------------------------------------
# 🚨 CONSULTADAS AO VIVO EM 22/10 em `GET /SituacaoOrdemServico/ObterSituacoesOS`
# e copiadas AQUI porque são o vocabulário das colunas -- a tela não pode
# depender de uma chamada ao Harmonit para saber quais colunas desenhar.
#
# ⚠️ "Nova sollicitação" tem DOIS L, e é assim no Harmonit. Corrigir aqui faria
# a tela e o ERP chamarem a mesma coisa por nomes diferentes; quem lê os dois
# lado a lado é que decide, e ele ainda não pediu.
#
# ⚠️ A LISTA PODE CRESCER NO HARMONIT sem ninguém avisar. Situação que chegar
# fora desta lista cai em "Sem situação" com o número cru à vista -- é a régua
# do grid do FPSL: *"estado desconhecido mostra o valor cru"*, nunca um rótulo
# inventado.
SITUACOES = (
    (38, "Nova sollicitação"),
    (251, "Configuração"),
    (677, "Envio dos Equipamentos"),
    (890, "Agendamento"),
    (1316, "Serviço Agendado"),
    (15694, "Serviço Realizado"),
    (15695, "Pós Venda"),
    (15696, "Aguardando Devolução do Equipamento"),
    (15746, "Financeiro"),
    (15747, "Aguardando Chegada do Fornecedor"),
    (15797, "Aguardando aviso prévio"),
)''',
       '''# ----------------------------------------------------------------------------
# As 17 situações da OS do Harmonit — e a ORDEM é a dele
# ----------------------------------------------------------------------------
# 🔵 Definidas por ele em 29/10: *"eis as situações que precisamos manter"*, e
# *"as situações já estão na Ordem"*. A ordem desta tupla É a ordem das colunas
# do painel, e é o fluxo da operação -- não alfabética, não por id.
#
# 🚨 O CATÁLOGO DO HARMONIT FOI AJUSTADO PARA ESTAS 17, em 29/10, pelo
# `fpsl_weso/ajustar_situacoes_os.py`: 11 renomeadas e 6 criadas. ⚠️ Nenhuma
# foi EXCLUÍDA -- excluir deixaria OS apontando para id inexistente --, e
# nenhuma sobrou fora: as 11 antigas todas mapearam.
#
# 🔵 As duas escolhas que ELE fez quando eu perguntei (não supus):
#   · a 677 "Envio dos Equipamentos" (4 OS reais) virou *"Enviar por
#     correio/transportadora"*, e *"Entrega de materiais prontos"* nasceu nova;
#   · a 15694 "Serviço Realizado" (19 OS) virou *"Atendimento finalizado"*.
#     🚨 ELA É A PORTA DO PAINEL FINANCEIRO DO FPSL (a rotina de conferência
#     dispara nesse id). O id não mudou, então o FPSL segue funcionando -- o
#     que mudou é o nome que a operação lê.
#
# ⚠️ Os nomes são como estão no ERP, inclusive "Novo Solicitação 1ª" e
# "Analise" sem acento: tela e ERP têm de chamar a mesma coisa pelo mesmo nome,
# e corrigir aqui criaria duas verdades. Quem muda o nome é o catálogo.
#
# ⚠️ A LISTA PODE CRESCER NO HARMONIT sem ninguém avisar. Situação que chegar
# fora desta lista não tem coluna -- e por isso o quadro conta essas em
# `fora_do_quadro`, para a tela dizer em vez de esconder.
SITUACOES = (
    (38,    "Novo Solicitação 1ª"),
    (16487, "Pendente de ação da Movisat"),
    (251,   "Configurar equipamentos e Sistemas"),
    (16488, "Entrega de materiais prontos"),
    (677,   "Enviar por correio/transportadora"),
    (15747, "Aguardando recebimento via correio/transportadora"),
    (15797, "Rescisão Aguardando Aviso Prévio"),
    (890,   "Agendar serviço"),
    (16489, "Confirmação agendamento"),
    (1316,  "Serviço Agendado"),
    (15696, "Aguardando devolução de equipamento"),
    (16490, "Analise de Equipamentos Retornados"),
    (15694, "Atendimento finalizado"),
    (16491, "Não atendido"),
    (15746, "Financeiro"),
    (15695, "Pós venda"),
    (16492, "Contratual"),
)''',
       "paineis.py: as 17 na ordem dele")

trocar(p, '''# As duas colunas que NÃO são situação do Harmonit, e por que existem:
#
# 🚨 `sem_os` é a primeira porque é de onde a OS nasce. Hoje TODAS as
# solicitações estão aqui -- nenhuma virou OS ainda --, e isso é o estado
# correto, não uma tela vazia.
#
# 🚨 `sem_situacao` existe por um número medido: das 574 OS no cache do FPSL em
# 22/10, **127 têm `situacao_id = 0` e 37 têm NULL** -- 164 que não estão em
# nenhuma das 11. Sem esta coluna elas desapareceriam da tela, e tela que
# esconde dado é o defeito que esta casa chama de `M12`.
COLUNA_SEM_OS = "sem_os"
COLUNA_SEM_SITUACAO = "sem_situacao"''',
       '''# 🔵 29/10: AS DUAS COLUNAS QUE NÃO ERAM SITUAÇÃO SAÍRAM -- *"qualquer aba
# fora dessas não deve estar no painel"*. E o motivo de cada uma deixou de
# valer no mesmo dia:
#
#   · "Sem OS" existia porque a OS nascia por BOTÃO (decisão de 23/10). Ele
#     mudou isso: *"todo chamado de suporte abrirá uma OS"*, automático no
#     envio -- então a coluna não recebe card nenhum;
#   · "Sem situação" existia por 164 OS com `situacao_id` 0 ou nulo no cache do
#     FPSL. ⚠️ Aquelas são OS de OUTRAS origens, não solicitações deste painel;
#     as daqui nascem em 38.
#
# 🚨 MAS NADA SOME DA TELA EM SILÊNCIO (`M12`). Solicitação sem OS (a escrita
# no Harmonit falhou) ou com situação fora das 17 não tem coluna -- e sumiria.
# Por isso o quadro conta essas em `fora_do_quadro`, e a tela escreve UMA linha
# quando houver o que dizer. Com zero, não escreve nada.''',
       "paineis.py: saem as duas colunas")

trocar(p, '''    conhecidas = {sid for sid, _ in SITUACOES}
    colunas = [
        {"chave": COLUNA_SEM_OS, "titulo": "Sem OS", "situacao_id": None,
         "nota": "a solicitação chegou e ainda não virou OS", "cards": []},
        {"chave": COLUNA_SEM_SITUACAO, "titulo": "Sem situação",
         "situacao_id": None,
         "nota": "tem OS, e a situação é 0, nula ou desconhecida", "cards": []},
    ]
    colunas += [{"chave": f"s{sid}", "titulo": nome, "situacao_id": sid,
                 "nota": None, "cards": []} for sid, nome in SITUACOES]
    por_chave = {c["chave"]: c for c in colunas}

    for linha in linhas:
        if not linha["os_id"]:
            chave = COLUNA_SEM_OS
        elif linha["situacao_id"] in conhecidas:
            chave = f"s{linha['situacao_id']}"
        else:
            # 🚨 Situação 0, nula ou que não está na lista. O número cru vai no
            # card, para o operador ver o que o Harmonit respondeu.
            chave = COLUNA_SEM_SITUACAO
        por_chave[chave]["cards"].append({''',
       '''    conhecidas = {sid for sid, _ in SITUACOES}
    colunas = [{"chave": f"s{sid}", "titulo": nome, "situacao_id": sid,
                "nota": None, "cards": []} for sid, nome in SITUACOES]
    por_chave = {c["chave"]: c for c in colunas}
    # 🚨 O que não tem coluna é CONTADO, não escondido (ver acima).
    fora = {"sem_os": 0, "situacao_fora": 0, "situacoes": []}

    for linha in linhas:
        if not linha["os_id"]:
            fora["sem_os"] += 1
            continue
        if linha["situacao_id"] not in conhecidas:
            fora["situacao_fora"] += 1
            # ⚠️ O número cru entra na lista, nunca um rótulo inventado -- é a
            # régua do grid do FPSL: *"estado desconhecido mostra o valor
            # cru"*.
            if linha["situacao_id"] not in fora["situacoes"]:
                fora["situacoes"].append(linha["situacao_id"])
            continue
        por_chave[f"s{linha['situacao_id']}"]["cards"].append({''',
       "paineis.py: distribui nas 17 e conta o resto")

trocar(p, '''        "colunas": colunas,
        "total": len(linhas),''',
       '''        "colunas": colunas,
        "total": len(linhas),
        # 🚨 O que não tem coluna. A tela só escreve se algum for maior que
        # zero -- `M12` sem encher a tela de aviso.
        "fora_do_quadro": fora,''',
       "paineis.py: devolve fora_do_quadro")

print()
print("ok -- falta a tela")


# ---------------------------------------------------------------------------
# A tela: 17 colunas, nenhuma fixa, e a linha do que ficou fora
# ---------------------------------------------------------------------------
t = MOVI / "frontend" / "src" / "telas" / "PainelOperacao.vue"
print(t.name)

trocar(t, '''   🚨 MOVER AINDA NÃO EXISTE, E A TELA DIZ ISSO. A rota que escreve
   `situacaoId` no Harmonit é da volta seguinte e depende de uma decisão dele.
   Enquanto não existir, não há `draggable` nenhum: oferecer o gesto e não
   gravar seria pior que não ter o gesto. É o precedente do `ModalAgendar`, que
   explica em vez de sumir.

   🚨 COLUNA VAZIA NASCE COLAPSADA, com o contador à vista — são 13 colunas, e
   nenhuma tela mostra 13 colunas sem rolar. É o que o kanban do FPSL já faz
   com a coluna "Pago". ⚠️ As duas primeiras ("Sem OS" e "Sem situação")
   nunca colapsam: a primeira é de onde a OS nasce, e a segunda existe porque
   **164 das 574 OS do Harmonit não estão em nenhuma das 11 situações**
   (medido em 22/10). Esconder essas duas seria esconder justamente o que há.''',
       '''   🚨 MOVER AINDA NÃO EXISTE. A rota que escreve `situacaoId` no Harmonit é da
   volta seguinte; enquanto não existir, não há `draggable` nenhum, porque
   oferecer o gesto e não gravar é pior que não ter o gesto. ⚠️ Em 29/10 ele
   mandou TIRAR a frase que explicava isso na tela (*"os comentários tbm devem
   sumir dali"*) -- o comportamento não mudou, só o texto saiu.

   🚨 SÃO 17 COLUNAS, E A ORDEM É A DELE (29/10): *"as situações já estão na
   Ordem"*. A ordem é o fluxo da operação, não alfabética nem por id, e ela
   vive numa tupla só, em `movizap/paineis.py`.

   🚨 COLUNA VAZIA NASCE COLAPSADA, com o contador à vista — são 17 colunas, e
   nenhuma tela mostra 17 sem rolar. É o que o kanban do FPSL já faz com a
   coluna "Pago". ⚠️ Nenhuma é fixa agora: as duas que nunca colapsavam ("Sem
   OS" e "Sem situação") SAÍRAM em 29/10 -- *"qualquer aba fora dessas não deve
   estar no painel"*.''',
       "tela: cabecalho das 17")

trocar(t, '''/* As duas que nunca colapsam. */
const SEMPRE_ABERTAS = ['sem_os', 'sem_situacao']
''', '''''', "tela: sai SEMPRE_ABERTAS")

trocar(t, '''      /* Vazia nasce fechada; com card, aberta. */
      abertas.value[coluna.chave] = SEMPRE_ABERTAS.includes(coluna.chave)
        || coluna.total > 0''',
       '''      /* Vazia nasce fechada; com card, aberta. ⚠️ Nenhuma é fixa desde
         29/10 -- as duas que não eram situação saíram do painel. */
      abertas.value[coluna.chave] = coluna.total > 0''',
       "tela: colapso so pelo contador")

trocar(t, '''function alternar(coluna) {
  if (SEMPRE_ABERTAS.includes(coluna.chave)) return
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}''',
       '''function alternar(coluna) {
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}''',
       "tela: alternar sem excecao")

trocar(t, '''const vazio = computed(
  () => Boolean(quadro.value) && quadro.value.total === 0)''',
       '''/* 🚨 O QUE NÃO TEM COLUNA, DITO EM UMA LINHA -- e só quando existe.
   Solicitação sem OS (a escrita no Harmonit falhou) ou com situação fora das
   17 não cabe em coluna nenhuma, e sumir da tela é o defeito que esta casa
   chama de `M12`. Com zero, esta linha não aparece: hoje o painel fica limpo,
   que é o que ele pediu em 29/10. */
const fora = computed(() => {
  const f = quadro.value?.fora_do_quadro
  if (!f || (!f.sem_os && !f.situacao_fora)) return ''
  const partes = []
  if (f.sem_os) {
    partes.push(`${f.sem_os} sem OS (a escrita no Harmonit falhou)`)
  }
  if (f.situacao_fora) {
    partes.push(`${f.situacao_fora} com situação fora das 17`
      + (f.situacoes.length ? ` (${f.situacoes.join(', ')})` : ''))
  }
  return partes.join(' · ')
})''',
       "tela: a linha do que ficou fora")

trocar(t, '''      <!-- 🔵 29/10, ele: *"os comentários tbm devem sumir dali"*. Saíram os''',
       '''      <p v-if="fora" class="aviso aviso--atencao" role="status">
        <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
        <span>{{ fora }} — abra em <strong>Solicitações</strong>.</span>
      </p>

      <!-- 🔵 29/10, ele: *"os comentários tbm devem sumir dali"*. Saíram os''',
       "tela: desenha a linha do que ficou fora")

print()
print("ok")
