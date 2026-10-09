package app.jojo.nativevoice;

import android.Manifest;
import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.provider.Settings;
import android.graphics.Color;
import android.widget.*;

public class MainActivity extends Activity {
    @Override public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL); panel.setPadding(36,60,36,24); panel.setBackgroundColor(Color.rgb(9,15,29));
        TextView heading = new TextView(this); heading.setText("JoJo\nYour native voice companion"); heading.setTextSize(27); heading.setTextColor(Color.WHITE); panel.addView(heading);
        TextView help = new TextView(this); help.setText("1. Pair using the key in laptop Settings.\n2. Connect USB and run adb reverse tcp:8000 tcp:8000.\n3. Enable JoJo accessibility and microphone.\n4. Start listening, then say JoJo.\n\nVoice and visible screen text go to your laptop; recognition and AI require internet. No audio is saved. Stop anytime from the notification."); help.setTextColor(Color.LTGRAY); help.setPadding(0,24,0,24); panel.addView(help);
        EditText key = new EditText(this); key.setHint("Pairing key from laptop Settings"); key.setSingleLine(); key.setText(getSharedPreferences("jojo",0).getString("key","")); panel.addView(key);
        button(panel,"Save pairing",()->{getSharedPreferences("jojo",0).edit().putString("key",key.getText().toString().trim()).apply(); Toast.makeText(this,"Pairing saved",Toast.LENGTH_SHORT).show();});
        button(panel,"Enable screen control",()->startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button(panel,"Start listening",()->{
            getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",true).apply();
            startListening(true);
        });
        button(panel,"Stop JoJo",()->stopJoJo());
        button(panel,"Uninstall JoJo",()->new android.app.AlertDialog.Builder(this)
            .setTitle("Uninstall JoJo from this phone?")
            .setMessage("Stops JoJo and opens Android's uninstall confirmation. Confirm there to remove the app and its private data, including the local PIN vault and pairing. Laptop and Firestore data stay until removed on the laptop. Downloaded APKs/backups outside the app are not deleted. If Android offers Keep app data, leave it unchecked.")
            .setNegativeButton("Cancel",null).setPositiveButton("Uninstall",(dialog,which)->{
                stopJoJo();
                if(ScreenService.instance!=null)ScreenService.instance.disableSelf();
                try{startActivity(new Intent(Intent.ACTION_UNINSTALL_PACKAGE,android.net.Uri.parse("package:"+getPackageName())));}
                catch(android.content.ActivityNotFoundException missing){startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName())));}
            }).show());
        button(panel,"Background battery settings",()->startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)));
        button(panel,"Local encrypted PIN vault",()->startActivity(new Intent(this,PinVaultActivity.class)));
        TextView startup=new TextView(this);startup.setTextColor(Color.LTGRAY);startup.setText("Listening stays on when you close this screen. After reboot, tap Resume JoJo in notifications. Force-stop requires reopening the app. Allow notifications and choose Unrestricted battery in system app settings if needed. Phone commands still require the laptop/USB connection.");panel.addView(startup);
        ScrollView scroll=new ScrollView(this);scroll.addView(panel);setContentView(scroll);
    }
    @Override protected void onPostResume(){
        super.onPostResume();
        if(getSharedPreferences("jojo",0).getBoolean("listen_enabled",false))startListening(false);
    }
    private void startListening(boolean request){
            if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) {
                if(request)requestPermissions(android.os.Build.VERSION.SDK_INT>=33?new String[]{Manifest.permission.RECORD_AUDIO,Manifest.permission.POST_NOTIFICATIONS}:new String[]{Manifest.permission.RECORD_AUDIO},1); return;
            }
            if(request&&android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},2);
            if(ScreenService.instance==null) { Toast.makeText(this,"Enable JoJo screen control first",Toast.LENGTH_LONG).show(); return; }
            if(getSharedPreferences("jojo",0).getString("key","").isEmpty()) { Toast.makeText(this,"Pair first",Toast.LENGTH_LONG).show(); return; }
            try{startForegroundService(new Intent(this,VoiceService.class));getSystemService(android.app.NotificationManager.class).cancel(9);}
            catch(SecurityException|IllegalStateException unavailable){Toast.makeText(this,"Cannot start microphone. Check app permissions, then tap Start listening.",Toast.LENGTH_LONG).show();return;}
            if(request)Toast.makeText(this,"Say JoJo after leaving this screen",Toast.LENGTH_LONG).show();
    }
    private void stopJoJo(){
        getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",false).apply();
        VoiceService.stopNow();
        stopService(new Intent(this,VoiceService.class));
        getSystemService(android.app.NotificationManager.class).cancel(9);
        if(ScreenService.instance!=null){ScreenService.instance.clearInstall();ScreenService.instance.show("sleeping");}
        Toast.makeText(this,"JoJo stopped. Tap Start listening to resume.",Toast.LENGTH_LONG).show();
    }
    void button(LinearLayout panel,String text,Runnable action) { Button b=new Button(this); b.setText(text); b.setOnClickListener(v->action.run()); panel.addView(b); }
}
