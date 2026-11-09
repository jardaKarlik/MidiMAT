using Microsoft.Win32;

namespace MidiMAT.Services;

/// <summary>Result of probing one dependency (DESIGN_APP.md §4).</summary>
public sealed record DependencyStatus(string Name, bool Found, string Detail);

/// <summary>
/// Detects external prerequisites using plain registry + filesystem probes (no WMI).
/// Each probe is deliberately conservative: it reports what it checked in <c>Detail</c>
/// so a "not found" is diagnosable rather than mysterious.
/// </summary>
public static class DependencyChecker
{
    public const string LoopMidi = "loopMIDI";
    public const string Traktor = "Traktor";
    public const string Obs = "OBS";
    public const string WebView2 = "WebView2";

    /// <summary>Run every dependency probe.</summary>
    public static IReadOnlyList<DependencyStatus> CheckAll() => new[]
    {
        CheckLoopMidi(),
        CheckTraktor(),
        CheckObs(),
        CheckWebView2(),
    };

    // ---------------------------------------------------------------------
    // loopMIDI — official installer registers under TOBIAS-ERICHSEN\loopMIDI.
    // NOTE: the exact value names below are the documented/commonly observed ones;
    // treat the key's existence as the primary signal and only surface values if present.
    // ---------------------------------------------------------------------
    private static DependencyStatus CheckLoopMidi()
    {
        foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
        {
            if (TryReadKey(hive, @"SOFTWARE\TOBIAS-ERICHSEN\loopMIDI", out var values))
            {
                var install = values.TryGetValue("InstallDir", out var dir)
                    ? dir?.ToString()
                    : null;
                var detail = string.IsNullOrEmpty(install)
                    ? $"registry key present ({hive})"
                    : $"installed at {install}";
                return new DependencyStatus(LoopMidi, true, detail);
            }
        }

        return new DependencyStatus(LoopMidi, false,
            @"not found (looked for HKLM/HKCU\SOFTWARE\TOBIAS-ERICHSEN\loopMIDI)");
    }

    // ---------------------------------------------------------------------
    // Traktor — look for "Traktor Settings.tsi" under Documents\Native Instruments\Traktor*.
    // DESIGN_APP.md §4 says "Documents"; on many machines Documents is OneDrive-backed,
    // which is why we probe the known-folder path too.
    // ---------------------------------------------------------------------
    private static DependencyStatus CheckTraktor()
    {
        var candidates = new List<string>();

        var myDocs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        if (!string.IsNullOrEmpty(myDocs))
        {
            candidates.Add(myDocs);
        }

        var profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        if (!string.IsNullOrEmpty(profile))
        {
            candidates.Add(Path.Combine(profile, "Documents"));
            candidates.Add(Path.Combine(profile, "OneDrive", "Documents"));
        }

        foreach (var docs in candidates.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            var ni = Path.Combine(docs, "Native Instruments");
            if (!Directory.Exists(ni))
            {
                continue;
            }

            // Match "Traktor <version>" folders containing the settings file.
            foreach (var traktorDir in Directory.EnumerateDirectories(ni, "Traktor*"))
            {
                var tsi = Path.Combine(traktorDir, "Traktor Settings.tsi");
                if (File.Exists(tsi))
                {
                    return new DependencyStatus(Traktor, true, tsi);
                }
            }
        }

        return new DependencyStatus(Traktor, false,
            @"not found (no " + @"\Native Instruments\Traktor*\Traktor Settings.tsi)");
    }

    // ---------------------------------------------------------------------
    // OBS — registry key (HKLM\SOFTWARE\OBS Studio) confirmed by common install paths.
    // ---------------------------------------------------------------------
    private static DependencyStatus CheckObs()
    {
        if (TryReadKey(RegistryHive.LocalMachine, @"SOFTWARE\OBS Studio", out var values))
        {
            var version = values.TryGetValue("Version", out var v) ? v?.ToString() : null;
            var detail = string.IsNullOrEmpty(version)
                ? "registry key present (HKLM\\SOFTWARE\\OBS Studio)"
                : $"registry key present, version {version}";
            return new DependencyStatus(Obs, true, detail);
        }

        foreach (var exe in CommonObsPaths())
        {
            if (File.Exists(exe))
            {
                return new DependencyStatus(Obs, true, exe);
            }
        }

        return new DependencyStatus(Obs, false,
            @"not found (registry HKLM\SOFTWARE\OBS Studio + common install paths)");
    }

    private static IEnumerable<string> CommonObsPaths()
    {
        var roots = new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
        };

        foreach (var root in roots)
        {
            if (!string.IsNullOrEmpty(root))
            {
                yield return Path.Combine(root, "obs-studio", "bin", "64bit", "obs64.exe");
                yield return Path.Combine(root, "obs-studio", "bin", "32bit", "obs32.exe");
            }
        }
    }

    // ---------------------------------------------------------------------
    // WebView2 Evergreen Runtime — registered under EdgeUpdate\Clients keyed by the
    // well-known WebView2 product GUID. Probe both machine (32/64) and per-user hives.
    // ---------------------------------------------------------------------
    private const string WebView2RuntimeGuid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";

    private static DependencyStatus CheckWebView2()
    {
        var subKey = $@"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WebView2RuntimeGuid}";

        foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
        {
            if (TryReadKey(hive, subKey, out var values))
            {
                var version = values.TryGetValue("pv", out var pv) ? pv?.ToString() : null;
                var detail = string.IsNullOrEmpty(version)
                    ? "Evergreen runtime present (no version value)"
                    : $"Evergreen runtime {version}";
                return new DependencyStatus(WebView2, true, detail);
            }
        }

        return new DependencyStatus(WebView2, false,
            "WebView2 Evergreen runtime not found (EdgeUpdate\\Clients probe)");
    }

    // ---------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------

    /// <summary>
    /// Open a registry key from a hive, trying both the 64-bit and 32-bit views
    /// (loopMIDI / OBS ship 64-bit but a 32-bit WOW node is also possible).
    /// Returns false when neither view contains the key.
    /// </summary>
    private static bool TryReadKey(RegistryHive hive, string subKey, out Dictionary<string, object?> values)
    {
        values = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);

        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(hive, view);
                using var key = baseKey.OpenSubKey(subKey, writable: false);
                if (key is null)
                {
                    continue;
                }

                foreach (var name in key.GetValueNames())
                {
                    values[name] = key.GetValue(name);
                }

                return true;
            }
            catch (Exception ex) when (ex is System.Security.SecurityException or UnauthorizedAccessException or IOException)
            {
                // Cannot read this hive/view — try the next one.
            }
        }

        return false;
    }
}
