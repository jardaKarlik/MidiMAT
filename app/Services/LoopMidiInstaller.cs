using System.Diagnostics;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Microsoft.Win32;

namespace MidiMAT.Services;

/// <summary>Outcome of <see cref="LoopMidiInstaller.EnsurePort"/>.</summary>
/// <param name="Ok">True when the port is defined AND live.</param>
/// <param name="AddedDefinition">True when a new DWORD port value was written to the registry.</param>
/// <param name="Restarted">True when loopMIDI.exe was restarted to pick up the change.</param>
/// <param name="Live">True when the port was visible in the real MIDI port list.</param>
/// <param name="Detail">Human-readable detail for the wizard.</param>
public sealed record LoopMidiPortResult(bool Ok, bool AddedDefinition, bool Restarted, bool Live, string Detail);

/// <summary>Outcome of <see cref="LoopMidiInstaller.InstallAsync"/>.</summary>
public sealed record LoopMidiInstallResult(bool Ok, string Status, string Detail);

/// <summary>
/// Detects and configures the loopMIDI virtual-MIDI driver.
///
/// <para>
/// loopMIDI records its virtual ports as <b>registry values</b> under
/// <c>HKCU\SOFTWARE\Tobias Erichsen\loopMIDI\Ports</c>, one DWORD named after the port.
/// Writing the value does <b>nothing</b> while loopMIDI is running — the process must be
/// restarted so it re-reads the registry and re-creates the ports. No admin rights are
/// needed (HKCU); the note "space, mixed case" in <c>Tobias Erichsen</c> is load-bearing.
/// </para>
///
/// <para>
/// The definitive liveness check is enumerating real MIDI ports via Win32 <c>winmm</c>,
/// not the registry.
/// </para>
/// </summary>
public static class LoopMidiInstaller
{
    // ------------------------------------------------------------------
    // UNPINNED ARTIFACTS — fill from an ACTUAL download before shipping.
    // ------------------------------------------------------------------
    // TODO: down-load once, record the SHA-256, and paste BOTH the exact URL and hash
    //       here. Until InstallerSha256 is non-empty, InstallAsync() refuses to run and
    //       returns a clear "not-implemented" result — it never pretends to install.
    //
    // Vendor page (re-confirm against this before each release):
    //   https://www.tobias-erichsen.de/software/loopmidi.html
    //
    // DESIGN_APP.md §4: do NOT redistribute the installer inside our EXE — download it
    // at setup time so the user gets the official, current build under their own EULA.
    // Pinned 2026-11-10 to the vendor's loopMIDI 1.0.16.27 build (the URL is versioned
    // and stable). The archive contains a single `loopMIDISetup.exe`.
    private const string InstallerUrl =
        "https://www.tobias-erichsen.de/wp-content/uploads/2020/01/loopMIDISetup_1_0_16_27.zip";

    /// <summary>SHA-256 of the pinned archive — verified before anything is executed.</summary>
    private const string InstallerSha256 =
        "975399eb76e2c5a1d553ecd8975ab361261ccab8fd9412b8060b19877cb4e0d5";
    // ------------------------------------------------------------------

    private const string TobiasKey = @"SOFTWARE\Tobias Erichsen";
    private const string LoopMidiKey = @"SOFTWARE\Tobias Erichsen\loopMIDI";
    private const string PortsSubKey = @"SOFTWARE\Tobias Erichsen\loopMIDI\Ports";

    /// <summary>Where the downloaded installer (or archive) is cached.</summary>
    public static string InstallerCachePath { get; } = Path.Combine(
        ConfigStore.AppDataDirectory, "downloads", "loopmidi-setup.exe");

    private static string InstallerCacheDirectory => Path.GetDirectoryName(InstallerCachePath)!;

    /// <summary>The silent-install arguments loopMIDI's Inno Setup installer accepts.</summary>
    public static IReadOnlyList<string> SilentInstallArguments { get; } =
        new[] { "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" };

    /// <summary>Nominal installer size (the pinned 1.0.16.27 archive is ~7.9 MB).</summary>
    public const long ExpectedDownloadBytes = 7884702L;

    /// <summary>How long <see cref="EnsurePort"/> waits for a restarted loopMIDI to publish the port.</summary>
    private static readonly TimeSpan PortPollTimeout = TimeSpan.FromSeconds(10);

    // ------------------------------------------------------------------
    // Detection
    // ------------------------------------------------------------------

    /// <summary>
    /// True when loopMIDI looks installed: either of its registry roots under
    /// <c>SOFTWARE\Tobias Erichsen</c> exists, or its Uninstall entry is present.
    /// </summary>
    public static bool IsInstalled()
    {
        foreach (var hive in new[] { RegistryHive.CurrentUser, RegistryHive.LocalMachine })
        {
            if (KeyExists(hive, LoopMidiKey) || KeyExists(hive, TobiasKey))
            {
                return true;
            }
        }

        return FindUninstallVersion() is not null;
    }

    /// <summary>Installed loopMIDI version (from the Uninstall entry), or null.</summary>
    public static string? InstalledVersion() => FindUninstallVersion();

    /// <summary>True when the <c>Ports</c> registry value for <paramref name="name"/> exists.</summary>
    public static bool HasPortDefinition(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return false;
        }

        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(PortsSubKey, writable: false);
            return key?.GetValue(name) is not null;
        }
        catch (Exception ex) when (ex is System.Security.SecurityException or UnauthorizedAccessException or IOException)
        {
            return false;
        }
    }

    /// <summary>
    /// The definitive liveness check: enumerate real MIDI output ports via Win32 <c>winmm</c>
    /// and match <paramref name="name"/> as a case-insensitive prefix.
    /// </summary>
    public static bool IsPortLive(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return false;
        }

        var count = MidiOutGetNumDevs();
        for (uint i = 0; i < count; i++)
        {
            var caps = new MIDIOUTCAPS { szPname = new char[MaxPNameLen] };
            if (MidiOutGetDevCaps(new UIntPtr(i), ref caps, (uint)Marshal.SizeOf<MIDIOUTCAPS>()) != 0)
            {
                continue;
            }

            var pname = new string(caps.szPname).TrimEnd('\0');
            if (pname.StartsWith(name, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    // ------------------------------------------------------------------
    // Configure
    // ------------------------------------------------------------------

    /// <summary>
    /// Ensure a virtual port named <paramref name="name"/> exists and is live: write the
    /// registry value if missing, restart loopMIDI.exe, then poll <see cref="IsPortLive"/>
    /// for up to ~10s. Returns what it actually did.
    /// </summary>
    public static LoopMidiPortResult EnsurePort(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return new LoopMidiPortResult(false, false, false, false, "port name is empty");
        }

        if (!IsInstalled())
        {
            return new LoopMidiPortResult(false, false, false, false,
                "loopMIDI is not installed — run the loopMIDI step first");
        }

        var added = false;
        if (!HasPortDefinition(name))
        {
            try
            {
                using var key = Registry.CurrentUser.CreateSubKey(PortsSubKey, writable: true);
                if (key is null)
                {
                    return new LoopMidiPortResult(false, false, false, false,
                        $@"could not open HKCU\{PortsSubKey}");
                }

                key.SetValue(name, 1, RegistryValueKind.DWord);
                added = true;
            }
            catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
            {
                return new LoopMidiPortResult(false, false, false, false,
                    $"could not write the port registry value: {ex.Message}");
            }
        }
        else if (IsPortLive(name))
        {
            // Already defined and already published — nothing to do.
            return new LoopMidiPortResult(true, false, false, true, $"port '{name}' is live");
        }

        // A registry change is only picked up when loopMIDI (re)reads it at startup.
        var restarted = RestartLoopMidi(out var restartDetail);

        var deadline = DateTime.UtcNow + PortPollTimeout;
        while (DateTime.UtcNow < deadline)
        {
            if (IsPortLive(name))
            {
                return new LoopMidiPortResult(true, added, restarted, true, $"port '{name}' is live");
            }

            Thread.Sleep(250);
        }

        return new LoopMidiPortResult(false, added, restarted, false,
            $"port '{name}' was {(added ? "added" : "already defined")} but did not appear within " +
            $"{PortPollTimeout.TotalSeconds:0}s ({restartDetail})");
    }

    private static bool RestartLoopMidi(out string detail)
    {
        var exe = FindLoopMidiExecutable();
        if (exe is null)
        {
            detail = "loopMIDI.exe not found";
            return false;
        }

        foreach (var process in Process.GetProcessesByName("loopMIDI"))
        {
            try
            {
                if (!process.HasExited)
                {
                    process.Kill();
                    process.WaitForExit(3000);
                }
            }
            catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
            {
                // Already gone, or we cannot kill it — carry on and try to start a fresh one.
            }
            finally
            {
                process.Dispose();
            }
        }

        try
        {
            Process.Start(new ProcessStartInfo { FileName = exe, UseShellExecute = true });
            detail = $"restarted {exe}";
            return true;
        }
        catch (Exception ex)
        {
            detail = $"failed to start loopMIDI: {ex.Message}";
            return false;
        }
    }

    /// <summary>loopMIDI.exe under Program Files (x86) or Program Files, or null.</summary>
    public static string? FindLoopMidiExecutable()
    {
        var roots = new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
        };

        foreach (var root in roots)
        {
            if (string.IsNullOrEmpty(root))
            {
                continue;
            }

            var exe = Path.Combine(root, "Tobias Erichsen", "loopMIDI", "loopMIDI.exe");
            if (File.Exists(exe))
            {
                return exe;
            }
        }

        return null;
    }

    // ------------------------------------------------------------------
    // Install (artifact-gated)
    // ------------------------------------------------------------------

    /// <summary>
    /// Download the vendor installer, verify its SHA-256, and run it elevated with
    /// <c>/VERYSILENT /SUPPRESSMSGBOXES /NORESTART</c>. Honest by construction: while the
    /// URL/hash constants are unfilled it returns a "not-implemented" result and does nothing.
    /// </summary>
    public static async Task<LoopMidiInstallResult> InstallAsync(
        IProgress<string>? progress = null,
        CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(InstallerUrl) || string.IsNullOrWhiteSpace(InstallerSha256))
        {
            return new LoopMidiInstallResult(false, "not-implemented",
                "loopMIDI installer URL/SHA-256 are not pinned yet. Fill " +
                "LoopMidiInstaller.InstallerUrl and InstallerSha256 from a verified download " +
                "(see the TODO) before silent install can run. Manual fallback: " +
                "https://www.tobias-erichsen.de/software/loopmidi.html");
        }

        Directory.CreateDirectory(InstallerCacheDirectory);

        byte[] bytes;
        try
        {
            progress?.Report("Downloading the loopMIDI installer…");
            using var http = new HttpClient { Timeout = TimeSpan.FromMinutes(5) };
            bytes = await http.GetByteArrayAsync(InstallerUrl, ct).ConfigureAwait(false);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new LoopMidiInstallResult(false, "error", $"download failed: {ex.Message}");
        }

        var actualHash = Convert.ToHexString(SHA256.HashData(bytes));
        if (!actualHash.Equals(InstallerSha256, StringComparison.OrdinalIgnoreCase))
        {
            return new LoopMidiInstallResult(false, "error",
                $"SHA-256 mismatch (got {actualHash}); refusing to run an unverified installer.");
        }

        await File.WriteAllBytesAsync(InstallerCachePath, bytes, ct).ConfigureAwait(false);

        string executable;
        var isZip = Path.GetExtension(new Uri(InstallerUrl).AbsolutePath)
            .Equals(".zip", StringComparison.OrdinalIgnoreCase);

        if (isZip)
        {
            var extractDir = Path.Combine(InstallerCacheDirectory, "extracted");
            try
            {
                if (Directory.Exists(extractDir))
                {
                    Directory.Delete(extractDir, recursive: true);
                }

                ZipFile.ExtractToDirectory(InstallerCachePath, extractDir);
                executable = Directory.EnumerateFiles(extractDir, "*.exe", SearchOption.AllDirectories)
                    .FirstOrDefault()
                    ?? string.Empty;
            }
            catch (Exception ex) when (ex is IOException or InvalidDataException or UnauthorizedAccessException)
            {
                return new LoopMidiInstallResult(false, "error", $"could not extract the installer archive: {ex.Message}");
            }

            if (string.IsNullOrEmpty(executable))
            {
                return new LoopMidiInstallResult(false, "error", "downloaded archive contained no .exe");
            }
        }
        else
        {
            executable = InstallerCachePath;
        }

        progress?.Report("Running the loopMIDI installer (Administrator permission required)…");

        try
        {
            // UseShellExecute + "runas" is what raises the UAC prompt. The app itself is
            // asInvoker and never elevates; the installer is a separate elevated process.
            var psi = new ProcessStartInfo
            {
                FileName = executable,
                UseShellExecute = true,
                Verb = "runas",
            };

            foreach (var argument in SilentInstallArguments)
            {
                psi.ArgumentList.Add(argument);
            }

            using var process = Process.Start(psi);
            if (process is not null)
            {
                await process.WaitForExitAsync(ct).ConfigureAwait(false);
            }
        }
        catch (System.ComponentModel.Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            // ERROR_CANCELLED — the user dismissed the UAC prompt. Not an error, but not a success.
            return new LoopMidiInstallResult(false, "cancelled",
                "Elevation was declined (UAC). loopMIDI was not installed.");
        }
        catch (Exception ex)
        {
            return new LoopMidiInstallResult(false, "error", $"the installer failed to run: {ex.Message}");
        }

        if (IsInstalled())
        {
            var version = InstalledVersion();
            return new LoopMidiInstallResult(true, "done",
                version is null ? "loopMIDI installed" : $"loopMIDI installed (v{version})");
        }

        return new LoopMidiInstallResult(false, "error",
            "The installer finished but loopMIDI was not detected in the registry.");
    }

    // ------------------------------------------------------------------
    // Registry helpers
    // ------------------------------------------------------------------

    private static bool KeyExists(RegistryHive hive, string subKey)
    {
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(hive, view);
                using var key = baseKey.OpenSubKey(subKey, writable: false);
                if (key is not null)
                {
                    return true;
                }
            }
            catch (Exception ex) when (ex is System.Security.SecurityException or UnauthorizedAccessException or IOException)
            {
                // Unreadable view — try the next.
            }
        }

        return false;
    }

    private static string? FindUninstallVersion()
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
                        if (app?.GetValue("DisplayName") as string == "loopMIDI")
                        {
                            return app.GetValue("DisplayVersion") as string;
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

    // ------------------------------------------------------------------
    // winmm P/Invoke
    // ------------------------------------------------------------------

    private const int MaxPNameLen = 32; // MAXPNAMELEN

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct MIDIOUTCAPS
    {
        public ushort wMid;
        public ushort wPid;
        public uint vDriverVersion; // MMVERSION == UINT

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = MaxPNameLen)]
        public char[] szPname;

        public ushort wTechnology;
        public ushort wVoices;
        public ushort wNotes;
        public ushort wChannelMask;
        public uint dwSupport;
    }

    [DllImport("winmm.dll", EntryPoint = "midiOutGetNumDevs")]
    private static extern uint MidiOutGetNumDevs();

    [DllImport("winmm.dll", EntryPoint = "midiOutGetDevCapsW", CharSet = CharSet.Unicode)]
    private static extern uint MidiOutGetDevCaps(UIntPtr uDeviceID, ref MIDIOUTCAPS caps, uint cbCaps);
}
