// MoviZap - Backup de Ligacoes | o lancador que a tarefa executa (v0.6, 19/10/2026)
//
// Por que ele existe: a tarefa chamava powershell.exe, e o Gerenciador de
// Tarefas mostrava "Windows PowerShell". Era isso que as pessoas encerravam.
// Com este executavel no meio, a lista de processos mostra
// "MoviZap - Backup de Ligacoes", com empresa e descricao -- e ninguem
// encerra por engano o que esta identificado.
//
// Ele NAO tem segredo nenhum dentro: so acha o agente em %LOCALAPPDATA% e o
// executa. Decompila-lo nao entrega nada.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

[assembly: AssemblyTitle("MoviZap - Backup de Ligacoes")]
[assembly: AssemblyProduct("MoviZap - Backup de Ligacoes")]
[assembly: AssemblyCompany("Movisat")]
[assembly: AssemblyDescription("Backup do historico de ligacoes do MicroSIP no MoviZap.")]
[assembly: AssemblyCopyright("Movisat")]
[assembly: AssemblyVersion("0.7.0.0")]
[assembly: AssemblyFileVersion("0.7.0.0")]

static class Lancador
{
    static int Main(string[] args)
    {
        string dados = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "MoviZapLigacoes");
        string agente = Path.Combine(dados, "movizap-ligacoes.ps1");
        if (!File.Exists(agente))
        {
            // Sem janela: quem ve isto e o log da tarefa, nao a pessoa.
            Console.Error.WriteLine("Agente nao encontrado: " + agente);
            return 2;
        }

        string modo = (args.Length > 0 && args[0].StartsWith("-")) ? args[0] : "-Enviar";
        bool simular = modo.Equals("-Simular", StringComparison.OrdinalIgnoreCase);

        // -Simular e para a pessoa ler: janela visivel e que nao fecha sozinha.
        // -Enviar e a tarefa: nada aparece na tela.
        string argumentos = "-NoProfile -ExecutionPolicy Bypass "
            + (simular ? "-NoExit " : "")
            + "-File \"" + agente + "\" " + modo;

        var inicio = new ProcessStartInfo("powershell.exe", argumentos);
        inicio.UseShellExecute = false;
        inicio.CreateNoWindow = !simular;
        inicio.WindowStyle = simular ? ProcessWindowStyle.Normal : ProcessWindowStyle.Hidden;
        inicio.WorkingDirectory = dados;

        using (var p = Process.Start(inicio))
        {
            if (simular) { return 0; }   // a janela fica com a pessoa
            p.WaitForExit();
            return p.ExitCode;
        }
    }
}
