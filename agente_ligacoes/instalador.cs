// MoviZap - Instalar Ligacoes | UM arquivo que a pessoa recebe (v0.6, 19/10/2026)
//
// Pedido dele: "eles vao precisar dar um .exe apenas para rodar tudo" e
// "eu apagaria do PC para evitar engenharia reversa e senha do banco".
//
// Ele carrega dentro de si o agente, o instalador em PowerShell, o
// desinstalador, o LEIA-ME e o lancador. Ao rodar: extrai numa pasta
// temporaria, chama o instalador e sai de cena.
//
// NAO TEM SEGREDO NENHUM DENTRO. Nem chave, nem senha, nem credencial de
// banco -- e o PC nunca fala com o banco, so com o servico do MoviZap por
// HTTPS. O que individualiza este PC e a senha que o Iago dita na hora, e o
// algoritmo que a gera vive SO NA VPS. Decompilar este arquivo entrega a URL
// publica e nada mais; se o algoritmo rodasse aqui, quem o abrisse passaria a
// fabricar senhas para sempre.
//
// NAO ESPERA o PowerShell terminar, de proposito: enquanto este processo vive,
// o proprio arquivo .exe fica em uso e nao se deixa apagar -- e apagar o
// instalador no fim e parte do pedido dele.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

[assembly: AssemblyTitle("MoviZap - Instalar Backup de Ligacoes")]
[assembly: AssemblyProduct("MoviZap - Backup de Ligacoes")]
[assembly: AssemblyCompany("Movisat")]
[assembly: AssemblyDescription("Instala o backup do historico de ligacoes do MicroSIP no MoviZap.")]
[assembly: AssemblyCopyright("Movisat")]
[assembly: AssemblyVersion("0.7.0.0")]
[assembly: AssemblyFileVersion("0.7.0.0")]

static class Instalador
{
    static readonly string[] Carga = {
        "instalar.ps1",
        "movizap-ligacoes.ps1",
        "desinstalar.ps1",
        "LEIA-ME.txt",
        "MoviZap-Backup-de-Ligacoes.exe"
    };

    static int Main(string[] args)
    {
        string pasta = Path.Combine(Path.GetTempPath(),
            "MoviZapLigacoes-instalar-" + Guid.NewGuid().ToString("N").Substring(0, 8));
        Directory.CreateDirectory(pasta);
        var eu = Assembly.GetExecutingAssembly();

        foreach (string nome in Carga)
        {
            using (Stream dentro = eu.GetManifestResourceStream(nome))
            {
                if (dentro == null)
                {
                    Console.Error.WriteLine("Faltou " + nome + " dentro do instalador.");
                    return 3;
                }
                using (var fora = File.Create(Path.Combine(pasta, nome)))
                {
                    dentro.CopyTo(fora);
                }
            }
        }

        string ps1 = Path.Combine(pasta, "instalar.ps1");
        string extras = "";
        foreach (string a in args) { extras += " " + a; }

        var inicio = new ProcessStartInfo("powershell.exe",
            "-NoProfile -ExecutionPolicy Bypass -NoLogo -NoExit -File \"" + ps1 + "\"" + extras);
        inicio.UseShellExecute = false;
        inicio.WorkingDirectory = pasta;
        // O instalador em PowerShell apaga ESTE arquivo no fim, se tudo der
        // certo. Ele so sabe quem somos por esta variavel.
        inicio.EnvironmentVariables["MZL_INSTALADOR"] = eu.Location;
        Process.Start(inicio);

        // Rede de seguranca: a pasta temporaria sai sozinha mais tarde, caso o
        // instalador em PowerShell nao chegue ao fim. Quem termina bem ja
        // apaga os proprios arquivos antes disto.
        try
        {
            var limpeza = new ProcessStartInfo("cmd.exe",
                "/c ping -n 900 127.0.0.1 >nul & rmdir /s /q \"" + pasta + "\"");
            limpeza.WindowStyle = ProcessWindowStyle.Hidden;
            limpeza.CreateNoWindow = true;
            limpeza.UseShellExecute = false;
            Process.Start(limpeza);
        }
        catch { }

        return 0;
    }
}
