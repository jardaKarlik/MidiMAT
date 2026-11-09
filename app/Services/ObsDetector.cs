using Microsoft.Win32;

namespace MidiMAT.Services;

/// <summary>What the OBS/Streamlabs probe found.</summary>
public sealed record ObsDetection(
    bool ObsStudioFound,
    string? ObsStudioPath,
    string? ObsStudioVersion,
    bool StreamlabsFound,
    string? StreamlabsPath,
    string? StreamlabsVersion)
{
    /// <summary>True when either OBS Studio or Streamlabs Desktop is present.</summary>
    public bool AnyFound => ObsStudioFound || StreamlabsFound;
}

/// <summary>
/// The Browser Source settings the wizard shows the user. OBS scene-collection JSON is not
/// automated in v1 — the user pastes the URL and ticks the two boxes manually.
/// </summary>
/// <param name="Url">Overlay URL to paste into the OBS "Browser" source.</param>
/// <param name="Width">Recommended source width.</param>
/// <param name="Height">Recommended source height.</param>
/// <param name="RefreshBrowserWhenSceneBecomesActive">Checkbox should be ON.</param>
/// <param name="ShutdownSourceWhenNotVisible">Checkbox should be OFF.</param>
public sealed record BrowserSourceGuide(
    string Url,
    int Width,
    int Height,
    bool RefreshBrowserWhenSceneBecomesActive,
    bool ShutdownSourceWhenNotVisible);

/// <summary>
/// Locates OBS Studio and Streamlabs Desktop (registry + common install paths) and describes
/// the Browser Source the user should create. Streamlabs Desktop is a supported OBS fork —
/// the same URL/checkboxes apply.
/// </summary>
public static class ObsDetector
{
    /// <summary>Overlay URL the user pastes into an OBS "Browser" source (DESIGN_APP.md §4, step 5).</summary>
    public const string OverlayBrowserSourceUrl = "http://127.0.0.1:8080/overlay/index.html";

    /// <summary>Recommended OBS Browser Source size.</summary>
    public const int RecommendedWidth = 1920;
    public const int RecommendedHeight = 1080;

    /// <summary>Exact OBS checkbox labels, so the UI can render them verbatim.</summary>
    public const string RefreshSettingLabel = "Refresh browser when scene becomes active";
    public const string ShutdownSettingLabel = "Shutdown source when not visible";

    /// <summary>Probe for OBS Studio and Streamlabs Desktop.</summary>
    public static ObsDetection Detect()
    {
        var obs = DetectObsStudio();
        var streamlabs = DetectStreamlabs();
        return new ObsDetection(obs.Found, obs.Path, obs.Version, streamlabs.Found, streamlabs.Path, streamlabs.Version);
    }

    /// <summary>
    /// Legacy convenience: the OBS executable path, or null. Prefer <see cref="Detect"/> which
    /// also reports Streamlabs and the version.
    /// </summary>
    public static string? DetectExecutable()
    {
        var detection = Detect();
        return detection.ObsStudioPath ?? detection.StreamlabsPath;
    }

    /// <summary>The Browser Source the user should add (URL + recommended size + checkbox states).</summary>
    public static BrowserSourceGuide BrowserSourceGuide() => new(
        OverlayBrowserSourceUrl,
        RecommendedWidth,
        RecommendedHeight,
        RefreshBrowserWhenSceneBecomesActive: true,
        ShutdownSourceWhenNotVisible: false);

    // ------------------------------------------------------------------
    // OBS Studio — HKLM\SOFTWARE\OBS Studio (Version), confirmed by common paths.
    // ------------------------------------------------------------------
    private static (bool Found, string? Path, string? Version) DetectObsStudio()
    {
        string? version = null;
        foreach (var subKey in new[] { @"SOFTWARE\OBS Studio", @"SOFTWARE\WOW6432Node\OBS Studio" })
        {
            if (TryReadKey(RegistryHive.LocalMachine, subKey, out var values))
            {
                version = values.TryGetValue("Version", out var v) ? v?.ToString() : null;
                break;
            }
        }

        foreach (var exe in CommonObsPaths())
        {
            if (File.Exists(exe))
            {
                return (true, exe, version);
            }
        }

        return (version is not null, null, version);
    }

    private static IEnumerable<string> CommonObsPaths()
    {
        foreach (var root in ProgramRoots())
        {
            yield return Path.Combine(root, "obs-studio", "bin", "64bit", "obs64.exe");
            yield return Path.Combine(root, "obs-studio", "bin", "32bit", "obs32.exe");
        }
    }

    // ------------------------------------------------------------------
    // Streamlabs Desktop — Uninstall DisplayName contains "Streamlabs", confirmed by paths.
    // ------------------------------------------------------------------
    private static (bool Found, string? Path, string? Version) DetectStreamlabs()
    {
        var version = FindUninstallVersion("Streamlabs");

        foreach (var exe in CommonStreamlabsPaths())
        {
            if (File.Exists(exe))
            {
                return (true, exe, version);
            }
        }

        return (version is not null, null, version);
    }

    private static IEnumerable<string> CommonStreamlabsPaths()
    {
        foreach (var root in ProgramRoots())
        {
            yield return Path.Combine(root, "Streamlabs OBS", "Streamlabs OBS.exe");
            yield return Path.Combine(root, "StreamlabsDesktop", "Streamlabs Desktop.exe");
        }

        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrEmpty(localAppData))
        {
            yield return Path.Combine(localAppData, "Programs", "Streamlabs OBS", "Streamlabs OBS.exe");
            yield return Path.Combine(localAppData, "Programs", "StreamlabsDesktop", "Streamlabs Desktop.exe");
            yield return Path.Combine(localAppData, "StreamlabsDesktop", "Streamlabs Desktop.exe");
        }
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private static IEnumerable<string> ProgramRoots()
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
                yield return root;
            }
        }
    }

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
                // Unreadable view — try the next.
            }
        }

        return false;
    }

    private static string? FindUninstallVersion(string displayNameContains)
    {
        var roots = new[]
        {
            (RegistryHive.LocalMachine, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (RegistryHive.LocalMachine, @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (RegistryHive.CurrentUser, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        };

        foreach (var (hive, root) in roots)
        {
            foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
            {
                try
                {
                    using var baseKey = RegistryKey.OpenBaseKey(hive, view);
                    using var key = baseKey.OpenSubKey(root);
                    if (key is null)
                    {
                        continue;
                    }

                    foreach (var sub in key.GetSubKeyNames())
                    {
                        using var app = key.OpenSubKey(sub);
                        var name = app?.GetValue("DisplayName") as string;
                        if (name is not null && name.Contains(displayNameContains, StringComparison.OrdinalIgnoreCase))
                        {
                            return app!.GetValue("DisplayVersion") as string;
                        }
                    }
                }
                catch (Exception ex) when (ex is System.Security.SecurityException or UnauthorizedAccessException or IOException)
                {
                    // Unreadable view — try the next.
                }
            }
        }

        return null;
    }
}
