using System.Security.Cryptography;
using System.Text;

namespace MidiMAT.Services;

/// <summary>
/// Installs the bundled Python sidecar into <c>%LOCALAPPDATA%\MidiMAT\sidecar\</c> on
/// first run (or when the bundle changes), so a user machine never needs a repo
/// checkout. <see cref="SidecarManager"/> already resolves that path first, so once the
/// files land there the app is fully self-contained.
///
/// The payload travels next to the executable as <c>sidecar\</c> (see MidiMAT.csproj).
/// Extraction is a plain directory copy, skipped when the target is already current.
/// </summary>
public static class SidecarExtractor
{
    /// <summary>
    /// Fingerprint of the bundled sidecar, written next to the installed copy.
    ///
    /// This used to be a hand-bumped constant ("1"), which meant an upgraded app
    /// kept running the sidecar from the previous release — the user got new UI
    /// with an old backend and no clue why. It is now derived from the bundle's
    /// content, so any change to the payload forces a re-copy automatically.
    /// </summary>
    private const string StampFileName = ".bundle-version";

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
    /// when the installed copy already matches the bundled one.
    /// </summary>
    public static ExtractResult EnsureInstalled()
    {
        var stampPath = Path.Combine(TargetDirectory, StampFileName);

        if (!Directory.Exists(SourceDirectory))
        {
            // No bundle (a source-only run) — SidecarManager falls back to the dev path.
            return new ExtractResult(false, false,
                $"no bundled sidecar at {SourceDirectory} (dev run?)");
        }

        var fingerprint = ComputeFingerprint(SourceDirectory);

        if (File.Exists(InstalledExecutable) && ReadStamp(stampPath) == fingerprint)
        {
            return new ExtractResult(true, false, $"sidecar up to date ({TargetDirectory})");
        }

        try
        {
            CopyDirectory(SourceDirectory, TargetDirectory);
            File.WriteAllText(stampPath, fingerprint);
            MainWindow.LogToFile($"sidecar installed -> {TargetDirectory} (bundle {fingerprint})");
            return new ExtractResult(true, true, $"installed to {TargetDirectory}");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            MainWindow.LogToFile($"sidecar install FAILED: {ex}");
            return new ExtractResult(false, false, $"install failed: {ex.Message}");
        }
    }

    /// <summary>
    /// Content fingerprint of the bundle: every file's relative path, size and
    /// last-write tick, hashed. Cheap (no file reads) but changes whenever the
    /// bundle is rebuilt, which is exactly when a re-copy is needed.
    /// </summary>
    private static string ComputeFingerprint(string directory)
    {
        var builder = new StringBuilder();

        foreach (var file in Directory.GetFiles(directory, "*", SearchOption.AllDirectories)
                     .OrderBy(f => f, StringComparer.Ordinal))
        {
            var info = new FileInfo(file);
            builder.Append(Path.GetRelativePath(directory, file))
                   .Append('|')
                   .Append(info.Length)
                   .Append('|')
                   .Append(info.LastWriteTimeUtc.Ticks)
                   .Append('\n');
        }

        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(builder.ToString()));
        return Convert.ToHexString(bytes)[..16];
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

            // Overwrite only when the file actually differs, so a re-run is cheap.
            // Compare size AND write time — a rebuild can produce a same-size file
            // with different bytes, and size alone would skip it.
            if (File.Exists(dest))
            {
                var existing = new FileInfo(dest);
                var incoming = new FileInfo(file);
                if (existing.Length == incoming.Length &&
                    existing.LastWriteTimeUtc == incoming.LastWriteTimeUtc)
                {
                    continue;
                }
            }

            File.Copy(file, dest, overwrite: true);
        }
    }
}
