namespace MidiMAT.Services;

/// <summary>
/// STUB — real loopMIDI download/verify/silent-install is a later task.
///
/// The shell deliberately NEVER elevates (app.manifest: asInvoker). loopMIDI's official
/// installer needs Administrator, so it must be launched by a separate elevated helper.
/// The intended flow (DESIGN_APP.md §4, step 1) is documented here so the real
/// implementation has an unambiguous contract:
///
///   1. Download the official installer from loopmidi.se into
///      %LOCALAPPDATA%\MidiMAT\downloads\loopmidi-setup.exe.
///      Do NOT redistribute it inside our EXE (EULA-clean).
///   2. Verify the download's SHA-256 against a hard-coded, version-pinned hash.
///   3. Launch the installer ELEVATED (runas verb) with:
///          /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
///   4. Wait for the installer process to exit; confirm the registry key
///      HKLM\SOFTWARE\TOBIAS-ERICHSEN\loopMIDI now exists.
///   5. Create the virtual port named by config (default "MidiMAT") — loopMIDI has no
///      documented silent port-creation switch, so this likely requires driving its UI or
///      writing its settings; verify the exact mechanism before implementing.
///   6. Poll the running sidecar / MIDI API until the new port is visible.
///
/// Nothing here talks to the network or spawns processes yet.
/// </summary>
public static class LoopMidiInstaller
{
    /// <summary>Where the downloaded installer would be cached.</summary>
    public static string InstallerCachePath { get; } = Path.Combine(
        ConfigStore.AppDataDirectory, "downloads", "loopmidi-setup.exe");

    /// <summary>The silent-install arguments loopMIDI's Inno Setup installer accepts.</summary>
    public static IReadOnlyList<string> SilentInstallArguments { get; } =
        new[] { "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" };

    /// <summary>Expected installer size shown in the wizard (DESIGN_APP.md §4).</summary>
    public const long ExpectedDownloadBytes = 2L * 1024 * 1024; // ~2 MB

    /// <summary>
    /// STUB. Downloads + verifies + silently installs loopMIDI via an elevated helper.
    /// </summary>
    public static Task InstallAsync(IProgress<string>? progress = null, CancellationToken ct = default)
        => throw new NotImplementedException(
            "LoopMidiInstaller.InstallAsync is a stub. See the class summary for the " +
            "download -> SHA-256 verify -> elevated /VERYSILENT flow (DESIGN_APP.md §4).");
}
