using System.Text.Json;
using System.Text.Json.Serialization;

namespace MidiMAT.Services;

/// <summary>
/// Strongly-typed model of <c>midimat.config.json</c> (DESIGN_APP.md §6).
/// JSON names are snake_case to match the spec exactly.
/// </summary>
public sealed class MidiMatConfig
{
    [JsonPropertyName("version")]
    public int Version { get; set; } = 2;

    [JsonPropertyName("setup_completed")]
    public string? SetupCompleted { get; set; }

    [JsonPropertyName("skip_checks")]
    public bool SkipChecks { get; set; }

    [JsonPropertyName("paths")]
    public ConfigPaths Paths { get; set; } = new();

    [JsonPropertyName("server")]
    public ServerConfig Server { get; set; } = new();

    [JsonPropertyName("overlay_url")]
    public string OverlayUrl { get; set; } = "http://127.0.0.1:8080/overlay/index.html";

    [JsonPropertyName("editor_url")]
    public string EditorUrl { get; set; } = "http://127.0.0.1:8080/overlay/edit.html";
}

public sealed class ConfigPaths
{
    [JsonPropertyName("loopmidi_port")]
    public string LoopmidiPort { get; set; } = "MidiMAT";

    [JsonPropertyName("traktor_tsi")]
    public string? TraktorTsi { get; set; }

    [JsonPropertyName("obs_exe")]
    public string? ObsExe { get; set; }
}

public sealed class ServerConfig
{
    [JsonPropertyName("http_port")]
    public int HttpPort { get; set; } = 8080;

    [JsonPropertyName("ws_port")]
    public int WsPort { get; set; } = 8787;

    [JsonPropertyName("auto_start")]
    public bool AutoStart { get; set; } = true;

    [JsonPropertyName("demo_mode")]
    public bool DemoMode { get; set; }

    [JsonPropertyName("nhl_mode")]
    public bool NhlMode { get; set; } = true;
}

/// <summary>
/// Reads/writes <c>%LOCALAPPDATA%\MidiMAT\config.json</c> with an atomic write
/// (temp file + replace) so a crash mid-write never truncates the config.
/// </summary>
public static class ConfigStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    /// <summary>%LOCALAPPDATA%\MidiMAT</summary>
    public static string AppDataDirectory { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MidiMAT");

    /// <summary>%LOCALAPPDATA%\MidiMAT\config.json</summary>
    public static string ConfigFilePath { get; } = Path.Combine(AppDataDirectory, "config.json");

    /// <summary>
    /// Load config from disk. Returns a default config if the file is missing or
    /// unreadable (a corrupt file is preserved as config.json.bad for diagnosis).
    /// </summary>
    public static MidiMatConfig Load()
    {
        try
        {
            if (!File.Exists(ConfigFilePath))
            {
                return new MidiMatConfig();
            }

            var json = File.ReadAllText(ConfigFilePath);
            return JsonSerializer.Deserialize<MidiMatConfig>(json, JsonOptions) ?? new MidiMatConfig();
        }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException)
        {
            TryPreserveCorruptConfig();
            return new MidiMatConfig();
        }
    }

    /// <summary>Atomically persist config to disk.</summary>
    public static void Save(MidiMatConfig config)
    {
        Directory.CreateDirectory(AppDataDirectory);

        var json = JsonSerializer.Serialize(config, JsonOptions);
        var tempPath = ConfigFilePath + ".tmp";

        File.WriteAllText(tempPath, json);

        if (File.Exists(ConfigFilePath))
        {
            // Atomic replace: readers only ever see the old or the new file.
            File.Replace(tempPath, ConfigFilePath, destinationBackupFileName: null);
        }
        else
        {
            File.Move(tempPath, ConfigFilePath);
        }
    }

    private static void TryPreserveCorruptConfig()
    {
        try
        {
            var bad = ConfigFilePath + ".bad";
            if (File.Exists(ConfigFilePath))
            {
                File.Copy(ConfigFilePath, bad, overwrite: true);
            }
        }
        catch
        {
            // Best-effort only; never throw while loading.
        }
    }
}
