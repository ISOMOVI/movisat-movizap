"""Importa times e atendentes do Chatwoot para o MoviZap — uma vez, e de novo
sem duplicar.

Decisão de 06/08: **times e atendentes nascem importados do Chatwoot**, que é
a estrutura que já está em uso; a partir daí o cadastro é na plataforma
(CAD_2.1 e CAD_2.2). O Chatwoot é ponto de partida, não fonte permanente.

🚨 O QUE ESTE SCRIPT NÃO FAZ:
  - não apaga nada;
  - não mexe em time que já existe (as descrições do MoviZap são melhores que
    as do Chatwoot, que estão vazias em 6 dos 7);
  - não define senha. Ninguém entra no painel por causa desta importação --
    `senha_hash` fica NULL e `auth.validar_login` recusa antes do bcrypt.

⚠️ Lê o Chatwoot por `docker exec psql` de propósito: assim nenhuma senha de
banco precisa existir neste processo nem passar por linha de comando.

Uso:  PYTHONPATH=. ./venv/bin/python scripts/importar_chatwoot.py [--aplicar]
Sem `--aplicar` ele só mostra o que faria.
"""
import argparse
import subprocess
import sys

from movizap import banco

CONTAINER = "movisat_postgres"
BANCO_CHATWOOT = "chatwoot_production"
USUARIO_CHATWOOT = "chatwoot"

# Perfil de tela no MoviZap. Não vem do Chatwoot: lá o papel é 'administrator'
# ou 'agent', que não descreve o que a pessoa enxerga AQUI.
# ⚠️ O owner continua sendo a conta do .env. Ninguém importado nasce owner --
# duas contas donas é o tipo de coisa que só se descobre no dia do problema.
PERFIL_POR_EMAIL = {
    "iago@movisat.com.br": "admin",
    "financeiro@movisat.com.br": "atendimento",
    "suporte@movisat.com.br": "atendimento",
    "comercial@movisat.com.br": "atendimento",
}
PERFIL_PADRAO = "atendimento"


def _consultar(sql: str) -> list[list[str]]:
    """Roda um SELECT no Chatwoot e devolve as linhas já quebradas.

    `-t` tira cabeçalho, `-A` tira alinhamento, `-F` fixa o separador. Sem os
    três, a saída do psql é texto bonito e imparseável.
    """
    saida = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", USUARIO_CHATWOOT,
         "-d", BANCO_CHATWOOT, "-t", "-A", "-F", "\x1f", "-c", sql],
        capture_output=True, text=True, check=True,
    ).stdout
    return [linha.split("\x1f") for linha in saida.splitlines() if linha.strip()]


def ler_chatwoot() -> dict:
    times = _consultar("SELECT id, name, COALESCE(description,'') FROM teams ORDER BY id")
    usuarios = _consultar(
        "SELECT id, name, email FROM users WHERE email IS NOT NULL ORDER BY id")
    membros = _consultar(
        "SELECT tm.user_id, t.name FROM team_members tm "
        "JOIN teams t ON t.id = tm.team_id ORDER BY tm.user_id")
    return {"times": times, "usuarios": usuarios, "membros": membros}


def login_de(email: str, usados: set[str]) -> str:
    """O login sai da parte local do e-mail: `suporte@movisat.com.br` -> `suporte`.

    ⚠️ `ux_atendente_login` é único em lower(login). Se dois e-mails tiverem a
    mesma parte local, o segundo ganha sufixo em vez de estourar no meio da
    importação.
    """
    base = email.split("@")[0].strip().lower() or "atendente"
    candidato, n = base, 2
    while candidato in usados:
        candidato, n = f"{base}{n}", n + 1
    usados.add(candidato)
    return candidato


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true",
                        help="grava de verdade; sem isto só mostra o plano")
    args = parser.parse_args()

    dados = ler_chatwoot()
    banco.abrir()

    print(f"Chatwoot: {len(dados['times'])} times, {len(dados['usuarios'])} usuários, "
          f"{len(dados['membros'])} vínculos.\n")

    # ---------------------------------------------------------------- times
    nossos = {t["nome"].casefold(): t for t in
              banco.varios("SELECT id, nome, descricao FROM time")}
    faltando = []
    for _id, nome, _desc in dados["times"]:
        if nome.casefold() in nossos:
            print(f"  time  = {nome}  (já existe, não mexo)")
        else:
            faltando.append(nome)
            print(f"  time  + {nome}  (criar)")

    if args.aplicar:
        for nome in faltando:
            banco.executar("INSERT INTO time (nome) VALUES (%s)", (nome,))
        if faltando:
            nossos = {t["nome"].casefold(): t for t in
                      banco.varios("SELECT id, nome, descricao FROM time")}

    # ----------------------------------------------------------- atendentes
    print()
    ja_tem = {a["origem"]: a for a in banco.varios(
        "SELECT id, origem, login, nome FROM atendente WHERE origem IS NOT NULL")}
    usados = {a["login"].lower() for a in
              banco.varios("SELECT login FROM atendente")}

    por_usuario_id = {}
    for cw_id, nome, email in dados["usuarios"]:
        origem = f"chatwoot:{cw_id}"
        perfil = PERFIL_POR_EMAIL.get(email.lower(), PERFIL_PADRAO)
        if origem in ja_tem:
            por_usuario_id[cw_id] = ja_tem[origem]["id"]
            print(f"  conta = {nome} <{email}>  (já importada, atualizo nome/e-mail)")
            if args.aplicar:
                banco.executar(
                    "UPDATE atendente SET nome = %s, email = %s, atualizado_em = now() "
                    "WHERE id = %s", (nome, email, ja_tem[origem]["id"]))
            continue

        login = login_de(email, usados)
        print(f"  conta + {nome} <{email}>  login={login}  perfil={perfil}  SEM SENHA")
        if args.aplicar:
            linha = banco.um(
                """INSERT INTO atendente (login, nome, email, perfil, origem)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (login, nome, email, perfil, origem))
            por_usuario_id[cw_id] = linha["id"]

    # -------------------------------------------------------------- membros
    print()
    for cw_user_id, nome_time in dados["membros"]:
        alvo = por_usuario_id.get(cw_user_id)
        time_nosso = nossos.get(nome_time.casefold())
        print(f"  time  » {nome_time} recebe o usuário {cw_user_id}")
        if args.aplicar and alvo and time_nosso:
            banco.executar(
                "INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING", (alvo, time_nosso["id"]))

    if not args.aplicar:
        print("\n(simulação -- nada foi gravado. Rode com --aplicar.)")
        return 0

    # ------------------------------------------------- conferir RELENDO
    print("\nConferência, relendo o banco:")
    print("  atendentes:", banco.um("SELECT COUNT(*) AS n FROM atendente")["n"])
    print("  vínculos  :", banco.um("SELECT COUNT(*) AS n FROM atendente_time")["n"])
    print("  com senha :", banco.um(
        "SELECT COUNT(*) AS n FROM atendente WHERE senha_hash IS NOT NULL")["n"],
        "(esperado 0 -- a senha se define na tela)")
    for linha in banco.varios(
            """SELECT a.nome, a.login, a.perfil,
                      COALESCE(string_agg(t.nome, ', ' ORDER BY t.nome), '--') AS times
                 FROM atendente a
                 LEFT JOIN atendente_time at ON at.atendente_id = a.id
                 LEFT JOIN time t ON t.id = at.time_id
                GROUP BY a.id, a.nome, a.login, a.perfil ORDER BY a.nome"""):
        print(f"    {linha['nome']:20} {linha['login']:12} {linha['perfil']:12} "
              f"{linha['times']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
