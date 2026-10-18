# SL4A Windows multi-touch observer V2: no driver/registry changes.
# Windows PowerShell 5.1 -STA. Press SPACE for next stage, M to annotate
# "two physical fingers on glass but the display counts fewer than two".
param([switch]$SelfTest, [string]$OutputFolder = '', [switch]$PhysicalTruthMode)

$ErrorActionPreference='Stop'
if (-not $SelfTest -and [Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    throw 'Run with powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File capture_os_pointer_contacts_v2.ps1'
}
if (-not $OutputFolder) {
    $OutputFolder=Join-Path ([Environment]::GetFolderPath('Desktop')) ('SL4A-Pinch-V2-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
}
$src=@'
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Drawing;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[StructLayout(LayoutKind.Sequential)] public struct WinPoint { public int X,Y; }
[StructLayout(LayoutKind.Sequential)] public struct WinRect { public int L,T,R,B; }
[StructLayout(LayoutKind.Sequential)] public struct PointerInfo {
 public uint Type, Id, FrameId, Flags;
 public IntPtr Device, Window;
 public WinPoint Pixel, Himetric, PixelRaw, HimetricRaw;
 public uint Time, History;
 public int InputData;
 public uint KeyStates;
 public ulong Performance;
 public uint ButtonChange;
}
[StructLayout(LayoutKind.Sequential)] public struct PointerTouchInfo {
 public PointerInfo Pointer;
 public uint Flags,Mask;
 public WinRect Contact,ContactRaw;
 public uint Orientation,Pressure;
}
public sealed class TouchModel {
 public Dictionary<uint,Point> Active=new Dictionary<uint,Point>();
 public int Down,Up,Duplicate,Orphan,CaptureLost;
 public void Apply(string kind,uint id,Point at) {
  if(kind=="DOWN") { if(Active.ContainsKey(id)) Duplicate++; Active[id]=at; Down++; }
  else if(kind=="UPDATE") { if(Active.ContainsKey(id)) Active[id]=at; }
  else if(kind=="UP" || kind=="CAPTURE_CHANGED" || kind=="CANCELLED") {
   if(!Active.Remove(id) && kind=="UP") Orphan++;
   if(kind=="UP") Up++; else CaptureLost++;
  }
 }
 public static int NativePointerSize(){return Marshal.SizeOf(typeof(PointerInfo));}
 public static void AssertSelfTest() {
  var a=new TouchModel();
  a.Apply("DOWN",1,new Point(20,20)); a.Apply("DOWN",2,new Point(200,20));
  if(a.Active.Count!=2) throw new Exception("2 contact regression");
  a.Apply("UP",1,Point.Empty);
  if(a.Active.Count!=1 || !a.Active.ContainsKey(2)) throw new Exception("staggered lift regression");
  a.Apply("UP",2,Point.Empty);
  if(a.Active.Count!=0 || a.Down!=2 || a.Up!=2)throw new Exception("final release regression");
 }
}
public sealed class PhysicalTruthModel {
 public int PhysicalCount=-1; // UNKNOWN until explicitly marked by operator
 public int Corrections=0;
 public int Marks=0;
 public string Apply(char key) {
  string action;
  switch(char.ToUpperInvariant(key)) {
   case 'B': PhysicalCount=2;action="BOTH_DOWN";break;
   case 'T': PhysicalCount=2;action="BOTH_STILL_DOWN";break;
   case 'R': PhysicalCount=2;action="SECOND_RETURNED";break;
   case 'L': PhysicalCount=1;action="SECOND_INTENTIONALLY_LIFTED";break;
   case 'N': PhysicalCount=0;action="BOTH_LIFTED";break;
   case 'X': PhysicalCount=-1;Corrections++;action="ANNOTATION_INVALIDATED";break;
   default: throw new ArgumentException("unknown physical marker");
  }
  Marks++;
  return action;
 }
 public static void AssertSelfTest() {
  var p=new PhysicalTruthModel();
  if(p.PhysicalCount!=-1)throw new Exception("missing initial UNKNOWN state");
  if(p.Apply('B')!="BOTH_DOWN"||p.PhysicalCount!=2)throw new Exception("two-finger mark");
  if(p.Apply('L')!="SECOND_INTENTIONALLY_LIFTED"||p.PhysicalCount!=1)throw new Exception("physical lift mark");
  if(p.Apply('R')!="SECOND_RETURNED"||p.PhysicalCount!=2)throw new Exception("physical return mark");
  if(p.Apply('N')!="BOTH_LIFTED"||p.PhysicalCount!=0)throw new Exception("physical zero mark");
  if(p.Apply('X')!="ANNOTATION_INVALIDATED"||p.PhysicalCount!=-1||p.Corrections!=1)throw new Exception("correction mark");
 }
}
public sealed class PinchWindow : Form {
 const int UPDATE=0x245,DOWN=0x246,UP=0x247,ENTER=0x249,LEAVE=0x24a,LOST=0x24c;
 const uint TOUCH=2, INCONTACT=0x4, CANCELLED=0x400;
 [DllImport("user32.dll",SetLastError=true)] static extern bool GetPointerType(uint id,out uint type);
 [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
 public static void TrySetDpiAware(){ try { SetProcessDPIAware(); } catch (EntryPointNotFoundException) {} }
 [DllImport("user32.dll",SetLastError=true)] static extern bool GetPointerInfo(uint id,out PointerInfo p);
 [DllImport("user32.dll",SetLastError=true)] static extern bool GetPointerTouchInfo(uint id,out PointerTouchInfo p);
 [DllImport("user32.dll",SetLastError=true)] static extern bool GetPointerFrameInfo(uint id,ref uint count,[Out] PointerInfo[] p);
 static readonly string[] Steps={
  "1 OF 4: ONE FINGER. Drag one finger. Lift.",
  "2 OF 4: TWO APART. Hold 5 sec, then SPACE WITHOUT LIFTING.",
  "3 OF 4: PINCH. SAME two fingers: slowly pinch 3 times, no lift.",
  "4 OF 4: LIFT one only, hold second 3 seconds, then lift."
 };
 static readonly string[] TruthSteps={
  "1/8 NO TOUCH: remove ALL fingers. Press N. Hold 2 seconds, then SPACE.",
  "2/8 TWO FAR APART: place two fingers far apart. Press B. Hold 3 seconds, then SPACE. KEEP THEM DOWN.",
  "3/8 PINCH - DO NOT LIFT: pinch/separate the SAME fingers 3 times. Press T when close or Windows shows 1. End close, then SPACE.",
  "4/8 CLOSE HOLD - DO NOT LIFT: keep both fingers close and still. Press T. Hold 3 seconds, then SPACE.",
  "5/8 LIFT SECOND ONLY: keep the original finger down. Lift only the other finger. Press L. Hold 3 seconds, then SPACE.",
  "6/8 ONE FINGER ONLY: keep the original finger down. Do NOT touch the second finger and press NO marker. Hold 3 seconds, then SPACE.",
  "7/8 RETURN SECOND: touch the second finger near its old close spot. Press R after it touches. Hold 3 seconds, then SPACE.",
  "8/8 LIFT BOTH: remove both fingers. Press N when the glass is empty. Hold 3 seconds, then SPACE to finish."
 };
 public static bool TruthMode=false;
 int StageTotal {get {return TruthMode?TruthSteps.Length:Steps.Length;}}
 string CurrentStep(int i){return TruthMode?TruthSteps[i]:Steps[i];}
 static string TruthKeyHelp(int i) {
  string[] help={
   "THIS STAGE: N = no fingers",
   "THIS STAGE: B = both down",
   "THIS STAGE: T = both still down",
   "THIS STAGE: T = both still down",
   "THIS STAGE: L = second intentionally lifted",
   "THIS STAGE: NO MARKER - just hold one finger",
   "THIS STAGE: R = second returned",
   "THIS STAGE: N = no fingers"
  };
  return help[i];
 }
 static int TruthExpected(int i) {
  int[] expected={0,2,2,2,1,1,2,0};
  return expected[i];
 }
 readonly TouchModel model=new TouchModel();
 readonly PhysicalTruthModel physical=new PhysicalTruthModel();
 readonly HashSet<Keys> heldKeys=new HashSet<Keys>();
 readonly StreamWriter events, samples;
 readonly Timer timer=new Timer();
 readonly string folder;
 readonly int[] ticks=new int[8],two=new int[8],one=new int[8],max=new int[8],marks=new int[8],frameTwo=new int[8];
 readonly int[] stageDown=new int[8],stageUp=new int[8],oneRun=new int[8],longestOneRun=new int[8];
 readonly double[] minDist={double.MaxValue,double.MaxValue,double.MaxValue,double.MaxValue,double.MaxValue,double.MaxValue,double.MaxValue,double.MaxValue}, maxDist=new double[8];
 readonly HashSet<uint>[] ids={
 new HashSet<uint>(),new HashSet<uint>(),new HashSet<uint>(),new HashSet<uint>(),
 new HashSet<uint>(),new HashSet<uint>(),new HashSet<uint>(),new HashSet<uint>()};
 readonly List<string> annotations=new List<string>();
 int stage=-1,frameContacts=-1,frameErr,errors,peak,framePeak;
 long messages;
 DateTime frameAt=DateTime.MinValue,begin=DateTime.UtcNow;
 bool finished=false;
 public PinchWindow(string target) {
  folder=target; Directory.CreateDirectory(target);
  events=new StreamWriter(Path.Combine(target,"events.csv"),false,Encoding.UTF8); events.AutoFlush=true;
  events.WriteLine("Utc,StopwatchTicks,Stage,Event,PointerId,MessageActive,FrameContacts,FrameAgeMs,PointerFlags,FrameId,X,Y,RawX,RawY,ContactL,ContactT,ContactR,ContactB,Pressure,Orientation,ApiError,ActiveIds,Note,OperatorPhysical");
  samples=new StreamWriter(Path.Combine(target,"samples.csv"),false,Encoding.UTF8);samples.AutoFlush=true;
  samples.WriteLine("Utc,Stage,Expected,MessageActive,FrameContacts,FrameAgeMs,ActiveIds,OperatorPhysical");
  Text=TruthMode?"SL4A PHYSICAL TRUTH V3":"SL4A PINCH TEST V2";FormBorderStyle=FormBorderStyle.None;WindowState=FormWindowState.Maximized;
  BackColor=Color.FromArgb(16,24,38);ForeColor=Color.White;KeyPreview=true;DoubleBuffered=true;
  KeyDown+=Key;KeyUp+=(sender,e)=>heldKeys.Remove(e.KeyCode); timer.Interval=100;timer.Tick+=(s,e)=>Sample();timer.Start();
 }
 string ActiveIds(){return string.Join("|",model.Active.Keys.OrderBy(x=>x));}
 bool Fresh(){return frameAt!=DateTime.MinValue&&(DateTime.UtcNow-frameAt).TotalMilliseconds<400;}
 string FCount(){return Fresh()?frameContacts.ToString():"NA";}
 int FAge(){return frameAt==DateTime.MinValue?-1:(int)(DateTime.UtcNow-frameAt).TotalMilliseconds;}
 string Utc(){return DateTime.UtcNow.ToString("O",CultureInfo.InvariantCulture);}
 void WriteEvent(string kind,uint id, int x,int y,PointerInfo p,PointerTouchInfo? t,int apiErr,string note){
  var c=t.HasValue?t.Value.Contact:new WinRect();
  string value=string.Join(",",new[]{
   Utc(),Stopwatch.GetTimestamp().ToString(),stage.ToString(),kind,id.ToString(),
   model.Active.Count.ToString(),FCount(),FAge().ToString(),"0x"+p.Flags.ToString("X8"),p.FrameId.ToString(),
   x.ToString(),y.ToString(),p.PixelRaw.X.ToString(),p.PixelRaw.Y.ToString(),
   t.HasValue?c.L.ToString():"",t.HasValue?c.T.ToString():"",
   t.HasValue?c.R.ToString():"",t.HasValue?c.B.ToString():"",
   t.HasValue?t.Value.Pressure.ToString():"",t.HasValue?t.Value.Orientation.ToString():"",
   apiErr.ToString(),ActiveIds(),note,physical.PhysicalCount.ToString()
  });events.WriteLine(value);
 }
 void Key(object sender,KeyEventArgs e){
  if(TruthMode && !heldKeys.Add(e.KeyCode)) {e.Handled=true;return;}
  if(e.KeyCode==Keys.Escape){e.Handled=true;Close();return;}
  if(TruthMode && (e.KeyCode==Keys.B||e.KeyCode==Keys.T||e.KeyCode==Keys.L||
                   e.KeyCode==Keys.R||e.KeyCode==Keys.N||e.KeyCode==Keys.X)) {
   e.Handled=true;e.SuppressKeyPress=true;
   char k=e.KeyCode.ToString()[0];
   string action=physical.Apply(k);
   WriteEvent("OPERATOR_"+action,0,0,0,new PointerInfo(),null,0,"KEY_"+k);
   annotations.Add(Utc()+" stage="+(stage+1)+" OPERATOR_"+action+
                   " physical="+physical.PhysicalCount+
                   " windows="+model.Active.Count+" frame="+FCount());
   Invalidate();
   return;
  }
  if(!TruthMode && e.KeyCode==Keys.M){
   e.Handled=true;string a=Utc()+" stage="+(stage+1)+" observedMessage="+model.Active.Count+" observedFrame="+FCount();
   annotations.Add(a);if(stage>=0&&stage<StageTotal)marks[stage]++;
   WriteEvent("PHYSICAL_TWO_MARK",0,0,0,new PointerInfo(),null,0,"USER_SAYS_TWO_ON_GLASS");
   Invalidate();return;
  }
  if(e.KeyCode==Keys.Space){
   e.Handled=true;
   if(stage>=StageTotal-1){stage=StageTotal;Close();return;}
   stage++;WriteEvent("STAGE_START",0,0,0,new PointerInfo(),null,0,"STEP_"+(stage+1));
   Invalidate();
  }
 }
 void Sample(){
  if(stage>=0&&stage<StageTotal&&!finished){
   ticks[stage]++;int n=model.Active.Count;
   if(n>=2)two[stage]++;else if(n==1)one[stage]++;
   if(Fresh()&&frameContacts>=2)frameTwo[stage]++;
   max[stage]=Math.Max(max[stage],n);
   // During the pinch stage, count drops AFTER a two-ID interval begins.
   // These are candidates, not physical truth unless also marked with M.
   if(!TruthMode && stage==2 && max[stage]>=2 && n==1) {
    oneRun[stage]++;longestOneRun[stage]=Math.Max(longestOneRun[stage],oneRun[stage]);
   } else oneRun[stage]=0;
   if(n>=2){
    var positions=model.Active.Values.Take(2).ToArray();
    double dx=positions[0].X-positions[1].X,dy=positions[0].Y-positions[1].Y;
    double distance=Math.Sqrt(dx*dx+dy*dy);
    minDist[stage]=Math.Min(minDist[stage],distance);
    maxDist[stage]=Math.Max(maxDist[stage],distance);
   }
   foreach(uint id in model.Active.Keys) ids[stage].Add(id);
   samples.WriteLine(string.Join(",",new[]{Utc(),(stage+1).ToString(),
     (TruthMode?TruthExpected(stage).ToString():(stage==0?"1":"2")),n.ToString(),FCount(),FAge().ToString(),ActiveIds(),physical.PhysicalCount.ToString()}));
  }
  Invalidate();
 }
 protected override void WndProc(ref Message m){
  string kind=null;
  switch(m.Msg){case ENTER:kind="ENTER";break;case DOWN:kind="DOWN";break;
   case UPDATE:kind="UPDATE";break;case UP:kind="UP";break;
   case LEAVE:kind="LEAVE";break;case LOST:kind="CAPTURE_CHANGED";break;}
  if(kind==null||events==null){base.WndProc(ref m);return;}
  uint id=unchecked((uint)(m.WParam.ToInt64()&65535L));
  uint type;
  if(!GetPointerType(id,out type)||type!=TOUCH){base.WndProc(ref m);return;}
  long lp=m.LParam.ToInt64();
  int x=unchecked((short)(lp&65535L)),y=unchecked((short)((lp>>16)&65535L));
  PointerInfo pi;bool good=GetPointerInfo(id,out pi);
  int error=good?0:Marshal.GetLastWin32Error();if(!good){errors++;pi=new PointerInfo();pi.PixelRaw.X=x;pi.PixelRaw.Y=y;}
  PointerTouchInfo ti;bool gotTouch=GetPointerTouchInfo(id,out ti);
  PointerTouchInfo? detail=gotTouch?(PointerTouchInfo?)ti:null;
  uint n=16;var frame=new PointerInfo[16];
  if(GetPointerFrameInfo(id,ref n,frame)){
   int contact=0;
   for(int i=0;i<Math.Min((int)n,frame.Length);i++)
    if(frame[i].Type==TOUCH&&(frame[i].Flags&INCONTACT)!=0)contact++;
   frameContacts=contact;frameAt=DateTime.UtcNow;frameErr=0;
   framePeak=Math.Max(framePeak,contact);
  }else{frameErr=Marshal.GetLastWin32Error();errors++;}
  if((pi.Flags&CANCELLED)!=0)kind="CANCELLED";
  model.Apply(kind,id,new Point(x,y));
  if(stage>=0&&stage<StageTotal) {
   if(kind=="DOWN")stageDown[stage]++;
   if(kind=="UP")stageUp[stage]++;
  }
  if(kind=="LEAVE"&&model.Active.ContainsKey(id)){
   model.Active.Remove(id);model.CaptureLost++;
   WriteEvent("UNEXPECTED_LEAVE_WHILE_DOWN",id,x,y,pi,detail,error,"NO_UP");
  }
  peak=Math.Max(peak,model.Active.Count);
  messages++;WriteEvent(kind,id,x,y,pi,detail,error==0?frameErr:error,"");
  m.Result=IntPtr.Zero;
 }
 void Finish(){
  if(finished)return;finished=true;timer.Stop();events.Flush();samples.Flush();
  string p=Path.Combine(folder,"SUMMARY.txt");
  using(var w=new StreamWriter(p,false,Encoding.UTF8)){
   w.WriteLine(TruthMode?
     "SL4A PHYSICAL TRUTH V3: OPERATOR-ANNOUNCED CONTACT STATES + OS POINTERS, NOT INSTRUMENTED FINGER MOTION":
     "SL4A WINDOWS V2 OBSERVER: FOREGROUND OS POINTERS, NOT PHYSICAL-SENSOR GROUND TRUTH");
   if(TruthMode) {
    w.WriteLine("Physical truth state labels are HUMAN KEY ANNOTATIONS, not a sensor measurement.");
    w.WriteLine("Keyboard response delays and state changes between keys are UNKNOWN.");
    w.WriteLine("X invalidates the latest interpretation without deleting original evidence; reinterpret invalid intervals.");
    w.WriteLine("Valid physical-state key marks: "+physical.Marks+"; Corrections: "+physical.Corrections);
   }
   w.WriteLine("Started UTC: "+begin.ToString("O")+"; finished "+Utc());
   w.WriteLine("Pointer events: "+messages+"; DOWN/UP: "+model.Down+"/"+model.Up);
   w.WriteLine("Duplicate DOWN: "+model.Duplicate+"; orphan UP: "+model.Orphan);
   w.WriteLine("Capture losses: "+model.CaptureLost+"; native pointer API failures: "+errors);
   w.WriteLine("Max message IDs: "+peak+"; max frame contacts: "+framePeak);
   w.WriteLine("Active at exit: "+(ActiveIds()==""?"NONE":ActiveIds()));
   for(int i=0;i<StageTotal;i++){
    w.WriteLine("");w.WriteLine(CurrentStep(i));
    w.WriteLine("Expected physical contacts while holding: "+(TruthMode?TruthExpected(i).ToString():(i==0?"1":"2")));
    w.WriteLine("Approx duration: "+(ticks[i]/10.0).ToString("F1")+" s");
    w.WriteLine("10Hz samples at message count >=2/1/0: "+two[i]+"/"+one[i]+"/"+(ticks[i]-two[i]-one[i]));
    w.WriteLine("Samples with native frame >=2: "+frameTwo[i]);
    w.WriteLine("Max message count in stage: "+max[i]);
    w.WriteLine("ID numbers observed: "+string.Join(" ",ids[i].OrderBy(x=>x)));
    w.WriteLine("Stage DOWN/UP events: "+stageDown[i]+" / "+stageUp[i]);
    w.WriteLine("Min/max two-ID distance (screen px): "+
       (minDist[i]==double.MaxValue?"N/A":minDist[i].ToString("F1"))+" / "+
       (minDist[i]==double.MaxValue?"N/A":maxDist[i].ToString("F1")));
    if(!TruthMode && i==2)w.WriteLine("Longest observed one-ID streak AFTER first two-ID frame: "+
       (longestOneRun[i]/10.0).ToString("F1")+" seconds at 10 Hz");
    w.WriteLine("M markers (operator confirmed two fingers physically down): "+marks[i]);
   }
   w.WriteLine("");w.WriteLine(TruthMode?"OPERATOR PHYSICAL STATE MARKERS:":"PHYSICAL TWO-FINGER M MARKERS:");
   foreach(string a in annotations)w.WriteLine("  "+a);
   w.WriteLine("");
   w.WriteLine("Important: one-count samples during finger placement/removal are NOT faults.");
   w.WriteLine("An M marker identifies when the operator confirmed two physical fingers.");
   w.WriteLine("Frame contacts reflect this WINDOW'S most recent input frame.");
   w.WriteLine("A device sending one contact per frame may report frame=1");
   w.WriteLine("even when the application has TWO active pointers: not an independent ground truth.");
   w.WriteLine("OS pointer IDs are NOT necessarily HID Contact IDs/HeatCore track IDs.");
   w.WriteLine("No driver/registry changes and no system-wide input capture.");
  }
  Console.WriteLine("Saved: "+folder);
  Console.WriteLine("Send SUMMARY.txt, samples.csv, events.csv for analysis.");
 }
 protected override void OnFormClosed(FormClosedEventArgs e){
  Finish();events.Dispose();samples.Dispose();timer.Dispose();base.OnFormClosed(e);
 }
 protected override void OnPaint(PaintEventArgs e){
  base.OnPaint(e);var g=e.Graphics;g.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
  int h=ClientSize.Height;
  using(var head=new Font("Segoe UI",21,FontStyle.Bold))
  using(var number=new Font("Segoe UI",67,FontStyle.Bold))
  using(var body=new Font("Segoe UI",17))
  using(var detail=new Font("Segoe UI",12))
  using(var white=new SolidBrush(Color.White))
  using(var dim=new SolidBrush(Color.FromArgb(169,189,211)))
  using(var green=new SolidBrush(Color.FromArgb(94,224,167)))
  using(var red=new SolidBrush(Color.FromArgb(255,142,111))){
   g.DrawString(TruthMode?"SL4A  •  PHYSICAL TRUTH V3":"SL4A  •  TWO-FINGER DIAGNOSTIC V2",head,white,26,18);
   if(stage<0)g.DrawString(TruthMode?"Press SPACE to begin. Read and perform ONLY the large instruction shown for each stage.":"SPACE starts. Lift after step 1; KEEP TWO FINGERS DOWN through steps 2-3.",body,white,30,85);
   else if(stage<StageTotal)g.DrawString(CurrentStep(stage),body,white,30,85);
   else g.DrawString("Finished.",body,white,30,85);
   g.DrawString(model.Active.Count.ToString(),number,
       (TruthMode ? (physical.PhysicalCount>=0 && physical.PhysicalCount!=model.Active.Count) : (stage>=1&&stage<StageTotal&&model.Active.Count<2))?red:green,29,143);
   g.DrawString("Active contact IDs from DOWN/UP",detail,dim,35,255);
   g.DrawString("Latest frame (may be serial): "+FCount(),body,white,30,302);
   g.DrawString("Active IDs: "+(ActiveIds()==""?"none":ActiveIds()),body,white,30,348);
   g.DrawString("Peak message IDs: "+peak+" | Frame peak: "+framePeak,detail,dim,30,394);
   if(TruthMode) {
    g.DrawString("Operator physically down: "+(physical.PhysicalCount<0?"UNKNOWN":physical.PhysicalCount.ToString()),body,red,30,440);
    if(stage>=0&&stage<StageTotal)g.DrawString(TruthKeyHelp(stage)+"   |   X = invalidate a mistaken marker",detail,white,30,478);
   }
   else if(stage>=1&&stage<StageTotal&&model.Active.Count<2)
    g.DrawString("BOTH FINGERS DOWN? Press M to mark missing detection!",body,red,30,440);
   g.DrawString((TruthMode?"Physical state key marks: ":"M markers: ")+annotations.Count,detail,dim,30,510);
   if(model.Active.Count>=2){
    Point[] p=model.Active.Values.Take(2).ToArray();
    double dx=p[0].X-p[1].X,dy=p[0].Y-p[1].Y;
    g.DrawString("Two-contact separation: "+Math.Sqrt(dx*dx+dy*dy).ToString("F0")+" px",
      body,white,30,523);
   }
   g.DrawString(TruthMode?
      "Perform only this stage's instruction | SPACE = next | X = correct mistake | ESC = save partial":
      "SPACE = next step     M = I physically have TWO fingers down     ESC = save/quit",
      detail,white,30,h-40);
   Color[] palette={Color.FromArgb(62,174,251),Color.FromArgb(247,198,82),
      Color.FromArgb(124,237,171),Color.FromArgb(238,141,203)};
   int k=0;
   foreach(var pair in model.Active.OrderBy(p=>p.Key)){
    Point point=PointToClient(pair.Value);Color color=palette[k++%palette.Length];
    using(var pen=new Pen(color,5))
    using(var fill=new SolidBrush(Color.FromArgb(105,color))){
     g.FillEllipse(fill,point.X-35,point.Y-35,70,70);
     g.DrawEllipse(pen,point.X-35,point.Y-35,70,70);
     g.DrawString(pair.Key.ToString(),detail,white,point.X+30,point.Y+25);
    }
   }
  }
 }
}
'@
Add-Type -TypeDefinition $src -ReferencedAssemblies 'System.Windows.Forms','System.Drawing' -ErrorAction Stop
if($SelfTest) {
    [PinchWindow]::TruthMode=[bool]$PhysicalTruthMode
    [TouchModel]::AssertSelfTest()
    [PhysicalTruthModel]::AssertSelfTest()
    if([IntPtr]::Size -eq 8) {
        $size=[TouchModel]::NativePointerSize()
        if($size -ne 96){throw "Win32 POINTER_INFO size wrong (expected 96, got $size)"}
        Write-Host "PASS: 64-bit Win32 POINTER_INFO is $size bytes"
    }
    Write-Host 'PASS: PowerShell parsing, embedded C# compilation, two-finger state transitions.'
    return
}
New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
if($PhysicalTruthMode) {Write-Host "EIGHT stages. Follow the large instruction shown for each stage. X invalidates a mistaken marker; SPACE advances."}
else {Write-Host "Four stages; SPACE advances, M marks two real fingers when displayed count is wrong."}
Write-Host "Results: $OutputFolder"
[PinchWindow]::TrySetDpiAware()
[System.Windows.Forms.Application]::EnableVisualStyles()
[PinchWindow]::TruthMode=[bool]$PhysicalTruthMode
$form=New-Object PinchWindow($OutputFolder)
try{[System.Windows.Forms.Application]::Run($form)}finally{$form.Dispose()}
