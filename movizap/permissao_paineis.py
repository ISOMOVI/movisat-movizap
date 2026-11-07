# -*- coding: utf-8 -*-
r"""A CONCESSÃO DE PAINEL POR PESSOA — o motor da aba `CFG_15.1` (06/11).

🔵 Pedido dele: *"em configuração, crie uma aba de permissão para os paineis,
ali vou definir quem pode ver o que e por aba tbm, como notará que o pós venda
ja possui abas"*.

🚨 **POR QUE PRECISOU DE CONCEITO NOVO.** A permissão do MoviZap era só por
PERFIL: `atendente.perfil` → um conjunto de nomes (`telas.PERFIS`), e cada tela
declara UM nome. Nesse modelo não existe *"esta pessoa, esta aba"* — e as três
telas de painel são `permissao: owner`, que `pode_acessar` recusa para todo
não-owner. Medido em 06/11: só o Iago (121) alcançava qualquer painel, e a
`atendente_time_permissao` estava vazia.

🚨 **A CONCESSÃO VENCE O `owner` DA TELA.** É a regra desta entrega, e sem ela a
aba nova gravaria sem efeito. ⚠️ A tela NÃO é rebaixada: continua `owner` no
registro, e quem não tem linha em `tela_concedida` continua barrado. O que
existe é uma lista de exceções nomeadas, cada uma com autor e hora.

🚨 **SÓ TELA DO GRUPO "PAINÉIS" É CONCEDÍVEL, e a trava é aqui, não na tela.**
Tela de marcar é fácil de generalizar por descuido, e uma tabela genérica com
uma tela genérica concederia `CFG_1.1` (os canais do WhatsApp) por acidente. O
conjunto sai do REGISTRO (`grupo == "Painéis"`), não de uma lista escrita à mão:
painel novo entra sozinho, e é isso que o Financeiro vai precisar.

⚠️ **O OWNER NÃO RECEBE CONCESSÃO.** Ele já vê tudo pela primeira linha de
`pode_acessar`; conceder a ele criaria linha que não muda nada e uma marca na
tela que diria "concedido" quando o motivo real é ser owner. Oferecer o gesto
sem efeito é o precedente do `ModalAgendar`.
"""
from movizap import banco
from movizap import telas as registro_telas

# O grupo do registro que esta aba governa. 🚨 Não é lista de códigos: é o
# grupo, para painel novo (o Financeiro, quando ele der as colunas) entrar sem
# tocar este arquivo.
GRUPO = "Painéis"


def _titulos_de_aba() -> dict[str, str]:
    """O título da ABA, que mora no BANCO (`painel_aba.titulo`).

    🚨 É INDISPENSÁVEL NESTA TELA, e é o detalhe que ele antecipou: *"como
    notará que o pós venda ja possui abas"*. No registro, `PNL_1.2` e `PNL_1.3`
    têm as DUAS o título "Pós-venda" (correção dele de 05/11: o item de menu é
    o do painel). Sem o título da aba, a grade teria duas colunas chamadas
    "Pós-venda" e marcar uma ou outra seria chute.

    ⚠️ Degrada para vazio: se a tabela não responder, a tela cai no título do
    registro -- coluna com nome repetido é ruim, coluna que não aparece é pior.
    """
    try:
        return {
            r["codigo_tela"]: r["titulo"]
            for r in banco.varios(
                "SELECT codigo_tela, titulo FROM painel_aba WHERE ativo"
            )
        }
    except Exception:  # noqa: BLE001 -- ver a advertência acima
        return {}


def concediveis() -> list[dict]:
    """As telas que esta aba pode conceder, na ordem do registro.

    ⚠️ `aba_de` VEM NA RESPOSTA e a tela precisa dele: é o que permite desenhar
    a aba de dentro aninhada na principal, e é o que ele chamou de *"por aba
    tbm"*.
    """
    abas = _titulos_de_aba()
    return [
        {
            "codigo": t["codigo"],
            "titulo": t["titulo"],
            # ⚠️ DOIS títulos, e os dois são verdade: `titulo` é o do menu
            # (vem do registro) e `aba_titulo` é o da coluna de abas (vem do
            # banco). A tela mostra o segundo quando ele existe.
            "aba_titulo": abas.get(t["codigo"]),
            "rota": t["rota"],
            "descricao": t["descricao"],
            "aba_de": t.get("aba_de"),
            # ⚠️ A permissão do registro vai junto por honestidade: a concessão
            # é exceção, não rebaixamento -- a tela diz isso em cada coluna.
            "permissao": t["permissao"],
        }
        for t in registro_telas.ativas()
        if registro_telas.grupo_da(t) == GRUPO
    ]


def codigos_concediveis() -> set[str]:
    """🚨 SAI DO REGISTRO, não do banco: a lista do que é concedível é a trava
    da rota, e trava não pode depender de uma tabela que uma falha de leitura
    esvazia -- conjunto vazio aqui recusaria tudo, mas um dia poderia recusar
    nada se alguém invertesse o sentido. O `_titulos_de_aba` é só rótulo."""
    return {t["codigo"] for t in registro_telas.ativas()
            if registro_telas.grupo_da(t) == GRUPO}


class TelaNaoConcedivel(Exception):
    """Código fora do grupo Painéis. É recusa de regra, não de digitação."""


def pessoas() -> list[dict]:
    """Quem aparece na grade: atendente ATIVO, o owner inclusive.

    ⚠️ O OWNER APARECE, mas marcado e sem caixa para marcar: tirá-lo da lista
    faria a grade parecer incompleta, e deixá-lo marcável ofereceria um gesto
    sem efeito. A tela mostra por que ele vê tudo.
    ⚠️ INATIVO NÃO APARECE: conta desligada não entra em tela de permissão --
    quem religar a conta decide a permissão na hora.
    """
    return banco.varios(
        """SELECT id, nome, email, perfil, owner
             FROM atendente
            WHERE ativo
         ORDER BY owner DESC, nome"""
    )


def concessoes() -> list[dict]:
    """Todas as concessões de painel que existem hoje.

    ⚠️ FILTRA PELO GRUPO na leitura também: se um dia alguém gravar um código
    de fora por outro caminho, esta aba não passa a exibi-lo nem a revogá-lo --
    ela governa os painéis e só.
    """
    codigos = codigos_concediveis()
    if not codigos:  # pragma: no cover -- só se o grupo Painéis esvaziar
        return []
    return banco.varios(
        """SELECT c.atendente_id, c.codigo_tela, c.concedida_em,
                  c.concedida_por, a.nome AS concedida_por_nome
             FROM tela_concedida c
             LEFT JOIN atendente a ON a.id = c.concedida_por
            WHERE c.codigo_tela = ANY(%s)
         ORDER BY c.atendente_id, c.codigo_tela""",
        (list(codigos),),
    )


def do_atendente(atendente_id: int) -> set[str]:
    """Os códigos concedidos a ESTA pessoa. Lido a cada requisição.

    🚨 NÃO FILTRA PELO GRUPO, e é de propósito: esta é a função que o
    `auth.buscar_usuario` usa para montar a identidade, e ela tem de devolver
    tudo o que foi concedido. O filtro de grupo é da ABA (quem concede), não da
    porta (quem entra) -- senão uma concessão gravada hoje deixaria de valer
    amanhã se a tela mudasse de grupo, em silêncio.
    """
    return {
        r["codigo_tela"]
        for r in banco.varios(
            "SELECT codigo_tela FROM tela_concedida WHERE atendente_id = %s",
            (atendente_id,),
        )
    }


def definir(atendente_id: int, codigos: list[str],
            concedida_por: int | None = None) -> set[str]:
    """Põe a lista de painéis DESTA pessoa exatamente como `codigos` diz.

    🚨 SUBSTITUI, não acrescenta: a tela manda o estado inteiro da linha dela, e
    é isso que faz desmarcar uma caixa revogar de verdade. Um POST por caixa
    pareceria mais simples e deixaria a tela e o banco divergirem no primeiro
    clique perdido.

    🚨 RECUSA CÓDIGO FORA DO GRUPO PAINÉIS e recusa o owner -- as duas são
    regra, e por isso estouram em vez de ignorar em silêncio. ⚠️ Ignorar seria
    pior: a tela gravaria com 200 e mostraria outra coisa na releitura.
    """
    permitidos = codigos_concediveis()
    pedidos = set(codigos)
    fora = pedidos - permitidos
    if fora:
        raise TelaNaoConcedivel(
            "esta aba concede só os painéis; fora da lista: " f"{sorted(fora)}"
        )

    quem = banco.um("SELECT id, owner, ativo FROM atendente WHERE id = %s",
                    (atendente_id,))
    if quem is None:
        raise TelaNaoConcedivel(f"atendente {atendente_id} não existe")
    if quem["owner"]:
        raise TelaNaoConcedivel(
            "o owner já alcança todos os painéis; conceder a ele seria uma "
            "linha sem efeito"
        )
    if not quem["ativo"]:
        raise TelaNaoConcedivel(
            "conta inativa não recebe painel -- religue a conta primeiro"
        )

    atuais = do_atendente(atendente_id) & permitidos
    # ⚠️ Só o DELTA é escrito: regravar o que já estava concedido trocaria
    # `concedida_em` e `concedida_por` por nada, e quem concedeu quando é o
    # único histórico que esta tabela guarda.
    for codigo in sorted(atuais - pedidos):
        banco.executar(
            "DELETE FROM tela_concedida WHERE atendente_id = %s "
            "AND codigo_tela = %s",
            (atendente_id, codigo),
        )
    for codigo in sorted(pedidos - atuais):
        banco.executar(
            """INSERT INTO tela_concedida (atendente_id, codigo_tela,
                                           concedida_por)
                    VALUES (%s, %s, %s)
               ON CONFLICT (atendente_id, codigo_tela) DO NOTHING""",
            (atendente_id, codigo, concedida_por),
        )
    return do_atendente(atendente_id) & permitidos


def grade() -> dict:
    """O que a aba `CFG_15.1` desenha, pronto: colunas, linhas e as marcas."""
    telas = concediveis()
    por_pessoa: dict[int, dict] = {}
    for c in concessoes():
        por_pessoa.setdefault(c["atendente_id"], {})[c["codigo_tela"]] = {
            "concedida_em": c["concedida_em"],
            "concedida_por": c["concedida_por"],
            "concedida_por_nome": c["concedida_por_nome"],
        }
    linhas = []
    for p in pessoas():
        marcas = por_pessoa.get(p["id"], {})
        linhas.append({
            "atendente_id": p["id"],
            "nome": p["nome"],
            "email": p["email"],
            "perfil": p["perfil"],
            "owner": p["owner"],
            # ⚠️ O owner vem com TODAS marcadas e `editavel: false`: a tela diz
            # a verdade (ele vê tudo) sem oferecer um gesto que não faz nada.
            "concedidas": ([t["codigo"] for t in telas] if p["owner"]
                           else sorted(marcas)),
            "detalhe": marcas,
            "editavel": not p["owner"],
        })
    return {"telas": telas, "pessoas": linhas, "grupo": GRUPO}
