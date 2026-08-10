"""Importa a exportacao do Bitrix como OBSERVACAO. Nao toca no cadastro.

🚨 NENHUMA LINHA DESTE SCRIPT ESCREVE EM `cliente`, `contato` OU
`contato_telefone`. Ele so preenche `bitrix_contato` e `bitrix_chave`. Se um
dia precisar promover algo ao cadastro, sera OUTRO script, com prova por
documento -- e com o usuario sabendo.

O arquivo do Bitrix e HTML com extensao .xls (exportacao tipica). 242 colunas.

Uso:  importar_bitrix.py <arquivo.xls>
"""
import html
import pathlib
import re
import shutil
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, telefone  # noqa: E402

GUARDA = pathlib.Path("/home/claude/movizap_bitrix")

COLUNAS = {
    "id": "ID",
    "nome": "Nome",
    "sobrenome": "Sobrenome",
    "cargo": "Posição",
    "empresa_nome": "Empresa",
    "empresa_id": "ID da empresa associada",
    "tipo": "Tipo de Contato",
}
FONES = ("Celular", "Telefone de trabalho", "Telefone de casa",
         "Outro número de telefone")
EMAILS = ("Email de trabalho", "E-mail de casa", "Outro e-mail")
DOCS = ("CPF", "CNPJ")


def celulas(linha: str) -> list[str]:
    return [html.unescape(re.sub(r"<[^>]*>", "", c)).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", linha, re.S)]


def main() -> int:
    origem = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                          else "/tmp/bitrix_contatos.xls")
    if not origem.is_file():
        sys.exit(f"nao encontrei {origem}")

    # ⚠️ O arquivo fica guardado FORA do backup, como a mídia. Ele é a prova do
    # que foi importado -- e não se duplica dentro do banco por isso.
    GUARDA.mkdir(parents=True, exist_ok=True)
    guardado = GUARDA / f"contatos_{origem.stat().st_mtime_ns}.xls"
    if not guardado.exists():
        shutil.copy2(origem, guardado)
    print(f"arquivo guardado em {guardado}")

    bruto = origem.read_text(encoding="utf-8", errors="replace")
    linhas = re.split(r"<tr[^>]*>", bruto)[1:]
    cab = celulas(linhas[0])
    ind = {k: cab.index(v) for k, v in COLUNAS.items() if v in cab}
    faltando = [v for k, v in COLUNAS.items() if v not in cab]
    if faltando:
        print(f"  ⚠️ colunas ausentes: {faltando}")

    banco.abrir()
    try:
        novos = atualizados = chaves = sem_id = 0
        with banco.cursor() as cur:
            for linha in linhas[1:]:
                c = celulas(linha)
                if len(c) < len(cab) // 2:
                    continue

                def g(nome_col):
                    j = cab.index(nome_col) if nome_col in cab else -1
                    return c[j].strip() if 0 <= j < len(c) else ""

                id_externo = (c[ind["id"]].strip()
                              if "id" in ind and ind["id"] < len(c) else "")
                if not id_externo:
                    sem_id += 1
                    continue

                cur.execute(
                    """INSERT INTO bitrix_contato
                         (id_externo, nome, sobrenome, cargo, empresa_nome,
                          empresa_id_externo, tipo)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id_externo) DO UPDATE
                          SET nome = EXCLUDED.nome,
                              sobrenome = EXCLUDED.sobrenome,
                              cargo = EXCLUDED.cargo,
                              empresa_nome = EXCLUDED.empresa_nome,
                              empresa_id_externo = EXCLUDED.empresa_id_externo,
                              tipo = EXCLUDED.tipo,
                              importado_em = now()
                       RETURNING id, (xmax = 0) AS criou""",
                    (id_externo, g("Nome") or None, g("Sobrenome") or None,
                     g("Posição") or None, g("Empresa") or None,
                     g("ID da empresa associada") or None,
                     g("Tipo de Contato") or None))
                linha_bd = cur.fetchone()
                contato_id = linha_bd["id"]
                if linha_bd["criou"]:
                    novos += 1
                else:
                    atualizados += 1

                # ── chaves normalizadas, que é por onde a consulta entra
                vistos = set()
                for campo in FONES:
                    for parte in re.split(r"[;,/]", g(campo)):
                        a = telefone.analisar(parte)
                        if a:
                            vistos.add(("telefone", a.e164))
                for campo in EMAILS:
                    for parte in re.split(r"[;,]", g(campo)):
                        e = parte.strip().lower()
                        if "@" in e and "." in e:
                            vistos.add(("email", e))
                for campo in DOCS:
                    d = re.sub(r"\D", "", g(campo))
                    if len(d) in (11, 14):
                        vistos.add(("documento", d))

                for tipo, valor in vistos:
                    cur.execute(
                        "INSERT INTO bitrix_chave (contato_id, tipo, valor) "
                        "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        (contato_id, tipo, valor))
                    chaves += 1

        print(f"\ncontatos novos      : {novos}")
        print(f"contatos atualizados: {atualizados}")
        print(f"sem ID (ignorados)  : {sem_id}")
        print(f"chaves gravadas     : {chaves}")

        # 🚨 RELER O ESTADO -- o contador acima é do laço, não do banco.
        print("\n=== CONFERINDO O ESTADO ===")
        print("  bitrix_contato:", banco.um("SELECT count(*) n FROM bitrix_contato")["n"])
        for r in banco.varios(
            "SELECT tipo, count(*) n, count(DISTINCT valor) d "
            "  FROM bitrix_chave GROUP BY tipo ORDER BY n DESC"):
            print(f"  chave {r['tipo']:10} {r['n']:6} linhas · {r['d']} valores distintos")

        print("\n  🚨 o cadastro foi tocado? (tem que ser NAO)")
        print("  clientes:", banco.um("SELECT count(*) n FROM cliente")["n"],
              "· contatos:", banco.um("SELECT count(*) n FROM contato")["n"],
              "· telefones:", banco.um("SELECT count(*) n FROM contato_telefone")["n"])
    finally:
        banco.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
