"""O que o Bitrix sabe sobre um telefone ou e-mail. SÓ CONSULTA.

🚨 ISTO NÃO IDENTIFICA NINGUÉM. Responde *"o que se sabe sobre este número?"*,
nunca *"de quem é este número?"* -- a segunda pergunta continua sendo do
cadastro, e só se responde com prova ou com uma pessoa confirmando.

Por quê: dos 14.214 contatos importados, 7.113 são prospect, 309 são ex-cliente
e 1.810 não têm tipo. Tratar isso como cadastro faria o painel oferecer
conversa com quem nunca foi cliente.
"""
from . import banco


def por_chave(tipo: str, valor: str) -> list[dict]:
    """Quem, no Bitrix, tem este telefone/e-mail. Pode ser mais de um."""
    if not valor:
        return []
    return banco.varios(
        """SELECT c.id, c.id_externo, c.nome, c.sobrenome, c.cargo,
                  c.empresa_nome, c.tipo
             FROM bitrix_chave k JOIN bitrix_contato c ON c.id = k.contato_id
            WHERE k.tipo = %s AND k.valor = %s
            ORDER BY c.empresa_nome NULLS LAST
            LIMIT 5""", (tipo, valor))


def observacao(telefone_e164: str | None = None,
               email: str | None = None) -> dict | None:
    """O que mostrar no selo amarelo, ou None se não há nada.

    ⚠️ Devolve `cadastro: False` sempre -- é o campo que impede a tela tratar
    isto como vínculo por engano.
    """
    achados = []
    if telefone_e164:
        achados += por_chave("telefone", telefone_e164)
    if email:
        achados += por_chave("email", email.strip().lower())
    if not achados:
        return None

    primeiro = achados[0]
    nome = " ".join(x for x in (primeiro["nome"], primeiro["sobrenome"]) if x)
    return {
        "cadastro": False,          # 🚨 nunca é vínculo
        "nome": nome or None,
        "empresa": primeiro["empresa_nome"],
        "cargo": primeiro["cargo"],
        "tipo": primeiro["tipo"],
        "quantos": len(achados),
    }
