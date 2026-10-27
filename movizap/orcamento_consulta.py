"""Ler os orçamentos emitidos: a aba Orçamentos (`ORC_1.1`, 26/10).

🔵 *"Painel de orçamento salvo para consulta apenas; Consultar em grid os
orçamentos aba nova 'Orçamentos' (como das ligações)"*.

Módulo separado de propósito: `orcamento.py` é o caminho de ESCRITA -- ele
gasta o número, monta o PDF e envia na conversa, e está no ar desde 21/10. A
mesma divisão de `ligacoes.py` (agente) e `ligacoes_consulta.py` (aba), que foi
o molde desta aba inteira.

🚨 **SÓ CONSULTA, E ISSO NÃO É LIMITAÇÃO TÉCNICA.** Orçamento emitido não muda
de conteúdo: o `reenviar()` remonta o MESMO papel a partir do que está gravado.
Então aqui não existe editar, cancelar nem emitir -- e a tela diz isso em
texto, em vez de deixar a ausência de botão explicar.

🚨 **O NOME DO TÉCNICO NÃO É `contato.nome`.** Em conversa de técnico o
`contato.nome` é o telefone cru -- medido em 26/10: os três orçamentos
emitidos sairiam todos como `+5518998116168`. O nome bom está em
`contato.harmonit_tecnico_nome`, que vem do vínculo com o Harmonit (migração
071). Daí o COALESCE, nessa ordem, com o telefone como último recurso.

🚨 **O PDF NÃO GANHA ROTA NOVA.** Ele é uma `midia` com `sala_id` nulo, e
`/api/midia/{id}/ver` já serve esse caso a quem tem `ATD_1.2` -- a mesma
permissão desta aba. Rota própria seria um segundo caminho para o mesmo
arquivo, e dois caminhos para o mesmo dado é como eles divergem.

⚠️ **`ordens_os` é um array de números, sem chave estrangeira** (migração 070).
Não há como juntar com a OS aqui dentro: a OS vive no Harmonit. O filtro por OS
procura o número DENTRO do array, e é tudo o que dá para prometer.
"""
import logging

from . import banco, orcamento
from .operacao import DadoInvalido

log = logging.getLogger("movizap.orcamento.consulta")

POR_PAGINA = 50
POR_PAGINA_MAX = 200

# 🚨 NÃO EXISTE EXPORTAR AQUI, e é escolha, não esquecimento. A aba de
# Ligações exporta porque ele pediu *"exportar e importar"* naquela; desta ele
# pediu *"para consulta apenas"*. Exportar orçamento é valor e dado de cliente
# saindo do sistema, o que na LIG_1.1 obrigou a gravar quem exportou
# (`ligacao_exportacao`) -- então é frente com tabela própria, não um botão.
# Se ele pedir, o molde é `ligacoes_consulta.para_csv` + `relatorio_csv`.

# As linhas de cada orçamento em uma consulta só. Subconsulta em vez de JOIN:
# com JOIN, um orçamento de duas linhas viraria duas linhas no grid.
_ITENS = """(SELECT json_agg(json_build_object(
                    'ordem', i.ordem, 'servico', i.servico,
                    'quantidade', i.quantidade, 'unidade', i.unidade,
                    'preco_unit_centavos', i.preco_unit_centavos,
                    'valor_centavos', i.valor_centavos)
                  ORDER BY i.ordem)
                FROM orcamento_item i WHERE i.orcamento_id = o.id) AS itens"""

# ⚠️ O elo com o agendamento é de LÁ para CÁ (`agendamento.orcamento_id`), e
# só existe quando o orçamento foi emitido antes do compromisso, no mesmo
# modal. Medido em 26/10: 1 dos 3. Por isso é subconsulta e pode vir nulo --
# "sem agendamento" é o estado comum, não defeito.
_AGENDAMENTO = """(SELECT json_build_object('id', g.id, 'inicio', g.inicio,
                                            'estado', g.estado,
                                            'cliente_nome', g.cliente_nome)
                     FROM agendamento g
                    WHERE g.orcamento_id = o.id
                    ORDER BY g.id LIMIT 1) AS agendamento"""

# 🚨 O nome do técnico. Ver o aviso do topo: `contato.nome` é o telefone.
_TECNICO = "COALESCE(c.harmonit_tecnico_nome, c.nome) AS tecnico"


def _filtros(de=None, ate=None, numero=None, tecnico_contato_id=None,
             atendente_id=None, os_numero=None, com_pdf=None) -> tuple[str, list]:
    """Monta o WHERE. Devolve sempre pedaço válido, mesmo sem filtro nenhum."""
    onde, valores = ["TRUE"], []

    if de:
        onde.append("o.criado_em >= %s")
        valores.append(de)
    if ate:
        # A data de fim é INCLUSIVA: quem filtra "até 26/10" espera o dia 26
        # inteiro, não até a meia-noite dele. Mesma régua da aba de Ligações.
        onde.append("o.criado_em < (%s::date + 1)")
        valores.append(ate)
    if numero:
        # 🚨 Número de orçamento é DOCUMENTO: busca exata, não parcial. Dizer
        # que o "1" casa com o 10 e o 21 seria útil num telefone e é errado
        # aqui -- quem procura um documento procura aquele.
        bruto = str(numero).strip()
        if not bruto.isdigit():
            raise DadoInvalido("O número do orçamento é um número inteiro.")
        onde.append("o.numero = %s")
        valores.append(int(bruto))
    if tecnico_contato_id:
        onde.append("o.tecnico_contato_id = %s")
        valores.append(int(tecnico_contato_id))
    if atendente_id:
        onde.append("o.criado_por = %s")
        valores.append(int(atendente_id))
    if os_numero:
        bruto = str(os_numero).strip()
        if not bruto.isdigit():
            raise DadoInvalido("O número da OS é um número inteiro.")
        onde.append("%s = ANY(o.ordens_os)")
        valores.append(int(bruto))
    if com_pdf is True:
        onde.append("o.midia_id IS NOT NULL")
    elif com_pdf is False:
        onde.append("o.midia_id IS NULL")

    return " AND ".join(onde), valores


def _enfeitar(linha: dict) -> dict:
    """Lista no lugar de NULL, e o dinheiro já escrito.

    🚨 O VALOR VIRA TEXTO AQUI, não na tela. `orcamento.reais()` é o único
    lugar do projeto que escreve centavos em português, e dividir por 100 no
    navegador seria um segundo lugar -- com outra regra de arredondamento.

    ⚠️ `_quantidade_texto` é privado do `orcamento.py` e é chamado aqui de
    propósito: ele é o único lugar que escreve "77 km" (sem casa decimal à
    toa, com vírgula), e é o MESMO texto que o PDF imprime. Copiar a regra
    para cá daria duas versões do mesmo número -- e o grid divergindo do papel
    é pior que a quebra de encapsulamento. Se ele virar público um dia, só
    cai o sublinhado.
    """
    linha["itens"] = linha.get("itens") or []
    linha["ordens_os"] = linha.get("ordens_os") or []
    linha["total"] = orcamento.reais(linha.get("total_centavos") or 0)
    for item in linha["itens"]:
        item["valor"] = orcamento.reais(item.get("valor_centavos") or 0)
        item["preco_unit"] = orcamento.reais(item.get("preco_unit_centavos") or 0)
        item["quantidade_texto"] = orcamento._quantidade_texto(
            item.get("quantidade") or 0, item.get("unidade") or "un")
    return linha


def consultar(pagina: int = 1, por_pagina: int = POR_PAGINA, **filtros) -> dict:
    """O grid da aba: uma página de orçamentos, com a soma do filtro.

    🚨 A soma é do FILTRO INTEIRO, não da página -- senão o rodapé mentiria a
    cada vez que alguém virasse a página. Mesma regra da aba de Ligações.
    """
    pagina = max(1, int(pagina or 1))
    por_pagina = min(POR_PAGINA_MAX, max(1, int(por_pagina or POR_PAGINA)))
    onde, valores = _filtros(**filtros)

    resumo = banco.um(
        f"""SELECT count(*) AS n, COALESCE(sum(o.total_centavos), 0) AS soma
              FROM orcamento o WHERE {onde}""", tuple(valores))
    total = resumo["n"]

    itens = banco.varios(
        f"""SELECT o.id, o.numero, o.criado_em, o.total_centavos, o.ordens_os,
                   o.midia_id, o.conversa_id, o.tecnico_contato_id,
                   o.criado_por, a.nome AS atendente,
                   {_TECNICO}, {_ITENS}, {_AGENDAMENTO}
              FROM orcamento o
              LEFT JOIN contato c ON c.id = o.tecnico_contato_id
              LEFT JOIN atendente a ON a.id = o.criado_por
             WHERE {onde}
             ORDER BY o.numero DESC
             LIMIT %s OFFSET %s""",
        tuple(valores) + (por_pagina, (pagina - 1) * por_pagina))

    return {"itens": [_enfeitar(i) for i in itens], "total": total,
            "pagina": pagina, "por_pagina": por_pagina,
            "paginas": max(1, -(-total // por_pagina)),
            "soma_centavos": int(resumo["soma"]),
            "soma": orcamento.reais(resumo["soma"])}


def tecnicos() -> list[dict]:
    """Os técnicos que têm orçamento, para o filtro da aba.

    ⚠️ Sai dos orçamentos, não do cadastro de contatos: filtro que oferece
    quem não tem nenhum orçamento devolve tela vazia e parece defeito.
    """
    return banco.varios(f"""
        SELECT o.tecnico_contato_id AS contato_id, {_TECNICO},
               count(*) AS orcamentos
          FROM orcamento o
          LEFT JOIN contato c ON c.id = o.tecnico_contato_id
         GROUP BY o.tecnico_contato_id, c.harmonit_tecnico_nome, c.nome
         ORDER BY 2""")


def atendentes() -> list[dict]:
    """Quem emitiu orçamento, para o filtro. Mesma régua do `tecnicos()`."""
    return banco.varios("""
        SELECT o.criado_por AS atendente_id, a.nome, count(*) AS orcamentos
          FROM orcamento o
          LEFT JOIN atendente a ON a.id = o.criado_por
         GROUP BY o.criado_por, a.nome
         ORDER BY a.nome""")
