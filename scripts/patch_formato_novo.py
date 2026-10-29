# -*- coding: utf-8 -*-
"""Patch 29/10: o FORMATO NOVO do formulario publico chega ao backend.

Pedido dele: *"ajuste ele no novo formato 'etapas, logo, cor, placas, etc'"* --
o formulario de Suporte. O desenho e o de 23/10
(`Desktop\\Formularios_Movisat_Design.md`, blocos 1, 3, 5 e 6).

Este patch mexe em `movizap/formularios.py`: le `formato`, `etapas` e
`validacao`, e a carga passa a escrever os tres.

🚨 Idempotente: cada troca confere se ja esta aplicada antes de mexer, e para
sem gravar nada se o trecho velho nao estiver exatamente uma vez no arquivo.
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
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias do "
                 f"trecho velho, esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


f = RAIZ / "movizap" / "formularios.py"
print(f.name)

trocar(f, """        \"\"\"SELECT id, codigo, slug, titulo, setor, botao, descricao, ativo,
                  gera_os, problema_id, tipo_os_id, prioridade_id
             FROM formulario WHERE slug = %s\"\"\", (slug,))""",
       """        \"\"\"SELECT id, codigo, slug, titulo, setor, botao, descricao, ativo,
                  gera_os, problema_id, tipo_os_id, prioridade_id,
                  formato, etapas
             FROM formulario WHERE slug = %s\"\"\", (slug,))""",
       "definicao: formato e etapas")

trocar(f, """        \"\"\"SELECT nome, nosso_nome, rotulo, tipo, obrigatorio, multiplo,
                  visivel, ordem, opcoes, ajuda
             FROM formulario_campo WHERE formulario_id = %s""",
       """        \"\"\"SELECT nome, nosso_nome, rotulo, tipo, obrigatorio, multiplo,
                  visivel, ordem, opcoes, ajuda, validacao
             FROM formulario_campo WHERE formulario_id = %s""",
       "definicao: validacao do campo")

trocar(f, """def gravar_definicao(bruto: dict, codigo: str, slug: str, setor: str,
                     titulo: str | None = None, painel: str | None = None,
                     ordem: int = 100) -> dict:""",
       """def gravar_definicao(bruto: dict, codigo: str, slug: str, setor: str,
                     titulo: str | None = None, painel: str | None = None,
                     ordem: int = 100, formato: str = "classico",
                     etapas: list | None = None,
                     validacoes: dict | None = None) -> dict:""",
       "gravar_definicao: tres parametros novos")

trocar(f, """    🚨 ALVO DE `show` NASCE ESCONDIDO -- é aqui que a tradução acontece, e o
    porquê está em `visiveis()`.
    \"\"\"""",
       """    🚨 ALVO DE `show` NASCE ESCONDIDO -- é aqui que a tradução acontece, e o
    porquê está em `visiveis()`.

    🚨 `formato`, `etapas` e `validacoes` SÃO REESCRITOS A CADA CARGA, como o
    `painel` e ao contrário de `ativo`: são decisão dele e vivem no
    `scripts/carregar_formularios.py`, então mudar o agrupamento das etapas ou
    ligar o formato novo no 2º formulário não exige migração nem deploy.

    ⚠️ `validacoes` é `{nosso_nome: regra}`, e as etapas também citam campo
    pelo `nosso_nome`. Casar pelo nome do Bitrix
    (`DEAL_UF_CRM_1647530180887`) seria ilegível para quem revisa -- e quem
    revisa é ele.
    \"\"\"""",
       "gravar_definicao: docstring")

trocar(f, """        \"\"\"INSERT INTO formulario (codigo, slug, titulo, setor, botao,
                                   bitrix_id, bitrix_sec, painel, ordem)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
       """        \"\"\"INSERT INTO formulario (codigo, slug, titulo, setor, botao,
                                   bitrix_id, bitrix_sec, painel, ordem,
                                   formato, etapas)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
       "gravar_definicao: colunas do INSERT")

trocar(f, """                  painel = EXCLUDED.painel,
                  ordem = EXCLUDED.ordem, atualizado_em = now()
        RETURNING id, ativo\"\"\",
        (codigo, slug,
         (titulo or dados.get("title") or "").strip() or slug,
         setor, (dados.get("buttonCaption") or "Enviar").strip()[:60],
         str(bruto.get("id")), bruto.get("sec"), painel, ordem))""",
       """                  painel = EXCLUDED.painel,
                  formato = EXCLUDED.formato, etapas = EXCLUDED.etapas,
                  ordem = EXCLUDED.ordem, atualizado_em = now()
        RETURNING id, ativo\"\"\",
        (codigo, slug,
         (titulo or dados.get("title") or "").strip() or slug,
         setor, (dados.get("buttonCaption") or "Enviar").strip()[:60],
         str(bruto.get("id")), bruto.get("sec"), painel, ordem,
         formato,
         json.dumps(etapas, ensure_ascii=False) if etapas else None))""",
       "gravar_definicao: valores do INSERT")

trocar(f, """    usados = set()
    for i, campo in enumerate(campos):
        opcoes = [{"value": str(it.get("value")), "label": it.get("label") or ""}
                  for it in (campo.get("items") or [])]
        banco.executar(
            \"\"\"INSERT INTO formulario_campo
                   (formulario_id, nome, nosso_nome, rotulo, tipo, obrigatorio,
                    multiplo, visivel, ordem, opcoes, ajuda)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)\"\"\",
            (linha["id"], campo["name"][:80],
             nome_legivel(campo.get("label") or "", campo["name"], usados),
             (campo.get("label") or "").strip(), campo["type"],
             bool(campo.get("required")), bool(campo.get("multiple")),
             campo["name"] not in alvos_de_show, i,
             json.dumps(opcoes, ensure_ascii=False),
             (campo.get("hint") or "").strip() or None))
""",
       """    usados = set()
    validacoes = validacoes or {}
    sem_campo = set(validacoes)
    nossos_todos: list[str] = []
    nossas_perguntas: list[str] = []
    for i, campo in enumerate(campos):
        opcoes = [{"value": str(it.get("value")), "label": it.get("label") or ""}
                  for it in (campo.get("items") or [])]
        nosso = nome_legivel(campo.get("label") or "", campo["name"], usados)
        sem_campo.discard(nosso)
        nossos_todos.append(nosso)
        if campo["type"] not in TIPOS_DECORATIVOS:
            nossas_perguntas.append(nosso)
        banco.executar(
            \"\"\"INSERT INTO formulario_campo
                   (formulario_id, nome, nosso_nome, rotulo, tipo, obrigatorio,
                    multiplo, visivel, ordem, opcoes, ajuda, validacao)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)\"\"\",
            (linha["id"], campo["name"][:80], nosso,
             (campo.get("label") or "").strip(), campo["type"],
             bool(campo.get("required")), bool(campo.get("multiple")),
             campo["name"] not in alvos_de_show, i,
             json.dumps(opcoes, ensure_ascii=False),
             (campo.get("hint") or "").strip() or None,
             validacoes.get(nosso)))

    # 🚨 MÁSCARA SEM CAMPO PARA NA CARGA, nunca na tela do cliente. Um
    # `nosso_nome` escrito errado na tabela viraria campo sem máscara -- e
    # ninguém notaria, porque a tela ficaria só um pouco mais permissiva.
    if sem_campo:
        raise DadoInvalido(
            f"{codigo}: validacao citando campo que nao existe: "
            + ", ".join(sorted(sem_campo)))

    # 🚨 E A MESMA RÉGUA PARA AS ETAPAS, com os dois erros possíveis:
    #   · etapa que cita campo inexistente -> some da tela em silêncio;
    #   · pergunta que ficou fora de toda etapa -> o cliente NUNCA a vê, e o
    #     formulário segue "funcionando" com uma pergunta menos.
    # O segundo é o perigoso, e é por isso que a conferência é dos dois lados.
    if etapas:
        citados = [n for e in etapas for n in (e.get("campos") or [])]
        fantasmas = sorted(set(citados) - set(nossos_todos))
        de_fora = sorted(set(nossas_perguntas) - set(citados))
        if fantasmas or de_fora:
            raise DadoInvalido(
                f"{codigo}: etapas erradas -- "
                f"campos que nao existem: {fantasmas or 'nenhum'}; "
                f"perguntas fora de toda etapa: {de_fora or 'nenhuma'}")
""",
       "gravar_definicao: validacao por campo e a conferencia das etapas")

print()
print("ok. Proximo: patch_formato_novo_2.py (main.py e a carga)")
