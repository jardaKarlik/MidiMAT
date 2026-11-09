using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace MidiMAT.Services;

/// <summary>
/// A single MidiMAT out-mapping to inject into the Traktor "Generic MIDI" device.
/// </summary>
/// <param name="CmdId">Traktor command id (from the mapping catalogue).</param>
/// <param name="Target">Deck/slot/FX-unit target (0-15).</param>
/// <param name="Channel">1-based MIDI channel; used only to build <see cref="Key"/>.</param>
/// <param name="Cc">
/// MIDI control-change number. Traktor's catalogue only accepts <b>0..127</b>; anything
/// outside that range is silently dropped by Traktor (the row then shows "Mapped to: n/a").
/// </param>
public sealed record MappingSpec(int CmdId, int Target, int Channel, int Cc)
{
    /// <summary>Traktor MIDI key, e.g. <c>Ch01.CC.101</c>.</summary>
    public string Key => $"Ch{Channel:00}.CC.{Cc:000}";
}

/// <summary>Result of a surgical write to <c>Traktor Settings.tsi</c>.</summary>
/// <param name="Ok">True when the file was written (or was already in the desired state).</param>
/// <param name="Status">Short status id: <c>done</c> or <c>error</c>.</param>
/// <param name="Detail">Human-readable detail for the wizard.</param>
/// <param name="BackupPath">Timestamped backup created before writing, or null when nothing was written.</param>
public sealed record TraktorWriteResult(bool Ok, string Status, string Detail, string? BackupPath);

/// <summary>The (in, out) port pair stored in a device's <c>DDPT</c>.</summary>
public sealed record TraktorPorts(string InPort, string OutPort);

/// <summary>
/// Reads/writes the user's <c>Traktor Settings.tsi</c> without disturbing anything the user
/// did not ask to change.
///
/// <para>
/// The file is XML whose <c>DeviceIO.Config.*</c> entry holds a Base64 TLV tree:
/// <c>DIOM &gt; DEVS &gt; DEVI(name) &gt; DDAT &gt; { DDPT, DDDC, DDCB, ... }</c>. Each controller is
/// one <c>DEVI</c>. MidiMAT only ever touches the <c>Generic MIDI</c> device:
/// </para>
/// <list type="bullet">
///   <item><description><c>DDPT</c> carries the (in-port, out-port) pair as
///   <c>[u32 char-count][utf16be]</c>; NI-native devices store their serial there instead —
///   those are copied byte-for-byte.</description></item>
///   <item><description><c>DDCB</c> carries the mappings: <c>CMAS{ CMAI… }</c> plus
///   <c>DCBM{ (idx, key)… }</c>. <c>CMAI.midi_idx</c> resolves through <c>DCBM[stored idx]</c>
///   (stored-idx lookup, not array order).</description></item>
/// </list>
///
/// <para>
/// Writes are <b>surgical</b>: only the <c>Value="…"</c> attribute of the original text is
/// regex-replaced. The XML is never re-serialised (ElementTree/XDocument would rewrite
/// <c>&lt;Entry&gt;&lt;/Entry&gt;</c> to <c>&lt;Entry /&gt;</c> and reformat the whole file). A
/// timestamped backup is taken first, and every write refuses to run while Traktor is open
/// (Traktor rewrites the file on exit and would clobber our change).
/// </para>
/// </summary>
public static class TraktorConfig
{
    public const string SettingsFileName = "Traktor Settings.tsi";
    public const string DefaultDevice = "Generic MIDI";

    /// <summary>Upper bound (inclusive) of Traktor's MIDI CC catalogue.</summary>
    public const int MaxMidiCc = 127;

    // Out-mappings are uniform across the proven files (DESIGN_APP.md §5.1):
    // mapping_type = 1 (Output), CMAD ControlType = 0xFFFF, InteractionMode = 8.
    private const uint OutputMappingType = 1;
    private const uint OutputControlType = 0xFFFF;
    private const uint OutputInteractionMode = 8;

    // ------------------------------------------------------------------
    // Discovery
    // ------------------------------------------------------------------

    /// <summary>
    /// Newest <c>Traktor Settings.tsi</c> under
    /// <c>&lt;Documents | OneDrive\Documents&gt;\Native Instruments\Traktor*</c>.
    /// Returns null when Traktor's settings are not found.
    /// </summary>
    public static string? FindSettingsFile()
    {
        var roots = new List<string>();

        var myDocs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        if (!string.IsNullOrEmpty(myDocs))
        {
            roots.Add(Path.Combine(myDocs, "Native Instruments"));
        }

        var profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        if (!string.IsNullOrEmpty(profile))
        {
            roots.Add(Path.Combine(profile, "Documents", "Native Instruments"));
            roots.Add(Path.Combine(profile, "OneDrive", "Documents", "Native Instruments"));
        }

        string? best = null;
        var bestTime = DateTime.MinValue;

        foreach (var ni in roots.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!Directory.Exists(ni))
            {
                continue;
            }

            foreach (var traktorDir in EnumerateDirectoriesSafe(ni, "Traktor*"))
            {
                var tsi = Path.Combine(traktorDir, SettingsFileName);
                if (!File.Exists(tsi))
                {
                    continue;
                }

                var written = File.GetLastWriteTimeUtc(tsi);
                if (best is null || written > bestTime)
                {
                    best = tsi;
                    bestTime = written;
                }
            }
        }

        return best;
    }

    private static IEnumerable<string> EnumerateDirectoriesSafe(string path, string pattern)
    {
        try
        {
            return Directory.EnumerateDirectories(path, pattern);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException)
        {
            return Array.Empty<string>();
        }
    }

    /// <summary>True when a process whose name starts with "Traktor" is running.</summary>
    public static bool IsTraktorRunning()
    {
        foreach (var process in Process.GetProcesses())
        {
            try
            {
                if (process.ProcessName.StartsWith("Traktor", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            catch (InvalidOperationException)
            {
                // Process exited between enumeration and access.
            }
            finally
            {
                process.Dispose();
            }
        }

        return false;
    }

    // ------------------------------------------------------------------
    // Read
    // ------------------------------------------------------------------

    /// <summary>Read the (in, out) port pair stored in the named device's DDPT.</summary>
    public static TraktorPorts ReadPorts(string tsiPath, string device = DefaultDevice)
    {
        var binary = ExtractConfigBinary(ReadXmlText(tsiPath, out _));

        var found = FindDevice(binary, device)
            ?? throw new InvalidOperationException($"device '{device}' not found in {tsiPath}");
        var (devi, restOffset) = found;

        var ddat = FindChunk(TlvCodec.ParseTlv(devi, restOffset), "DDAT");
        var ddpt = FindChunkOrNull(TlvCodec.ParseTlv(ddat), "DDPT")
            ?? throw new InvalidOperationException($"device '{device}' has no DDPT");

        var ports = ReadPortStrings(ddpt);
        return new TraktorPorts(
            ports.Count > 0 ? ports[0] : string.Empty,
            ports.Count > 1 ? ports[1] : string.Empty);
    }

    // ------------------------------------------------------------------
    // Write: out-port
    // ------------------------------------------------------------------

    /// <summary>
    /// Set the named device's OUT-port (<c>DDPT</c> index 1), keeping the in-port unchanged.
    /// Backs up the file first and refuses to write while Traktor is running.
    /// </summary>
    public static TraktorWriteResult SetOutPort(string tsiPath, string portName, string device = DefaultDevice)
    {
        if (IsTraktorRunning())
        {
            return new TraktorWriteResult(false, "error",
                "Traktor is running — close it before MidiMAT writes the settings file " +
                "(Traktor rewrites it on exit).", null);
        }

        if (!File.Exists(tsiPath))
        {
            return new TraktorWriteResult(false, "error", $"Traktor settings not found: {tsiPath}", null);
        }

        var text = ReadXmlText(tsiPath, out var hasBom);

        byte[] binary;
        try
        {
            binary = ExtractConfigBinary(text);
        }
        catch (Exception ex) when (ex is FormatException or InvalidOperationException)
        {
            return new TraktorWriteResult(false, "error", $"could not decode DeviceIO.Config: {ex.Message}", null);
        }

        var found = FindDevice(binary, device);
        if (found is null)
        {
            return new TraktorWriteResult(false, "error", $"device '{device}' not found in {Path.GetFileName(tsiPath)}", null);
        }

        var (devi, restOffset) = found.Value;
        var ddat = FindChunk(TlvCodec.ParseTlv(devi, restOffset), "DDAT");
        var ddpt = FindChunkOrNull(TlvCodec.ParseTlv(ddat), "DDPT");
        if (ddpt is null)
        {
            return new TraktorWriteResult(false, "error", $"device '{device}' has no DDPT", null);
        }

        var original = ReadPortStrings(ddpt);
        var newPorts = new List<string>(original);
        if (newPorts.Count == 0)
        {
            newPorts.Add("None");
        }

        if (newPorts.Count < 2)
        {
            newPorts.Add(portName);
        }
        else
        {
            newPorts[1] = portName;
        }

        if (newPorts.SequenceEqual(original))
        {
            return new TraktorWriteResult(true, "done",
                $"out-port already '{portName}' (in-port '{newPorts[0]}')", null);
        }

        var newDdpt = Concat(newPorts.Select(TlvCodec.EncodeUtf16Be));
        var newDdat = ReplaceDdatChunk(ddat, "DDPT", TlvCodec.BuildTlv("DDPT", newDdpt));
        var newDevi = RebuildDevi(devi, restOffset, newDdat);
        var newBinary = RebuildWithDevice(binary, device, newDevi);

        string newText;
        try
        {
            newText = ReplaceConfigValue(text, newBinary);
        }
        catch (InvalidOperationException ex)
        {
            return new TraktorWriteResult(false, "error", ex.Message, null);
        }

        var backup = Backup(tsiPath);
        WriteXmlText(tsiPath, newText, hasBom);

        var check = ReadPorts(tsiPath, device);
        return new TraktorWriteResult(true, "done",
            $"out-port -> '{check.OutPort}' (in-port '{check.InPort}')", backup);
    }

    // ------------------------------------------------------------------
    // Write: out-mapping injection
    // ------------------------------------------------------------------

    /// <summary>
    /// Append MidiMAT's out-mappings to the named device's <c>DDCB</c>, leaving every other
    /// device and every existing mapping intact. Idempotent: an entry whose
    /// <c>(cmd_id, target, key)</c> is already present is skipped.
    /// </summary>
    public static TraktorWriteResult InjectMappings(
        string tsiPath,
        IReadOnlyList<MappingSpec> pack,
        string device = DefaultDevice)
    {
        if (IsTraktorRunning())
        {
            return new TraktorWriteResult(false, "error",
                "Traktor is running — close it before MidiMAT writes the settings file.", null);
        }

        if (!File.Exists(tsiPath))
        {
            return new TraktorWriteResult(false, "error", $"Traktor settings not found: {tsiPath}", null);
        }

        if (pack is null || pack.Count == 0)
        {
            return new TraktorWriteResult(true, "done", "no mappings to inject", null);
        }

        foreach (var spec in pack)
        {
            if (spec.Cc is < 0 or > MaxMidiCc)
            {
                return new TraktorWriteResult(false, "error",
                    $"CC out of Traktor's range (0..{MaxMidiCc}): {spec.Key} — Traktor would drop it.", null);
            }
        }

        var text = ReadXmlText(tsiPath, out var hasBom);

        byte[] binary;
        try
        {
            binary = ExtractConfigBinary(text);
        }
        catch (Exception ex) when (ex is FormatException or InvalidOperationException)
        {
            return new TraktorWriteResult(false, "error", $"could not decode DeviceIO.Config: {ex.Message}", null);
        }

        var found = FindDevice(binary, device);
        if (found is null)
        {
            return new TraktorWriteResult(false, "error", $"device '{device}' not found in {Path.GetFileName(tsiPath)}", null);
        }

        var (devi, restOffset) = found.Value;
        var ddat = FindChunk(TlvCodec.ParseTlv(devi, restOffset), "DDAT");
        var ddcb = FindChunkOrNull(TlvCodec.ParseTlv(ddat), "DDCB");
        if (ddcb is null)
        {
            return new TraktorWriteResult(false, "error", $"device '{device}' has no DDCB", null);
        }

        var (cmaiPayloads, bindings) = SplitDdcb(ddcb);
        var keyByIdx = new Dictionary<uint, string>();
        foreach (var binding in bindings)
        {
            keyByIdx[binding.Idx] = binding.Name;
        }

        // Existing signatures, so a second run is a no-op.
        var existing = new HashSet<(uint CmdId, uint Target, string Key)>();
        foreach (var cmai in cmaiPayloads)
        {
            var (idx, _, cmdId) = ReadCmaiHeader(cmai);
            var target = ReadCmadTarget(cmai);
            var key = keyByIdx.TryGetValue(idx, out var k) ? k : string.Empty;
            existing.Add((cmdId, target, key));
        }

        // idx is device-local and arbitrary: a fresh max(idx)+2 is valid (and leaves a gap).
        var nextIdx = bindings.Count == 0 ? 0u : bindings.Max(b => b.Idx);
        nextIdx += 2;

        var newCmai = new List<byte[]>(cmaiPayloads);
        var newBindings = new List<DcbmBinding>(bindings);
        var added = 0;
        var skipped = 0;

        foreach (var spec in pack)
        {
            var signature = ((uint)spec.CmdId, (uint)spec.Target, spec.Key);
            if (existing.Contains(signature))
            {
                skipped++;
                continue;
            }

            var cmad = BuildOutputCmad((uint)spec.Target);
            newCmai.Add(BuildCmai(nextIdx, OutputMappingType, (uint)spec.CmdId, cmad));
            newBindings.Add(new DcbmBinding(nextIdx, spec.Key));
            existing.Add(signature);
            added++;
            nextIdx += 2;
        }

        if (added == 0)
        {
            return new TraktorWriteResult(true, "done",
                $"all {skipped} mapping(s) already present; nothing to inject", null);
        }

        var newDdcb = BuildDdcb(newCmai, newBindings);
        var newDdat = ReplaceDdatChunk(ddat, "DDCB", newDdcb);
        var newDevi = RebuildDevi(devi, restOffset, newDdat);
        var newBinary = RebuildWithDevice(binary, device, newDevi);

        string newText;
        try
        {
            newText = ReplaceConfigValue(text, newBinary);
        }
        catch (InvalidOperationException ex)
        {
            return new TraktorWriteResult(false, "error", ex.Message, null);
        }

        var backup = Backup(tsiPath);
        WriteXmlText(tsiPath, newText, hasBom);

        return new TraktorWriteResult(true, "done",
            $"added {added}, skipped {skipped} (device now holds {newCmai.Count} mappings)", backup);
    }

    // ------------------------------------------------------------------
    // TLV navigation / rebuild (mirrors scripts/prototype_tsi_inject.py)
    // ------------------------------------------------------------------

    private readonly record struct DcbmBinding(uint Idx, string Name);

    private static (byte[] Devi, int RestOffset)? FindDevice(byte[] binary, string name)
    {
        var diom = FindChunk(TlvCodec.ParseTlv(binary), "DIOM");
        var devs = FindChunk(TlvCodec.ParseTlv(diom), "DEVS");

        foreach (var chunk in TlvCodec.ParseTlv(devs, 4))
        {
            if (chunk.Tag != "DEVI")
            {
                continue;
            }

            var (deviceName, restOffset) = TlvCodec.DecodeUtf16Be(chunk.Payload, 0);
            if (deviceName == name)
            {
                return (chunk.Payload, restOffset);
            }
        }

        return null;
    }

    private static (List<byte[]> CmaiPayloads, List<DcbmBinding> Bindings) SplitDdcb(byte[] ddcb)
    {
        var inner = TlvCodec.ParseTlv(ddcb);

        var cmaiPayloads = new List<byte[]>();
        var cmas = FindChunkOrNull(inner, "CMAS");
        if (cmas is not null)
        {
            foreach (var chunk in TlvCodec.ParseTlv(cmas, 4))
            {
                if (chunk.Tag == "CMAI")
                {
                    cmaiPayloads.Add(chunk.Payload);
                }
            }
        }

        var bindings = new List<DcbmBinding>();
        var dcbm = FindChunkOrNull(inner, "DCBM");
        if (dcbm is not null)
        {
            foreach (var chunk in TlvCodec.ParseTlv(dcbm, 4))
            {
                if (chunk.Tag == "DCBM" && chunk.Payload.Length >= 4)
                {
                    var idx = TlvCodec.ReadU32(chunk.Payload, 0);
                    var name = TlvCodec.DecodeUtf16Be(chunk.Payload, 4).Value;
                    bindings.Add(new DcbmBinding(idx, name));
                }
            }
        }

        return (cmaiPayloads, bindings);
    }

    private static (uint MidiIdx, uint MappingType, uint CmdId) ReadCmaiHeader(byte[] cmai)
    {
        if (cmai.Length < 12)
        {
            throw new InvalidOperationException($"CMAI payload too short: {cmai.Length}");
        }

        return (TlvCodec.ReadU32(cmai, 0), TlvCodec.ReadU32(cmai, 4), TlvCodec.ReadU32(cmai, 8));
    }

    /// <summary>Read the `target` field (CMAD word 3) from a CMAI payload.</summary>
    private static uint ReadCmadTarget(byte[] cmai)
    {
        if (cmai.Length < 12)
        {
            return 0;
        }

        foreach (var chunk in TlvCodec.ParseTlv(cmai, 12))
        {
            if (chunk.Tag == "CMAD" && chunk.Payload.Length >= 16)
            {
                return TlvCodec.ReadU32(chunk.Payload, 12);
            }
        }

        return 0;
    }

    /// <summary>
    /// Build the 120-byte CMAD for a MidiMAT out-mapping: the knob field layout with
    /// ControlType patched to 0xFFFF and InteractionMode = 8 (matches the proven script).
    /// </summary>
    private static byte[] BuildOutputCmad(uint target)
    {
        uint[] fields =
        {
            4, OutputControlType, OutputInteractionMode, target,
            0, 0, 0, 0x40A00000,
            0, 0, 2, 0x3F800000,
            0, 0, 0, 0,
            0, 0, 0, 2,
            0, 2, 0x3F800000, 0,
            127, 0, 1, 2,
            0x3D800000, 0,
        };

        var payload = new byte[120];
        for (var i = 0; i < fields.Length; i++)
        {
            TlvCodec.WriteU32(payload, i * 4, fields[i]);
        }

        return payload;
    }

    private static byte[] BuildCmai(uint midiIdx, uint mappingType, uint cmdId, byte[] cmad)
    {
        var header = Concat(
            TlvCodec.U32(midiIdx),
            TlvCodec.U32(mappingType),
            TlvCodec.U32(cmdId));
        return Concat(header, TlvCodec.BuildTlv("CMAD", cmad));
    }

    private static byte[] BuildDdcb(IReadOnlyList<byte[]> cmaiPayloads, IReadOnlyList<DcbmBinding> bindings)
    {
        var cmasInner = new List<byte>(TlvCodec.U32((uint)cmaiPayloads.Count));
        foreach (var raw in cmaiPayloads)
        {
            cmasInner.AddRange(TlvCodec.BuildTlv("CMAI", raw));
        }

        var cmas = TlvCodec.BuildTlv("CMAS", cmasInner.ToArray());

        var dcbmInner = new List<byte>(TlvCodec.U32((uint)bindings.Count));
        foreach (var binding in bindings)
        {
            dcbmInner.AddRange(TlvCodec.BuildTlv("DCBM",
                Concat(TlvCodec.U32(binding.Idx), TlvCodec.EncodeUtf16Be(binding.Name))));
        }

        var dcbm = TlvCodec.BuildTlv("DCBM", dcbmInner.ToArray());

        return TlvCodec.BuildTlv("DDCB", Concat(cmas, dcbm));
    }

    /// <summary>Rebuild a DEVI, replacing only its DDAT (name + every other chunk preserved).</summary>
    private static byte[] RebuildDevi(byte[] devi, int restOffset, byte[] newDdat)
    {
        var name = TlvCodec.DecodeUtf16Be(devi, 0).Value;
        var nameBytes = TlvCodec.EncodeUtf16Be(name);

        var rest = new List<byte>();
        foreach (var chunk in TlvCodec.ParseTlv(devi, restOffset))
        {
            rest.AddRange(chunk.Tag == "DDAT"
                ? TlvCodec.BuildTlv("DDAT", newDdat)
                : TlvCodec.BuildTlv(chunk.Tag, chunk.Payload));
        }

        return Concat(nameBytes, rest.ToArray());
    }

    /// <summary>Rebuild a DDAT, replacing only the chunks tagged <paramref name="tag"/>.</summary>
    private static byte[] ReplaceDdatChunk(byte[] ddat, string tag, byte[] newChunk)
    {
        var result = new List<byte>();
        foreach (var chunk in TlvCodec.ParseTlv(ddat))
        {
            result.AddRange(chunk.Tag == tag ? newChunk : TlvCodec.BuildTlv(chunk.Tag, chunk.Payload));
        }

        return result.ToArray();
    }

    /// <summary>
    /// Rebuild the DIOM/DEVS tree, replacing only <paramref name="deviceName"/>'s DEVI.
    /// Every other device is copied byte-for-byte.
    /// </summary>
    private static byte[] RebuildWithDevice(byte[] binary, string deviceName, byte[] newDevi)
    {
        var diomPayload = FindChunk(TlvCodec.ParseTlv(binary), "DIOM");

        var newDiom = new List<byte>();
        foreach (var chunk in TlvCodec.ParseTlv(diomPayload))
        {
            if (chunk.Tag != "DEVS")
            {
                newDiom.AddRange(TlvCodec.BuildTlv(chunk.Tag, chunk.Payload));
                continue;
            }

            var count = TlvCodec.ReadU32(chunk.Payload, 0);
            var newDevs = new List<byte>(TlvCodec.U32(count));

            foreach (var deviChunk in TlvCodec.ParseTlv(chunk.Payload, 4))
            {
                if (deviChunk.Tag != "DEVI")
                {
                    newDevs.AddRange(TlvCodec.BuildTlv(deviChunk.Tag, deviChunk.Payload));
                    continue;
                }

                var name = TlvCodec.DecodeUtf16Be(deviChunk.Payload, 0).Value;
                newDevs.AddRange(TlvCodec.BuildTlv("DEVI",
                    name == deviceName ? newDevi : deviChunk.Payload));
            }

            newDiom.AddRange(TlvCodec.BuildTlv("DEVS", newDevs.ToArray()));
        }

        return TlvCodec.BuildTlv("DIOM", newDiom.ToArray());
    }

    // ------------------------------------------------------------------
    // DDPT port strings ([u32 char-count][utf16be], repeated)
    // ------------------------------------------------------------------

    private static List<string> ReadPortStrings(byte[] ddpt)
    {
        var ports = new List<string>();
        var offset = 0;

        while (offset + 4 <= ddpt.Length)
        {
            var count = TlvCodec.ReadU32(ddpt, offset);
            long end = offset + 4L + (long)count * 2;
            if (end > ddpt.Length)
            {
                break;
            }

            ports.Add(Encoding.BigEndianUnicode.GetString(ddpt, offset + 4, (int)count * 2));
            offset = (int)end;
        }

        return ports;
    }

    // ------------------------------------------------------------------
    // Surgical XML read/write
    // ------------------------------------------------------------------

    // Matches ONLY the Value="…" attribute of a DeviceIO.Config.* entry:
    //   group 1 = up to and including Value=", group 2 = the base64 value, group 3 = closing quote.
    private static readonly Regex ConfigEntryRegex = new(
        "(<Entry\\s+Name=\"DeviceIO\\.Config\\.[^\"]*\"\\s+Type=\"\\d+\"\\s+Value=\")([^\"]*)(\")",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    private static byte[] ExtractConfigBinary(string xmlText)
    {
        var match = ConfigEntryRegex.Match(xmlText);
        if (!match.Success)
        {
            throw new InvalidOperationException("no DeviceIO.Config entry found");
        }

        return Convert.FromBase64String(match.Groups[2].Value);
    }

    private static string ReplaceConfigValue(string xmlText, byte[] binary)
    {
        if (!ConfigEntryRegex.IsMatch(xmlText))
        {
            throw new InvalidOperationException("no DeviceIO.Config entry found");
        }

        var payload = Convert.ToBase64String(binary);
        return ConfigEntryRegex.Replace(
            xmlText,
            m => m.Groups[1].Value + payload + m.Groups[3].Value,
            count: 1);
    }

    /// <summary>
    /// Read the file as text without normalising anything. A UTF-8 BOM (if present) is
    /// stripped here and re-added on write so every byte outside the patched attribute is
    /// preserved exactly.
    /// </summary>
    private static string ReadXmlText(string path, out bool hasBom)
    {
        var bytes = File.ReadAllBytes(path);
        hasBom = bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF;
        var start = hasBom ? 3 : 0;
        return new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)
            .GetString(bytes, start, bytes.Length - start);
    }

    private static void WriteXmlText(string path, string text, bool hasBom)
    {
        var body = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false).GetBytes(text);

        if (!hasBom)
        {
            File.WriteAllBytes(path, body);
            return;
        }

        var withBom = new byte[body.Length + 3];
        withBom[0] = 0xEF;
        withBom[1] = 0xBB;
        withBom[2] = 0xBF;
        Array.Copy(body, 0, withBom, 3, body.Length);
        File.WriteAllBytes(path, withBom);
    }

    /// <summary>Copy the file to a timestamped sibling backup; returns the backup path.</summary>
    private static string Backup(string tsiPath)
    {
        var stamp = DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture);
        var backup = $"{tsiPath}.midimat-backup-{stamp}";

        var suffix = 1;
        while (File.Exists(backup))
        {
            backup = $"{tsiPath}.midimat-backup-{stamp}-{suffix++}";
        }

        File.Copy(tsiPath, backup, overwrite: false);
        return backup;
    }

    // ------------------------------------------------------------------
    // Small helpers
    // ------------------------------------------------------------------

    private static byte[] FindChunk(List<TlvChunk> chunks, string tag)
        => FindChunkOrNull(chunks, tag)
           ?? throw new InvalidOperationException($"TLV tag '{tag}' not found");

    private static byte[]? FindChunkOrNull(List<TlvChunk> chunks, string tag)
    {
        foreach (var chunk in chunks)
        {
            if (chunk.Tag == tag)
            {
                return chunk.Payload;
            }
        }

        return null;
    }

    private static byte[] Concat(params byte[][] parts)
    {
        var length = 0;
        foreach (var part in parts)
        {
            length += part.Length;
        }

        var result = new byte[length];
        var offset = 0;
        foreach (var part in parts)
        {
            Array.Copy(part, 0, result, offset, part.Length);
            offset += part.Length;
        }

        return result;
    }

    private static byte[] Concat(IEnumerable<byte[]> parts) => Concat(parts.ToArray());
}

/// <summary>A parsed TLV chunk: 4-byte ASCII tag + payload, at its original offset.</summary>
internal readonly record struct TlvChunk(string Tag, byte[] Payload, int StartOffset);

/// <summary>
/// Minimal Traktor TSI TLV codec (tag + u32 BE length + payload) plus the
/// <c>[u32 char-count][utf16be bytes]</c> string form used throughout the format.
/// Deliberately dependency-free (a port of the <c>py-ni-traktor-tsi</c> primitives).
/// </summary>
internal static class TlvCodec
{
    /// <summary>Parse consecutive TLV chunks starting at <paramref name="offset"/>.</summary>
    public static List<TlvChunk> ParseTlv(byte[] data, int offset = 0)
    {
        var chunks = new List<TlvChunk>();

        while (offset + 8 <= data.Length)
        {
            var tag = Encoding.ASCII.GetString(data, offset, 4);
            var length = ReadU32(data, offset + 4);
            var payloadStart = offset + 8;
            var available = data.Length - payloadStart;
            var take = length <= (uint)available ? (int)length : available;

            var payload = new byte[take];
            Array.Copy(data, payloadStart, payload, 0, take);
            chunks.Add(new TlvChunk(tag, payload, offset));

            long next = payloadStart + (long)length;
            if (next > data.Length)
            {
                break;
            }

            offset = (int)next;
        }

        return chunks;
    }

    /// <summary>Build a TLV chunk from a 4-char tag and payload.</summary>
    public static byte[] BuildTlv(string tag, byte[] payload)
    {
        var buffer = new byte[8 + payload.Length];
        var tagBytes = Encoding.ASCII.GetBytes(tag);
        Array.Copy(tagBytes, 0, buffer, 0, Math.Min(4, tagBytes.Length));
        WriteU32(buffer, 4, (uint)payload.Length);
        Array.Copy(payload, 0, buffer, 8, payload.Length);
        return buffer;
    }

    /// <summary>Encode a string as <c>[u32 char-count][utf16be bytes]</c> (single length prefix).</summary>
    public static byte[] EncodeUtf16Be(string value)
    {
        var body = Encoding.BigEndianUnicode.GetBytes(value);
        var buffer = new byte[4 + body.Length];
        WriteU32(buffer, 0, (uint)value.Length); // UTF-16 code units
        Array.Copy(body, 0, buffer, 4, body.Length);
        return buffer;
    }

    /// <summary>Decode a <c>[u32 char-count][utf16be bytes]</c> string; returns the next offset.</summary>
    public static (string Value, int NextOffset) DecodeUtf16Be(byte[] data, int offset)
    {
        var count = ReadU32(data, offset);
        var start = offset + 4;
        long bytes = (long)count * 2;
        var available = Math.Max(0, data.Length - start);
        var take = bytes <= available ? (int)bytes : available;
        var value = Encoding.BigEndianUnicode.GetString(data, start, take);
        return (value, start + take);
    }

    /// <summary>A 4-byte big-endian encoding of <paramref name="value"/>.</summary>
    public static byte[] U32(uint value)
    {
        var buffer = new byte[4];
        WriteU32(buffer, 0, value);
        return buffer;
    }

    public static uint ReadU32(byte[] data, int offset) =>
        ((uint)data[offset] << 24) | ((uint)data[offset + 1] << 16) | ((uint)data[offset + 2] << 8) | data[offset + 3];

    public static void WriteU32(byte[] buffer, int offset, uint value)
    {
        buffer[offset] = (byte)(value >> 24);
        buffer[offset + 1] = (byte)(value >> 16);
        buffer[offset + 2] = (byte)(value >> 8);
        buffer[offset + 3] = (byte)value;
    }
}
