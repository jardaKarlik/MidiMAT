namespace MidiMAT.Services;

/// <summary>
/// The six first-run wizard steps (DESIGN_APP.md §4). The integer values are the wire values
/// the React UI sends in <c>setup:start</c>.
/// </summary>
public enum SetupStep
{
    LoopMidi = 1,
    Traktor = 2,
    Runtime = 3,
    Server = 4,
    Obs = 5,
    Save = 6,
}

/// <summary>Result of running one wizard step.</summary>
/// <param name="Status">One of <c>done</c>, <c>error</c>, <c>pending</c> (UI vocab).</param>
/// <param name="Detail">Human-readable detail for the wizard card.</param>
/// <param name="Ok">True when the step succeeded.</param>
public sealed record StepResult(string Status, string Detail, bool Ok);

/// <summary>A progress update for one wizard step.</summary>
/// <param name="Step">1-based step number.</param>
/// <param name="Status">One of <c>pending|running|done|error</c>.</param>
/// <param name="Detail">Detail line for the UI.</param>
public sealed record SetupProgress(int Step, string Status, string Detail);

/// <summary>
/// Orchestrates the setup wizard one step at a time and raises <see cref="ProgressChanged"/>
/// with the same <c>{ step, status, detail }</c> shape the UI expects on <c>setup:progress</c>.
///
/// Each step runs the real check/action against the machine (registry, filesystem, the
/// surgical Traktor writer, the sidecar supervisor). Steps that would mutate the user's
/// machine (loopMIDI port registry, Traktor settings file) do so only through the honest
/// services, which back up / guard / refuse as documented.
/// </summary>
public sealed class SetupService
{
    private readonly MidiMatConfig _config;
    private readonly SidecarManager _sidecar;

    public SetupService(MidiMatConfig config, SidecarManager sidecar)
    {
        _config = config;
        _sidecar = sidecar;
    }

    /// <summary>Raised as a step moves through running -> done/error.</summary>
    public event EventHandler<SetupProgress>? ProgressChanged;

    /// <summary>Run one wizard step, raising progress for <c>running</c> then the final status.</summary>
    public async Task<StepResult> RunAsync(SetupStep step, CancellationToken ct = default)
    {
        Raise(step, "running", Describe(step));

        StepResult result;
        try
        {
            result = step switch
            {
                SetupStep.LoopMidi => await RunLoopMidiAsync(ct).ConfigureAwait(false),
                SetupStep.Traktor => RunTraktor(),
                SetupStep.Runtime => RunRuntime(),
                SetupStep.Server => await RunServerAsync(ct).ConfigureAwait(false),
                SetupStep.Obs => RunObs(),
                SetupStep.Save => RunSave(),
                _ => new StepResult("error", $"unknown step: {step}", false),
            };
        }
        catch (OperationCanceledException)
        {
            result = new StepResult("pending", "cancelled", false);
        }
        catch (Exception ex)
        {
            result = new StepResult("error", ex.Message, false);
        }

        Raise(step, result.Status, result.Detail);
        return result;
    }

    private static string Describe(SetupStep step) => step switch
    {
        SetupStep.LoopMidi => "Checking loopMIDI…",
        SetupStep.Traktor => "Checking Traktor settings…",
        SetupStep.Runtime => "Checking the runtime…",
        SetupStep.Server => "Starting the server…",
        SetupStep.Obs => "Checking for OBS…",
        SetupStep.Save => "Saving configuration…",
        _ => "Working…",
    };

    // ------------------------------------------------------------------
    // Step 1 — loopMIDI
    // ------------------------------------------------------------------
    private async Task<StepResult> RunLoopMidiAsync(CancellationToken ct)
    {
        var port = LoopMidiPortName();

        if (!LoopMidiInstaller.IsInstalled())
        {
            // Artifact-gated: InstallAsync returns a clear "not-implemented" result until the
            // download URL + SHA-256 are pinned. We surface that honestly.
            var install = await LoopMidiInstaller.InstallAsync(progress: null, ct).ConfigureAwait(false);
            if (!install.Ok)
            {
                return new StepResult(install.Status == "cancelled" ? "pending" : "error", install.Detail, false);
            }
        }

        if (LoopMidiInstaller.IsPortLive(port))
        {
            return new StepResult("done", $"loopMIDI installed; port '{port}' is live", true);
        }

        var ensure = LoopMidiInstaller.EnsurePort(port);
        return new StepResult(ensure.Ok ? "done" : "error", ensure.Detail, ensure.Ok);
    }

    // ------------------------------------------------------------------
    // Step 2 — Traktor (surgical out-port write)
    // ------------------------------------------------------------------
    private StepResult RunTraktor()
    {
        var tsi = TraktorConfig.FindSettingsFile() ?? _config.Paths.TraktorTsi;
        if (string.IsNullOrEmpty(tsi) || !File.Exists(tsi))
        {
            return new StepResult("error",
                "Traktor Settings.tsi not found — open Traktor once, or import the mapping manually.", false);
        }

        if (TraktorConfig.IsTraktorRunning())
        {
            return new StepResult("error",
                "Traktor is running — close it, then re-run this step (Traktor rewrites the file on exit).", false);
        }

        _config.Paths.TraktorTsi = tsi;

        var result = TraktorConfig.SetOutPort(tsi, LoopMidiPortName());
        return new StepResult(result.Ok ? "done" : "error", result.Detail, result.Ok);
    }

    // ------------------------------------------------------------------
    // Step 3 — Runtime (embedded; nothing to install)
    // ------------------------------------------------------------------
    private static StepResult RunRuntime() => new(
        "done",
        "Python runtime is embedded in the bundled sidecar (~60 MB). No installation required.",
        true);

    // ------------------------------------------------------------------
    // Step 4 — Server (start the sidecar)
    // ------------------------------------------------------------------
    private async Task<StepResult> RunServerAsync(CancellationToken ct)
    {
        _sidecar.Start();

        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(8);
        while (DateTime.UtcNow < deadline)
        {
            switch (_sidecar.State)
            {
                case SidecarState.Running:
                    return new StepResult("done", "server running", true);
                case SidecarState.Failed:
                    return new StepResult("error", "server failed to start — see the server log", false);
            }

            try
            {
                await Task.Delay(250, ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }

        var running = _sidecar.State == SidecarState.Running;
        return new StepResult(running ? "done" : "error", $"server state: {_sidecar.State}", running);
    }

    // ------------------------------------------------------------------
    // Step 5 — OBS
    // ------------------------------------------------------------------
    private static StepResult RunObs()
    {
        var detection = ObsDetector.Detect();

        if (detection.ObsStudioFound)
        {
            var version = string.IsNullOrEmpty(detection.ObsStudioVersion) ? "" : $" (v{detection.ObsStudioVersion})";
            return new StepResult("done", $"OBS Studio detected{version}", true);
        }

        if (detection.StreamlabsFound)
        {
            return new StepResult("done", "Streamlabs Desktop detected", true);
        }

        return new StepResult("error",
            "OBS/Streamlabs not detected — install one, then re-check it.", false);
    }

    // ------------------------------------------------------------------
    // Step 6 — Save
    // ------------------------------------------------------------------
    private StepResult RunSave()
    {
        _config.Paths.LoopmidiPort = LoopMidiPortName();
        _config.Paths.TraktorTsi = TraktorConfig.FindSettingsFile() ?? _config.Paths.TraktorTsi;

        var detection = ObsDetector.Detect();
        _config.Paths.ObsExe = detection.ObsStudioPath ?? detection.StreamlabsPath ?? _config.Paths.ObsExe;

        _config.SetupCompleted = DateTimeOffset.UtcNow.ToString("o");
        ConfigStore.Save(_config);

        return new StepResult("done", $"saved configuration to {ConfigStore.ConfigFilePath}", true);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------
    private string LoopMidiPortName()
        => string.IsNullOrWhiteSpace(_config.Paths.LoopmidiPort) ? "MidiMAT" : _config.Paths.LoopmidiPort;

    private void Raise(SetupStep step, string status, string detail)
        => ProgressChanged?.Invoke(this, new SetupProgress((int)step, status, detail));
}
