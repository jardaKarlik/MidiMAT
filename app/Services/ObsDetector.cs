namespace MidiMAT.Services;

/// <summary>
/// STUB — OBS automation is a later task. This type only LOCATES the OBS installation
/// (registry + common install paths), reusing the same probe as
/// <see cref="DependencyChecker"/>.
/// </summary>
public static class ObsDetector
{
    /// <summary>Overlay URL the user pastes into an OBS "Browser" source (DESIGN_APP.md §4, step 5).</summary>
    public const string OverlayBrowserSourceUrl = "http://127.0.0.1:8080/overlay/index.html";

    /// <summary>Detected path to obs64.exe, or null when OBS is not installed.</summary>
    public static string? DetectExecutable()
    {
        var status = DependencyChecker.CheckAll()
            .FirstOrDefault(d => d.Name == DependencyChecker.Obs);

        return status is { Found: true } && status.Detail.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)
            ? status.Detail
            : null;
    }

    /// <summary>
    /// STUB. Future: generate/validate an OBS Browser Source config pointing at
    /// <see cref="OverlayBrowserSourceUrl"/>. OBS scene-collection JSON automation is not
    /// implemented; v1 only shows the URL + visual guide for the user to paste manually.
    /// </summary>
    public static Task ConfigureBrowserSourceAsync(CancellationToken ct = default)
        => throw new NotImplementedException(
            "ObsDetector.ConfigureBrowserSourceAsync is a stub. v1 shows the overlay URL for " +
            "manual OBS setup; programmatic scene-collection edits are out of scope.");
}
