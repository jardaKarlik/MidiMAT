namespace MidiMAT.Services;

/// <summary>
/// STUB — full Traktor TSI handling (locate + surgical out-mapping injection) is a later
/// task. This type currently only LOCATES the user's "Traktor Settings.tsi".
///
/// IMPORTANT (DESIGN_APP.md §5.1): injection must be surgical. Never overwrite the whole
/// settings file; never re-serialize the XML with ElementTree (it rewrites
/// &lt;Entry&gt;&lt;/Entry&gt; to &lt;Entry /&gt;). The proven approach is a targeted regex
/// replace of the DeviceIO.Config base64 blob only, after a timestamped backup, and only
/// while Traktor is not running.
/// </summary>
public static class TraktorConfig
{
    public const string SettingsFileName = "Traktor Settings.tsi";

    /// <summary>
    /// Locate "Traktor Settings.tsi" under Documents\Native Instruments\Traktor*.
    /// Returns null when Traktor's settings are not found. (Mirrors the probe used by
    /// <see cref="DependencyChecker"/> so both report the same path.)
    /// </summary>
    public static string? FindSettingsFile()
    {
        var status = DependencyChecker.CheckAll()
            .FirstOrDefault(d => d.Name == DependencyChecker.Traktor);

        return status is { Found: true } ? status.Detail : null;
    }

    /// <summary>
    /// STUB. Injects MidiMAT's out-mappings into the existing "Generic MIDI" device in
    /// the TSI, per the algorithm in DESIGN_APP.md §5.1.
    /// </summary>
    public static Task InjectMappingsAsync(string tsiPath, CancellationToken ct = default)
        => throw new NotImplementedException(
            "TraktorConfig.InjectMappingsAsync is a stub (DESIGN_APP.md §5.1). " +
            "Implement: backup -> parse base64 DeviceIO.Config -> append MidiMAT CMAs/DCBMs " +
            "-> surgical regex replace of the Value=\"...\" attribute only.");
}
