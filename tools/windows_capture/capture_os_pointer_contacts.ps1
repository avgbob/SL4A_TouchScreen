# Capture OS-facing WM_POINTER events on Windows 10/11 from a full-screen test window.
# Windows PowerShell 5.1 (STA) with .NET Framework Windows Forms is recommended.
# This is a RESEARCH PROBE, not a HID-level contact report decoder.
# It does not modify drivers or devices; it writes a local CSV in the user's Desktop.
# The pointer ID supplied by Windows WM_POINTER is NOT automatically the raw HID Contact ID.
param(
    [string]$CsvPath = (Join-Path ([Environment]::GetFolderPath('Desktop'))
        ('sl4a-os-pointer-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.csv'))
)

if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    throw 'Launch in STA: powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File .\capture_os_pointer_contacts.ps1'
}
if ([System.IO.File]::Exists($CsvPath)) {
    throw "Refusing to overwrite existing CSV: $CsvPath"
}
$code = @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public sealed class Sl4aPointerCapture : Form
{
    const int WM_POINTERUPDATE = 0x0245;
    const int WM_POINTERDOWN = 0x0246;
    const int WM_POINTERUP = 0x0247;
    const int WM_POINTERENTER = 0x0249;
    const int WM_POINTERLEAVE = 0x024A;
    const int WM_POINTERCAPTURECHANGED = 0x024C;

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool GetPointerType(uint pointerId, out uint pointerType);

    readonly StreamWriter writer;
    readonly HashSet<uint> active = new HashSet<uint>();
    readonly string outputPath;
    long count;

    public Sl4aPointerCapture(string path)
    {
        outputPath = path;
        writer = new StreamWriter(path, false, System.Text.Encoding.UTF8);
        writer.AutoFlush = true;
        writer.WriteLine("UtcTimestamp,StopwatchTicks,Event,PointerId,PointerType,ScreenX,ScreenY,WParamHex");
        Text = "SL4A: Windows pointer contact reference - ESC to end";
        FormBorderStyle = FormBorderStyle.None;
        WindowState = FormWindowState.Maximized;
        BackColor = Color.FromArgb(25, 30, 40);
        ForeColor = Color.White;
        KeyPreview = true;
        DoubleBuffered = true;
        KeyDown += (sender, args) => { if (args.KeyCode == Keys.Escape) Close(); };
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        using (Font title = new Font(FontFamily.GenericSansSerif, 22, FontStyle.Bold))
        using (Font smaller = new Font(FontFamily.GenericSansSerif, 14))
        using (Brush brush = new SolidBrush(Color.White))
        using (Pen pen = new Pen(Color.FromArgb(90, 150, 180), 2))
        {
            e.Graphics.DrawString("SL4A Windows contact oracle", title, brush, 40, 28);
            e.Graphics.DrawString("Touch with 1 and 2 fingers, pinch, separate, lift. Press ESC to stop.", smaller, brush, 40, 90);
            e.Graphics.DrawString("Pointer messages: " + count + "   Active IDs: " + active.Count, smaller, brush, 40, 135);
            int top = 180, bottom = ClientSize.Height - 40;
            int left = 60, right = ClientSize.Width - 60;
            for (int i = 1; i <= 2; i++)
            {
                int x = left + (right - left) * i / 3;
                int y = top + (bottom - top) * i / 3;
                e.Graphics.DrawLine(pen, x, top, x, bottom);
                e.Graphics.DrawLine(pen, left, y, right, y);
            }
        }
    }

    protected override void WndProc(ref Message m)
    {
        string eventName = null;
        switch (m.Msg)
        {
            case WM_POINTERUPDATE: eventName = "UPDATE"; break;
            case WM_POINTERDOWN: eventName = "DOWN"; break;
            case WM_POINTERUP: eventName = "UP"; break;
            case WM_POINTERENTER: eventName = "ENTER"; break;
            case WM_POINTERLEAVE: eventName = "LEAVE"; break;
            case WM_POINTERCAPTURECHANGED: eventName = "CAPTURE_CHANGED"; break;
        }
        if (eventName != null)
        {
            ulong w = unchecked((ulong)m.WParam.ToInt64());
            long l = m.LParam.ToInt64();
            uint pointerId = (uint)(w & 0xffff);
            short x = unchecked((short)(l & 0xffff));
            short y = unchecked((short)((l >> 16) & 0xffff));
            uint pointerType;
            if (!GetPointerType(pointerId, out pointerType)) pointerType = 0;
            if (m.Msg == WM_POINTERDOWN) active.Add(pointerId);
            if (m.Msg == WM_POINTERUP || m.Msg == WM_POINTERCAPTURECHANGED) active.Remove(pointerId);
            writer.WriteLine(
                DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "," +
                Stopwatch.GetTimestamp().ToString(CultureInfo.InvariantCulture) + "," +
                eventName + "," + pointerId + "," + pointerType + "," +
                x + "," + y + ",0x" + w.ToString("X16", CultureInfo.InvariantCulture));
            count++;
            if (m.Msg != WM_POINTERUPDATE || count % 12 == 0) Invalidate();
        }
        base.WndProc(ref m);
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        writer.Dispose();
        base.OnFormClosed(e);
    }
}
'@
Add-Type -TypeDefinition $code -ReferencedAssemblies 'System.Windows.Forms','System.Drawing' -ErrorAction Stop
Write-Host "Pointer CSV: $CsvPath"
Write-Host "ESC closes the capture window. Keep original Windows drivers unchanged."
$form = New-Object Sl4aPointerCapture($CsvPath)
try {
    [System.Windows.Forms.Application]::Run($form)
}
finally {
    $form.Dispose()
}
$events = @(Import-Csv -LiteralPath $CsvPath)
$down = @($events | Where-Object { $_.Event -eq 'DOWN' }).Count
$up = @($events | Where-Object { $_.Event -eq 'UP' }).Count
Write-Host "Captured $($events.Count) pointer messages; DOWN=$down, UP=$up."
if ($down -eq 0) {
    Write-Warning 'No WM_POINTERDOWN events received. This CSV is NOT usable as contact ground truth until capture is validated.'
}
Write-Host "Saved: $CsvPath"
