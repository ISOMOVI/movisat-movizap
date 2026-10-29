# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 6): os ajustes dele no formulario de Suporte.

🔵 Seis pedidos, todos de DADO -- nenhum `.vue` novo:
   1. uma caixa so para o nome (sai `sobrenome`, `primeiro-nome` vira
      "Nome completo");
   2. telefone com o modelo esmaecido "(00) 123456789";
   3. as 4 opcoes novas de "Tipo de solicitacao", em ordem alfabetica;
   4. sai o campo "Assunto" -- *"o assunto ja e o proprio tipo de
      solicitacao"*;
   5. "Detalhe a ocorrencia" mais alto;
   6. o campo de placa passa a ter FONTE (as placas ativas na WESO).

🚨 TUDO EM `AJUSTES`, NO `carregar_formularios.py`, porque a carga APAGA e
reescreve campos a cada rodada: editar no banco funcionaria hoje e
desapareceria na proxima carga, sem erro e sem aviso.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


# ---------------------------------------------------------------------------
# 1. A definicao aplica os ajustes
# ---------------------------------------------------------------------------
f = RAIZ / "movizap" / "formularios.py"
print(f.name)

trocar(f, """        \"\"\"SELECT nome, nosso_nome, rotulo, tipo, obrigatorio, multiplo,
                  visivel, ordem, opcoes, ajuda, validacao
             FROM formulario_campo WHERE formulario_id = %s""",
       """        \"\"\"SELECT nome, nosso_nome, rotulo, tipo, obrigatorio, multiplo,
                  visivel, ordem, opcoes, ajuda, validacao,
                  fantasma, linhas, fonte
             FROM formulario_campo WHERE formulario_id = %s""",
       "definicao: fantasma, linhas e fonte")

trocar(f, """                     ordem: int = 100, formato: str = "classico",
                     etapas: list | None = None,
                     validacoes: dict | None = None) -> dict:""",
       """                     ordem: int = 100, formato: str = "classico",
                     etapas: list | None = None,
                     validacoes: dict | None = None,
                     ajustes: dict | None = None) -> dict:""",
       "gravar_definicao: parametro ajustes")

trocar(f, """    for campo in campos:
        if campo["type"] not in TIPOS:
            raise DadoInvalido(
                f"Tipo de campo desconhecido no formulário {codigo}: "
                f"{campo['type']!r} em {campo['name']!r}.")
""",
       '''    for campo in campos:
        if campo["type"] not in TIPOS:
            raise DadoInvalido(
                f"Tipo de campo desconhecido no formulário {codigo}: "
                f"{campo['type']!r} em {campo['name']!r}.")

    # ----------------------------------------------------------------------
    # OS AJUSTES NOSSOS, em cima da definição do Bitrix
    # ----------------------------------------------------------------------
    # 🔵 Decisão dele, 29/10: *"vamos mudar as opções do 'Tipo de solicitação',
    # pois são do bitrix e não nos satisfazem mais"*. A definição continua
    # vindo de lá -- o que muda é que ela deixa de ser a palavra final.
    #
    # 🚨 ISTO NÃO EDITA O `mapa_bruto.json`. O bruto é **procedência**: diz de
    # onde a definição foi lida em 22/10. Reescrevê-lo apagaria a prova de como
    # o formulário era no Bitrix, e é essa prova que permite responder *"o que
    # foi perdido em relação ao original?"* -- pergunta que ele já fez.
    ajustes = ajustes or {}
    fora = set(ajustes.get("fora") or [])
    por_campo = ajustes.get("campos") or {}
    nao_casados = set(fora) | set(por_campo)
    sobraram = []
    for campo in campos:
        nosso = nome_legivel(campo.get("label") or "", campo["name"], set())
        nao_casados.discard(nosso)
        if nosso in fora:
            # ⚠️ Campo TIRADO não é campo escondido: ele não existe, não vem na
            # definição e não entra no registro. Quem some por regra é outra
            # coisa, e continua sendo.
            continue
        mudar = por_campo.get(nosso) or {}
        # 🚨 O RÓTULO NOVO VAI NUM CAMPO À PARTE, e isto não é estilo: o
        # `nosso_nome` é DERIVADO do rótulo (`nome_legivel`). Trocar
        # `campo["label"]` aqui renomearia o campo -- "Primeiro Nome" viraria
        # `nome-completo` --, e aí as tabelas `ETAPAS` e `VALIDACOES`, que
        # citam `primeiro-nome`, apontariam para um campo que não existe mais.
        # O nome continua saindo do rótulo ORIGINAL; o rótulo novo é só o que
        # a pessoa lê.
        campo["_rotulo"] = mudar.get("rotulo")
        if "opcoes" in mudar:
            campo["items"] = [{"value": o["value"], "label": o["label"]}
                              for o in mudar["opcoes"]]
        if "obrigatorio" in mudar:
            campo["required"] = mudar["obrigatorio"]
        campo["_fantasma"] = mudar.get("fantasma")
        campo["_linhas"] = mudar.get("linhas")
        campo["_fonte"] = mudar.get("fonte")
        sobraram.append(campo)

    # 🚨 AJUSTE QUE NÃO ACHOU CAMPO PARA NA CARGA. Um `nosso_nome` escrito
    # errado aqui seria ajuste que não acontece -- e o formulário ficaria com a
    # cara antiga sem ninguém saber por quê.
    if nao_casados:
        raise DadoInvalido(
            f"{codigo}: ajuste citando campo que nao existe: "
            + ", ".join(sorted(nao_casados)))

    # ⚠️ As REGRAS continuam as do Bitrix, e podem apontar para campo tirado.
    # Regra com alvo inexistente é ignorada por `visiveis()` (`if alvo not in
    # todos`), então não há o que limpar -- e deixá-las registradas preserva a
    # procedência.
    campos = sobraram
''',
       "gravar_definicao: aplica os ajustes")

# ---------------------------------------------------------------------------
# 2. A rota publica entrega os tres
# ---------------------------------------------------------------------------
m = RAIZ / "movizap" / "main.py"
print(m.name)
trocar(m, """                    "ajuda": c["ajuda"], "validacao": c.get("validacao")}
                   for c in d["campos"]],""",
       """                    "ajuda": c["ajuda"], "validacao": c.get("validacao"),
                    "fantasma": c.get("fantasma"), "linhas": c.get("linhas"),
                    "fonte": c.get("fonte")}
                   for c in d["campos"]],""",
       "main.py: fantasma, linhas e fonte no corpo publico")

# ---------------------------------------------------------------------------
# 3. A tabela de ajustes, na carga
# ---------------------------------------------------------------------------
c = RAIZ / "scripts" / "carregar_formularios.py"
print(c.name)

trocar(c, '''# A mascara e a conferencia de cada campo, por `nosso_nome`.''',
       '''# ----------------------------------------------------------------------------
# OS AJUSTES NOSSOS em cima da definicao do Bitrix (29/10)
# ----------------------------------------------------------------------------
# 🔵 *"vamos mudar as opcoes do 'Tipo de solicitacao', pois sao do bitrix e nao
# nos satisfazem mais"*. A partir daqui a definicao do Bitrix e ponto de
# partida, nao palavra final.
#
# 🚨 E PRECISA MORAR AQUI: `gravar_definicao` APAGA e reescreve os campos a cada
# carga. Ajuste editado no banco funciona hoje e desaparece na proxima rodada,
# sem erro e sem aviso.
#
# ⚠️ `fora` TIRA o campo (ele deixa de existir, nao fica escondido). O resto
# muda o campo que fica.
AJUSTES = {
    "SUPORTE": {
        # 🔵 *"na aba 2, somente 1 caixa para o nome ja serve"* e *"o assunto
        # ja e o proprio tipo de solicitacao"*.
        "fora": ["sobrenome", "assunto"],
        "campos": {
            "primeiro-nome": {"rotulo": "Nome completo"},
            # 🔵 *"deixar em fantasma o modelo de preenchimento"* -- as palavras
            # dele, inclusive o exemplo. O espaco e o tracinho a tela poe
            # sozinha enquanto se digita (`validacao_campo.mascarar`).
            "telefone": {"fantasma": "(00) 123456789"},
            # 🔵 As 4 opcoes dele, EM ORDEM ALFABETICA ("so coloque em ordem
            # alfabetica").
            #
            # 🚨 OS VALORES SAO NOSSOS, e de proposito: os do Bitrix (1340,
            # 1342, ...) eram ids da base deles e nao significam nada aqui. Em
            # slug porque e deste campo que vai sair o mapa para o `problemaId`
            # do Harmonit -- e ler "rastreamento" numa decisao e melhor que ler
            # "1348".
            #
            # ⚠️ SAIRAM 8 OPCOES do Bitrix, entre elas as DUAS de Backup
            # (ativacao e desativacao) que nao tinham candidato em nenhum dos 24
            # problemas do Harmonit. A pendencia dos "dois Backup" morre aqui:
            # viraram uma, "Acesso ao Backup de dados".
            "tipo-de-solicitacao": {"opcoes": [
                {"value": "backup",       "label": "Acesso ao Backup de dados"},
                {"value": "veiculo",      "label": "Problemas com o veiculo"},
                {"value": "rastreamento", "label": "Problemas com rastreamento"},
                {"value": "sugestao",     "label": "Sugestao de melhoria"},
            ]},
            # 🔵 *"pode ser um pouco mais alto para exprimir que pode colocar
            # mais texto"*. ⚠️ O campo e `string` no Bitrix -- sem isto ele
            # seria uma linha so, que diz a quem preenche "escreva pouco".
            "detalhe-a-ocorrencia": {"linhas": 6},
            # 🔵 *"se ja tem o cliente validado, ja podemos trazer no campo de
            # veiculo placa os veiculos que ele tem ativo na Weso"*.
            "veiculo-e-placa-somente-se-for-referente": {
                "rotulo": "Veiculo e placa",
                "fonte": "weso_placas",
            },
        },
    },
}

# A mascara e a conferencia de cada campo, por `nosso_nome`.''',
       "carga: a tabela AJUSTES")

trocar(c, '''        {"titulo": "Seus dados",
         "campos": ["primeiro-nome", "sobrenome", "e-mail", "telefone"]},
        {"titulo": "A solicitacao",
         "campos": ["tipo-de-solicitacao", "assunto", "detalhe-a-ocorrencia"]},''',
       '''        # ⚠️ Sem `sobrenome` e sem `assunto`: os dois sairam em 29/10 (ver
        # `AJUSTES`). Etapa que cita campo que nao existe PARA na carga, e e
        # por isso que as duas tabelas tem de andar juntas.
        {"titulo": "Seus dados",
         "campos": ["primeiro-nome", "e-mail", "telefone"]},
        {"titulo": "A solicitacao",
         "campos": ["tipo-de-solicitacao", "detalhe-a-ocorrencia"]},''',
       "carga: etapas sem sobrenome e sem assunto")

trocar(c, '''                                         etapas=ETAPAS.get(codigo),
                                         validacoes=VALIDACOES.get(codigo))''',
       '''                                         etapas=ETAPAS.get(codigo),
                                         validacoes=VALIDACOES.get(codigo),
                                         ajustes=AJUSTES.get(codigo))''',
       "carga: passa os ajustes")

print()
print("ok")
