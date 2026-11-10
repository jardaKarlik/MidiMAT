using System.Diagnostics;

namespace MidiMAT.Services;

/// <summary>
/// Installs the bundled Python sidecar into <c>%LOCALAPPDATA%\MidiMAT\sidecar\</c> on
/// first run (or when the version changes), so a user machine never needs a repo
/// checkout. <see cref="SidecarManager"/> already resolves that path first, so once the
/// files land there the app is fully self-contained.
///
/// The payload travels next to the executable as <c>sidecar\</c> (see MidiMAT.csproj).
/// Extraction is a plain directory copy, skipped when the target is already current.
/// </summary>
public static class SidecarExtractor
{
    /// <summary>Bump when the bundled sidecar changes, to force a re-copy on upgrade.</summary>
    private const string BundleVersion = "1";

    private static string TargetDirectory =>
        Path.Combine(ConfigStore.AppDataDirectory, "sidecar");

    /// <summary>Absolute path to the installed sidecar executable.</summary>
    public static string InstalledExecutable =>
        Path.Combine(TargetDirectory, "midimat-server.exe");

    /// <summary>Where the bundle sits in the app payload (next to the exe / in the extract dir).</summary>
    private static string SourceDirectory =>
        Path.Combine(AppContext.BaseDirectory, "sidecar");

    public sealed record ExtractResult(bool Ok, bool Copied, string Detail);

    /// <summary>
    /// Ensure the sidecar is installed. Safe to call on every start: returns quickly
    /// when the installed copy is already at <see cref="BundleVersion"/>.
    /// </summary>
    public static ExtractResult EnsureInstalled()
    {
        var stampPath = Path.Combine(TargetDirectory, ".bundle-version");

        if (File.Exists(InstalledExecutable) && ReadStamp(stampPath) == BundleVersion)
        {
            return new ExtractResult(true, false, $"sidecar up to date ({TargetDirectory})");
        }

        if (!Directory.Exists(SourceDirectory))
        {
            // No bundle (a source-only run) — SidecarManager falls back to the dev path.
            return new ExtractResult(false, false,
                $"no bundled sidecar at {SourceDirectory} (dev run?)");
        }

        try
        {
            CopyDirectory(SourceDirectory, TargetDirectory);
            File.WriteAllText(stampPath, BundleVersion);
            MainWindow.LogToFile($"sidecar installed -> {TargetDirectory}");
            return new ExtractResult(true, true, $"installed to {TargetDirectory}");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            MainWindow.LogToFile($"sidecar install FAILED: {ex}");
            return new ExtractResult(false, false, $"install failed: {ex.Message}");
        }
    }

    private static string? ReadStamp(string path)
    {
        try
        {
            return File.Exists(path) ? File.ReadAllText(path).Trim() : null;
        }
        catch (IOException)
        {
            return null;
        }
    }

    private static void CopyDirectory(string source, string target)
    {
        Directory.CreateDirectory(target);

        foreach (var dir in Directory.GetDirectories(source, "*", SearchOption.AllDirectories))
        {
            Directory.CreateDirectory(Path.Combine(target, Path.GetRelativePath(source, dir)));
        }

        foreach (var file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            var dest = Path.Combine(target, Path.GetRelativePath(source, file));
            Directory.CreateDirectory(Path.GetDirectoryName(dest)!);

            // Overwrite only when the bytes differ, so a re-run is cheap.
            if (File.Exists(dest) && new FileInfo(dest).Length == new FileInfo(file).Length)
            {
                continue;
            }

            File.Copy(file, dest, overwrite: true);
        }
    }
}
