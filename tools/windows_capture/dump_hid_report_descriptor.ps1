param(
    [string]$OutDir = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$src = @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class HidReportDescriptorDump
{
    const uint DIGCF_PRESENT = 0x00000002;
    const uint DIGCF_DEVICEINTERFACE = 0x00000010;
    const uint GENERIC_READ = 0x80000000;
    const uint GENERIC_WRITE = 0x40000000;
    const uint FILE_SHARE_READ = 0x00000001;
    const uint FILE_SHARE_WRITE = 0x00000002;
    const uint OPEN_EXISTING = 3;
    const uint IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0007;

    [StructLayout(LayoutKind.Sequential)]
    struct SP_DEVICE_INTERFACE_DATA
    {
        public int cbSize;
        public Guid InterfaceClassGuid;
        public int Flags;
        public IntPtr Reserved;
    }

    [DllImport("hid.dll")]
    static extern void HidD_GetHidGuid(out Guid HidGuid);

    [DllImport("setupapi.dll", CharSet=CharSet.Auto, SetLastError=true)]
    static extern IntPtr SetupDiGetClassDevs(
        ref Guid ClassGuid,
        IntPtr Enumerator,
        IntPtr hwndParent,
        uint Flags);

    [DllImport("setupapi.dll", SetLastError=true)]
    static extern bool SetupDiEnumDeviceInterfaces(
        IntPtr DeviceInfoSet,
        IntPtr DeviceInfoData,
        ref Guid InterfaceClassGuid,
        uint MemberIndex,
        ref SP_DEVICE_INTERFACE_DATA DeviceInterfaceData);

    [DllImport("setupapi.dll", CharSet=CharSet.Auto, SetLastError=true)]
    static extern bool SetupDiGetDeviceInterfaceDetail(
        IntPtr DeviceInfoSet,
        ref SP_DEVICE_INTERFACE_DATA DeviceInterfaceData,
        IntPtr DeviceInterfaceDetailData,
        uint DeviceInterfaceDetailDataSize,
        out uint RequiredSize,
        IntPtr DeviceInfoData);

    [DllImport("setupapi.dll")]
    static extern bool SetupDiDestroyDeviceInfoList(IntPtr DeviceInfoSet);

    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    static extern SafeFileHandle CreateFile(
        string lpFileName,
        uint dwDesiredAccess,
        uint dwShareMode,
        IntPtr lpSecurityAttributes,
        uint dwCreationDisposition,
        uint dwFlagsAndAttributes,
        IntPtr hTemplateFile);

    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool DeviceIoControl(
        SafeFileHandle hDevice,
        uint dwIoControlCode,
        IntPtr lpInBuffer,
        uint nInBufferSize,
        byte[] lpOutBuffer,
        uint nOutBufferSize,
        out uint lpBytesReturned,
        IntPtr lpOverlapped);

    public sealed class Result
    {
        public string Path;
        public byte[] Descriptor;
        public int Error;
    }

    public static List<string> EnumerateHidPaths()
    {
        Guid hidGuid;
        HidD_GetHidGuid(out hidGuid);

        IntPtr set = SetupDiGetClassDevs(
            ref hidGuid, IntPtr.Zero, IntPtr.Zero,
            DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

        if (set == new IntPtr(-1))
            throw new Win32Exception(Marshal.GetLastWin32Error());

        var result = new List<string>();
        try
        {
            for (uint index = 0; ; index++)
            {
                var data = new SP_DEVICE_INTERFACE_DATA();
                data.cbSize = Marshal.SizeOf(typeof(SP_DEVICE_INTERFACE_DATA));

                if (!SetupDiEnumDeviceInterfaces(
                    set, IntPtr.Zero, ref hidGuid, index, ref data))
                {
                    int err = Marshal.GetLastWin32Error();
                    if (err == 259) break;
                    throw new Win32Exception(err);
                }

                uint need;
                SetupDiGetDeviceInterfaceDetail(
                    set, ref data, IntPtr.Zero, 0, out need, IntPtr.Zero);

                IntPtr detail = Marshal.AllocHGlobal((int)need);
                try
                {
                    Marshal.WriteInt32(detail, IntPtr.Size == 8 ? 8 : 6);

                    if (!SetupDiGetDeviceInterfaceDetail(
                        set, ref data, detail, need, out need, IntPtr.Zero))
                        throw new Win32Exception(Marshal.GetLastWin32Error());

                    IntPtr pPath = IntPtr.Add(detail, 4);
                    string path = Marshal.PtrToStringUni(pPath);
                    if (!String.IsNullOrEmpty(path))
                        result.Add(path);
                }
                finally
                {
                    Marshal.FreeHGlobal(detail);
                }
            }
        }
        finally
        {
            SetupDiDestroyDeviceInfoList(set);
        }
        return result;
    }

    public static Result ReadDescriptor(string path)
    {
        var r = new Result();
        r.Path = path;

        SafeFileHandle h = CreateFile(
            path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            IntPtr.Zero,
            OPEN_EXISTING,
            0,
            IntPtr.Zero);

        if (h.IsInvalid)
        {
            r.Error = Marshal.GetLastWin32Error();
            return r;
        }

        using (h)
        {
            byte[] buffer = new byte[8192];
            uint got;
            bool ok = DeviceIoControl(
                h,
                IOCTL_HID_GET_REPORT_DESCRIPTOR,
                IntPtr.Zero, 0,
                buffer, (uint)buffer.Length,
                out got,
                IntPtr.Zero);

            if (!ok)
            {
                r.Error = Marshal.GetLastWin32Error();
                return r;
            }

            r.Descriptor = new byte[got];
            Buffer.BlockCopy(buffer, 0, r.Descriptor, 0, (int)got);
            return r;
        }
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp

$paths = [HidReportDescriptorDump]::EnumerateHidPaths()
$log = New-Object System.Collections.Generic.List[string]
$ok  = @()

foreach ($p in $paths) {
    $low = $p.ToLowerInvariant()
    if ($low -notmatch 'mshw0231|vid_045e&pid_0c19') {
        continue
    }

    $r = [HidReportDescriptorDump]::ReadDescriptor($p)
    if ($null -ne $r.Descriptor -and $r.Descriptor.Length -gt 0) {
        $ok += $r
        $log.Add("OK bytes=$($r.Descriptor.Length) path=$p")
    } else {
        $log.Add("FAIL win32=$($r.Error) path=$p")
    }
}

$log | Set-Content -Encoding utf8 (Join-Path $OutDir "report-descriptor-attempts.txt")

if ($ok.Count -eq 0) {
    "No MSHW0231/045E:0C19 HID interface returned IOCTL_HID_GET_REPORT_DESCRIPTOR." |
        Set-Content -Encoding utf8 (Join-Path $OutDir "report-descriptor-NOT-RECOVERED.txt")
    exit 2
}

$best = $ok | Sort-Object { $_.Descriptor.Length } -Descending | Select-Object -First 1
$bin = Join-Path $OutDir "mshw0231_report_descriptor.bin"
[IO.File]::WriteAllBytes($bin, $best.Descriptor)

$hex = for ($i = 0; $i -lt $best.Descriptor.Length; $i += 16) {
    $last = [Math]::Min($i+15,$best.Descriptor.Length-1)
    $chunk = $best.Descriptor[$i..$last]
    "{0:X4}: {1}" -f $i,(($chunk | ForEach-Object { "{0:X2}" -f $_ }) -join " ")
}
$hex | Set-Content -Encoding ascii (Join-Path $OutDir "mshw0231_report_descriptor.txt")

[pscustomobject]@{
    path = $best.Path
    bytes = $best.Descriptor.Length
    sha256 = (Get-FileHash -Algorithm SHA256 $bin).Hash.ToLowerInvariant()
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $OutDir "mshw0231_report_descriptor.json")

Write-Host "Recovered HID report descriptor: $($best.Descriptor.Length) bytes"
exit 0
