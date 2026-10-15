"""Build a Windows setup/launcher EXE from audited source and a clean stdlib runtime.

Third-party packages and voice models are downloaded by the existing setup wizard.
No account, site-packages, voice profile, logs or personal database is bundled.
"""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import zipfile
from jojo_release import files, audit, export

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'jojo_release/windows'
CS = r'''
using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Windows.Forms;
using System.Threading.Tasks;

class JoJoSetup {
    static string Root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","JoJo");
    static string PayloadHash = "__HASH__";
    static string Q(string s) { return "\"" + s.Replace("\"","") + "\""; }
    static Stream Payload() { return Assembly.GetExecutingAssembly().GetManifestResourceStream("jojo.payload"); }
    static void Verify() {
        using(var stream=Payload()) using(var sha=SHA256.Create()) {
            var digest=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
            if(digest!=PayloadHash) throw new Exception("Installer payload verification failed.");
        }
    }
    static void CheckPath(string path,string root) {
        string p=Path.GetFullPath(path);
        if(!p.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
            throw new Exception("Unsafe archive path.");
        var parent=new DirectoryInfo(Path.GetDirectoryName(p));
        while(parent!=null) {
            if(parent.Exists && (parent.Attributes & FileAttributes.ReparsePoint)!=0)
                throw new Exception("Installation through a junction/symlink is not allowed.");
            parent=parent.Parent;
        }
        if(File.Exists(p) && (File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)
            throw new Exception("Linked destination file is not allowed.");
    }
    static void Extract(string root) {
        Verify();
        root=Path.GetFullPath(root);
        using(var stream=Payload()) using(var zip=new ZipArchive(stream,ZipArchiveMode.Read)) {
            foreach(var item in zip.Entries) {
                var path=Path.GetFullPath(Path.Combine(root,item.FullName.Replace('/',Path.DirectorySeparatorChar)));
                CheckPath(path,root);
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using(var input=item.Open()) using(var output=File.Create(path)) input.CopyTo(output);
            }
        }
    }
    static void Shortcut(string folder) {
        Directory.CreateDirectory(folder);
        var type=Type.GetTypeFromProgID("WScript.Shell");
        var shell=Activator.CreateInstance(type);
        var shortcut=type.InvokeMember("CreateShortcut",BindingFlags.InvokeMethod,null,shell,new object[]{Path.Combine(folder,"JoJo.lnk")});
        var t=shortcut.GetType();
        t.InvokeMember("TargetPath",BindingFlags.SetProperty,null,shortcut,new object[]{Path.Combine(Root,"JoJo.exe")});
        t.InvokeMember("WorkingDirectory",BindingFlags.SetProperty,null,shortcut,new object[]{Root});
        t.InvokeMember("Hotkey",BindingFlags.SetProperty,null,shortcut,new object[]{"CTRL+ALT+J"});
        t.InvokeMember("Save",BindingFlags.InvokeMethod,null,shortcut,new object[]{});
    }
    static void Launch(bool setup,bool cli) {
        string python=Path.Combine(Root,".venv","Scripts",cli?"python.exe":"pythonw.exe");
        if(!File.Exists(python)) {
            python=Path.Combine(Root,"runtime",cli?"python.exe":"pythonw.exe");
            setup=true;
        }
        if(!File.Exists(python)) throw new Exception("Install JoJo first.");
        var script=Path.Combine(Root,setup?"jojo_install.py":"jojo_start.py");
        var args=Q(script)+(setup?(cli?" --cli":" --gui"):" --no-autostart");
        var proc=Process.Start(new ProcessStartInfo(python,args){WorkingDirectory=Root,UseShellExecute=false,CreateNoWindow=!cli});
        if(cli)proc.WaitForExit();
    }
    [STAThread] static int Main(string[] args) {
        try {
            if(args.Length>0 && args[0]=="--verify"){Verify();Console.WriteLine("JoJo payload SHA256 verified.");return 0;}
            if(args.Length==2 && args[0]=="--extract-only"){Extract(args[1]);Console.WriteLine("Extracted verified payload.");return 0;}
            if(args.Length>0 && args[0]=="--cli"){Launch(true,true);return 0;}
            if(string.Equals(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location),Root,StringComparison.OrdinalIgnoreCase) && args.Length==0){
                Launch(false,false);return 0;
            }
            Application.EnableVisualStyles();
            var form=new Form(){Text="JoJo Setup",Width=610,Height=390,StartPosition=FormStartPosition.CenterScreen};
            var label=new Label(){Left=22,Top=20,Width=550,Height=150,Text=
                "JoJo — Windows desktop assistant\r\n\r\nInstalls Python and clean JoJo source for your Windows account.\r\nThe setup wizard downloads dependencies and the voice model.\r\nUse your own AI key; Firebase is optional. No accounts are included.\r\n\r\nLocation: "+Root};
            var status=new Label(){Left=22,Top=280,Width=550,Height=55,Text="Internet is required for dependency setup. This build is unsigned."};
            var install=new Button(){Text="Install / update",Left=22,Top=180,Width=165,Height=36};
            var open=new Button(){Text="Open dashboard",Left=200,Top=180,Width=165,Height=36};
            var setup=new Button(){Text="Account setup",Left=378,Top=180,Width=165,Height=36};
            var cli=new Button(){Text="CLI setup",Left=22,Top=230,Width=165,Height=36};
            install.Click+=async delegate {
                install.Enabled=false;open.Enabled=false;setup.Enabled=false;cli.Enabled=false;
                status.Text="Verifying and extracting clean source and Python...";
                try {
                    await Task.Run(()=>Extract(Root));
                    var exe=Path.Combine(Root,"JoJo.exe");
                    if(!string.Equals(exe,Assembly.GetExecutingAssembly().Location,StringComparison.OrdinalIgnoreCase))
                        File.Copy(Assembly.GetExecutingAssembly().Location,exe,true);
                    Shortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"JoJo"));
                    status.Text="Installed. Complete dependency and account setup in the new window.";
                    Launch(true,false);
                } catch(Exception error){status.Text=error.Message;}
                finally{install.Enabled=true;open.Enabled=true;setup.Enabled=true;cli.Enabled=true;}
            };
            open.Click+=delegate {try{Launch(false,false);}catch(Exception e){status.Text=e.Message;}};
            setup.Click+=delegate {try{Launch(true,false);}catch(Exception e){status.Text=e.Message;}};
            cli.Click+=delegate {Task.Run(()=>{try{Launch(true,true);}catch(Exception e){form.BeginInvoke((Action)(()=>status.Text=e.Message));}});};
            form.Controls.AddRange(new Control[]{label,status,install,open,setup,cli});
            Application.Run(form);return 0;
        } catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}
    }
}
'''

def build():
    if sys.version_info[:2] != (3,14) or __import__('struct').calcsize('P') != 8:
        raise RuntimeError('Build with CPython 3.14 x64.')
    selected=files()
    issues=audit(selected)
    if issues:raise RuntimeError('Source audit failed: '+str(issues))
    source=export(selected)
    OUT.mkdir(parents=True,exist_ok=True)
    payload=OUT/'jojo_payload.zip'
    runtime=Path(sys.base_prefix)
    allowed_top={'python.exe','pythonw.exe','python3.dll','python314.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt','COPYING'}
    with zipfile.ZipFile(payload,'w',zipfile.ZIP_DEFLATED) as z:
        with zipfile.ZipFile(source) as clean:
            for name in clean.namelist():
                z.writestr(name.removeprefix('JoJo/'),clean.read(name))
        excluded={'site-packages','__pycache__','test','tests','idle_test'}
        for base,dirs,names in os.walk(runtime):
            directory=Path(base)
            dirs[:]=[name for name in dirs if name not in excluded and not (directory/name).is_symlink()
                     and (directory!=runtime or name in ('Lib','DLLs','tcl','include','libs'))]
            for name in sorted(names):
                path=directory/name
                if path.is_symlink():continue
                rel=path.relative_to(runtime)
                if directory==runtime and name not in allowed_top:continue
                if path.suffix in ('.pyc','.pyo'):continue
                z.write(path,'runtime/'+rel.as_posix())
    digest=hashlib.sha256(payload.read_bytes()).hexdigest()
    code=OUT/'jojo_setup.cs'
    code.write_text(CS.replace('__HASH__',digest),encoding='utf-8')
    compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    exe=OUT/'JoJo-Setup.exe'
    subprocess.run([str(compiler),'/nologo','/target:exe','/platform:x64','/out:'+str(exe),
        '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
        '/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',
        '/resource:'+str(payload)+',jojo.payload',str(code)],check=True)
    print('Installer:',exe)
    print('SHA256:',hashlib.sha256(exe.read_bytes()).hexdigest())

if __name__=='__main__':build()
