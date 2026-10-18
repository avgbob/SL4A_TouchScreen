# SL4A Windows multi-touch observer: V2 diagnostic plus guided V4 physical truth.
# No driver/registry changes. V4 uses only SPACE to confirm the displayed state;
# V2 retains M to annotate two physical fingers when fewer than two are shown.
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
 public int PhysicalCount=-1; // UNKNOWN while the operator changes state
 public int Marks=0;
 public string Confirm(int count,string action) {
  if(count<0||count>2||String.IsNullOrWhiteSpace(action))throw new ArgumentException("bad guided marker");
  PhysicalCount=count;Marks++;return action;
 }
 public void BeginTransition(){PhysicalCount=-1;}
 public static void AssertSelfTest() {
  var p=new PhysicalTruthModel();
  if(p.PhysicalCount!=-1)throw new Exception("missing initial UNKNOWN state");
  if(p.Confirm(2,"BOTH_DOWN")!="BOTH_DOWN"||p.PhysicalCount!=2)throw new Exception("two-finger mark");
  p.BeginTransition();if(p.PhysicalCount!=-1)throw new Exception("transition must be unknown");
  if(p.Confirm(1,"LEFT_LIFTED")!="LEFT_LIFTED"||p.PhysicalCount!=1)throw new Exception("physical lift mark");
  if(p.Confirm(0,"BOTH_LIFTED")!="BOTH_LIFTED"||p.PhysicalCount!=0||p.Marks!=3)throw new Exception("guided marks");
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
  "REMOVE ALL FINGERS from the glass.",
  "HORIZONTAL: place TWO fingers far apart, side by side.",
  "Keep BOTH down and slowly bring them CLOSE side by side.",
  "Lift the LEFT finger only. Keep the RIGHT finger down.",
  "Keep only the RIGHT finger down.",
  "Return the LEFT finger close beside the RIGHT finger.",
  "Lift the RIGHT finger only. Keep the LEFT finger down.",
  "Keep only the LEFT finger down.",
  "Return the RIGHT finger close beside the LEFT finger.",
  "Keep BOTH down and separate them far apart side by side.",
  "REMOVE ALL FINGERS before the vertical trial.",
  "VERTICAL: place TWO fingers far apart, one above the other.",
  "Keep BOTH down, bring them CLOSE vertically, and use LIGHT pressure.",
  "Keep BOTH close and press a little MORE FIRMLY without moving.",
  "Lift the TOP finger only. Keep the BOTTOM finger down.",
  "Keep only the BOTTOM finger down.",
  "Return the TOP finger close above the BOTTOM finger.",
  "Keep BOTH down and separate them far apart vertically.",
  "REMOVE ALL FINGERS. This is the final step."
 };
 static readonly string[] TruthActions={
  "EMPTY_START","HORIZONTAL_TWO_APART","HORIZONTAL_CLOSE_BOTH_DOWN",
  "HORIZONTAL_LEFT_LIFTED","HORIZONTAL_RIGHT_ONLY","HORIZONTAL_LEFT_RETURNED",
  "HORIZONTAL_RIGHT_LIFTED","HORIZONTAL_LEFT_ONLY","HORIZONTAL_RIGHT_RETURNED",
  "HORIZONTAL_TWO_APART_AGAIN","EMPTY_BETWEEN_TRIALS","VERTICAL_TWO_APART",
  "VERTICAL_CLOSE_LIGHT","VERTICAL_CLOSE_FIRM","VERTICAL_TOP_LIFTED",
  "VERTICAL_BOTTOM_ONLY","VERTICAL_TOP_RETURNED","VERTICAL_TWO_APART_AGAIN","EMPTY_FINISH"
 };
 static readonly int[] TruthExpectedCounts={0,2,2,1,1,2,1,1,2,2,0,2,2,2,1,1,2,2,0};
 public static bool TruthMode=false;
 int StageTotal {get {return TruthMode?TruthSteps.Length:Steps.Length;}}
 string CurrentStep(int i){return TruthMode?TruthSteps[i]:Steps[i];}
 static int TruthExpected(int i) {
  return TruthExpectedCounts[i];
 }
 public static void AssertTruthProtocol() {
  if(TruthSteps.Length!=TruthActions.Length||TruthSteps.Length!=TruthExpectedCounts.Length)
   throw new Exception("guided protocol array length mismatch");
  if(TruthSteps.Length>MaxStages||TruthSteps.Length<10)throw new Exception("guided stage capacity");
  if(TruthExpectedCounts[0]!=0||TruthExpectedCounts[TruthExpectedCounts.Length-1]!=0)
   throw new Exception("guided protocol must begin and end empty");
  if(TruthActions.Distinct().Count()!=TruthActions.Length)throw new Exception("duplicate guided action");
  if(TruthExpectedCounts.Any(n=>n<0||n>2))throw new Exception("invalid guided count");
 }
 readonly TouchModel model=new TouchModel();
 readonly PhysicalTruthModel physical=new PhysicalTruthModel();
 readonly HashSet<Keys> heldKeys=new HashSet<Keys>();
 readonly StreamWriter events, samples;
 readonly Timer timer=new Timer();
 readonly string folder;
 const int MaxStages=24;
 const double GuidedHoldSeconds=2.0;
 readonly int[] ticks=new int[MaxStages],two=new int[MaxStages],one=new int[MaxStages],max=new int[MaxStages],marks=new int[MaxStages],frameTwo=new int[MaxStages];
 readonly int[] stageDown=new int[MaxStages],stageUp=new int[MaxStages],oneRun=new int[MaxStages],longestOneRun=new int[MaxStages];
 readonly double[] minDist=Enumerable.Repeat(double.MaxValue,MaxStages).ToArray(),maxDist=new double[MaxStages];
 readonly HashSet<uint>[] ids=Enumerable.Range(0,MaxStages).Select(i=>new HashSet<uint>()).ToArray();
 readonly List<string> annotations=new List<string>();
 int stage=-1,frameContacts=-1,frameErr,errors,peak,framePeak;
 long messages;
 DateTime frameAt=DateTime.MinValue,begin=DateTime.UtcNow;
 DateTime guidedHoldUntil=DateTime.MinValue;
 bool finished=false,guidedHolding=false;
 public PinchWindow(string target) {
  folder=target; Directory.CreateDirectory(target);
  events=new StreamWriter(Path.Combine(target,"events.csv"),false,Encoding.UTF8); events.AutoFlush=true;
  events.WriteLine("Utc,StopwatchTicks,Stage,Event,PointerId,MessageActive,FrameContacts,FrameAgeMs,PointerFlags,FrameId,X,Y,RawX,RawY,ContactL,ContactT,ContactR,ContactB,Pressure,Orientation,ApiError,ActiveIds,Note,OperatorPhysical");
  samples=new StreamWriter(Path.Combine(target,"samples.csv"),false,Encoding.UTF8);samples.AutoFlush=true;
  samples.WriteLine("Utc,Stage,Expected,MessageActive,FrameContacts,FrameAgeMs,ActiveIds,OperatorPhysical");
  Text=TruthMode?"SL4A GUIDED PHYSICAL TRUTH V4":"SL4A PINCH TEST V2";FormBorderStyle=FormBorderStyle.None;WindowState=FormWindowState.Maximized;
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
  if(!TruthMode && e.KeyCode==Keys.M){
   e.Handled=true;string a=Utc()+" stage="+(stage+1)+" observedMessage="+model.Active.Count+" observedFrame="+FCount();
   annotations.Add(a);if(stage>=0&&stage<StageTotal)marks[stage]++;
   WriteEvent("PHYSICAL_TWO_MARK",0,0,0,new PointerInfo(),null,0,"USER_SAYS_TWO_ON_GLASS");
   Invalidate();return;
  }
  if(e.KeyCode==Keys.Space){
   e.Handled=true;e.SuppressKeyPress=true;
   if(TruthMode){
    if(guidedHolding)return;
    if(stage<0){stage=0;physical.BeginTransition();WriteEvent("STAGE_START",0,0,0,new PointerInfo(),null,0,"STEP_1");Invalidate();return;}
    if(stage>=StageTotal)return;
    string action=physical.Confirm(TruthExpected(stage),TruthActions[stage]);
    WriteEvent("OPERATOR_CONFIRM_"+action,0,0,0,new PointerInfo(),null,0,"GUIDED_SPACE");
    annotations.Add(Utc()+" stage="+(stage+1)+" OPERATOR_CONFIRM_"+action+
                    " physical="+physical.PhysicalCount+
                    " windows="+model.Active.Count+" frame="+FCount());
    guidedHolding=true;guidedHoldUntil=DateTime.UtcNow.AddSeconds(GuidedHoldSeconds);
    Invalidate();return;
   }
   if(stage>=StageTotal-1){stage=StageTotal;Close();return;}
   stage++;WriteEvent("STAGE_START",0,0,0,new PointerInfo(),null,0,"STEP_"+(stage+1));
   Invalidate();
  }
 }
 void AdvanceGuidedStage(){
  if(!TruthMode||!guidedHolding)return;
  WriteEvent("GUIDED_HOLD_COMPLETE",0,0,0,new PointerInfo(),null,0,TruthActions[stage]);
  guidedHolding=false;stage++;physical.BeginTransition();
  WriteEvent("OPERATOR_TRANSITION_UNKNOWN",0,0,0,new PointerInfo(),null,0,"GUIDED_AUTO_ADVANCE");
  if(stage>=StageTotal){Close();return;}
  WriteEvent("STAGE_START",0,0,0,new PointerInfo(),null,0,"STEP_"+(stage+1));
  Invalidate();
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
  if(TruthMode&&guidedHolding&&DateTime.UtcNow>=guidedHoldUntil)AdvanceGuidedStage();
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
     "SL4A GUIDED PHYSICAL TRUTH V4: ONE-KEY OPERATOR-CONFIRMED STATES + OS POINTERS":
     "SL4A WINDOWS V2 OBSERVER: FOREGROUND OS POINTERS, NOT PHYSICAL-SENSOR GROUND TRUTH");
   if(TruthMode) {
    w.WriteLine("Physical truth labels are HUMAN SPACE confirmations, not instrumented finger motion.");
    w.WriteLine("Each confirmation is followed by an automatic 2-second labelled hold.");
    w.WriteLine("Transitions between stages are UNKNOWN and intentionally not labelled.");
    w.WriteLine("Valid guided physical-state confirmations: "+physical.Marks);
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
   w.WriteLine("");w.WriteLine(TruthMode?"GUIDED OPERATOR PHYSICAL STATE CONFIRMATIONS:":"PHYSICAL TWO-FINGER M MARKERS:");
   foreach(string a in annotations)w.WriteLine("  "+a);
   w.WriteLine("");
   w.WriteLine("Important: one-count samples during finger placement/removal are NOT faults.");
   w.WriteLine(TruthMode?"A guided marker records the displayed state when SPACE was pressed.":"An M marker identifies when the operator confirmed two physical fingers.");
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
   g.DrawString(TruthMode?"SL4A  •  GUIDED PHYSICAL TRUTH V4":"SL4A  •  TWO-FINGER DIAGNOSTIC V2",head,white,26,18);
   if(stage<0)g.DrawString(TruthMode?"Only SPACE is used. Press SPACE once to show STEP 1.":"SPACE starts. Lift after step 1; KEEP TWO FINGERS DOWN through steps 2-3.",body,white,30,85);
   else if(stage<StageTotal){
    g.DrawString("STEP "+(stage+1)+" OF "+StageTotal,detail,dim,30,82);
    g.DrawString(CurrentStep(stage),body,white,30,112);
    if(TruthMode)g.DrawString(guidedHolding?
      "CONFIRMED — HOLD STILL: "+Math.Max(0,(guidedHoldUntil-DateTime.UtcNow).TotalSeconds).ToString("F1")+" seconds":
      "DO THIS NOW — then press SPACE once",body,guidedHolding?green:red,30,155);
   }
   else g.DrawString("Finished.",body,white,30,85);
   int countY=TruthMode?190:143;
   g.DrawString(model.Active.Count.ToString(),number,
       (TruthMode ? (physical.PhysicalCount>=0 && physical.PhysicalCount!=model.Active.Count) : (stage>=1&&stage<StageTotal&&model.Active.Count<2))?red:green,29,countY);
   g.DrawString("Active contact IDs from DOWN/UP",detail,dim,35,TruthMode?300:255);
   g.DrawString("Latest frame (may be serial): "+FCount(),body,white,30,TruthMode?335:302);
   g.DrawString("Active IDs: "+(ActiveIds()==""?"none":ActiveIds()),body,white,30,TruthMode?375:348);
   g.DrawString("Peak message IDs: "+peak+" | Frame peak: "+framePeak,detail,dim,30,TruthMode?415:394);
   if(TruthMode) {
    g.DrawString("Confirmed physical count: "+(physical.PhysicalCount<0?"WAITING FOR SPACE":physical.PhysicalCount.ToString()),body,physical.PhysicalCount<0?dim:green,30,455);
    if(stage>=0&&stage<StageTotal)g.DrawString("Expected after SPACE: "+TruthExpected(stage)+" physical contact(s)",detail,white,30,493);
   }
   else if(stage>=1&&stage<StageTotal&&model.Active.Count<2)
    g.DrawString("BOTH FINGERS DOWN? Press M to mark missing detection!",body,red,30,440);
   g.DrawString((TruthMode?"Completed confirmations: ":"M markers: ")+annotations.Count,detail,dim,30,TruthMode?525:510);
   if(model.Active.Count>=2){
    Point[] p=model.Active.Values.Take(2).ToArray();
    double dx=p[0].X-p[1].X,dy=p[0].Y-p[1].Y;
    g.DrawString("Two-contact separation: "+Math.Sqrt(dx*dx+dy*dy).ToString("F0")+" px",
      body,white,30,TruthMode?550:523);
   }
   g.DrawString(TruthMode?
      "SPACE = confirm displayed state   |   Do not press letters   |   ESC = save partial":
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
    [PinchWindow]::AssertTruthProtocol()
    if([IntPtr]::Size -eq 8) {
        $size=[TouchModel]::NativePointerSize()
        if($size -ne 96){throw "Win32 POINTER_INFO size wrong (expected 96, got $size)"}
        Write-Host "PASS: 64-bit Win32 POINTER_INFO is $size bytes"
    }
    Write-Host 'PASS: PowerShell parsing, embedded C# compilation, two-finger state transitions.'
    return
}
New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
if($PhysicalTruthMode) {Write-Host "GUIDED V4: press SPACE to begin, then SPACE once after each displayed state is physically true. Do not press letter keys."}
else {Write-Host "Four stages; SPACE advances, M marks two real fingers when displayed count is wrong."}
Write-Host "Results: $OutputFolder"
[PinchWindow]::TrySetDpiAware()
[System.Windows.Forms.Application]::EnableVisualStyles()
[PinchWindow]::TruthMode=[bool]$PhysicalTruthMode
$form=New-Object PinchWindow($OutputFolder)
try{[System.Windows.Forms.Application]::Run($form)}finally{$form.Dispose()}
