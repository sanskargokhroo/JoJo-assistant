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
    private final android.os.Handler ui=new android.os.Handler(android.os.Looper.getMainLooper());
    private TextView connectionStatus, permissionStatus, lastReply;
    private boolean checking=false, destroyed=false;
    private final Runnable refresh=new Runnable(){public void run(){refreshStatus();ui.postDelayed(this,1500);}};
    private int dp(int n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}
    private android.graphics.drawable.GradientDrawable surface(int color,int radius){
        android.graphics.drawable.GradientDrawable d=new android.graphics.drawable.GradientDrawable();
        d.setColor(color);d.setCornerRadius(dp(radius));return d;
    }
    private TextView label(LinearLayout parent,String text,int size,int color){
        TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setTextColor(color);
        v.setPadding(0,dp(5),0,dp(5));parent.addView(v);return v;
    }
    private LinearLayout card(LinearLayout parent,String title,String subtitle){
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(18),dp(14),dp(18),dp(16));box.setBackground(surface(Color.rgb(20,30,48),20));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.topMargin=dp(16);parent.addView(box,lp);
        label(box,title,19,Color.WHITE).setTypeface(null,android.graphics.Typeface.BOLD);
        if(!subtitle.isEmpty())label(box,subtitle,13,Color.rgb(164,182,207));return box;
    }
    @Override public void onCreate(Bundle bundle){
        super.onCreate(bundle);
        getWindow().setStatusBarColor(Color.rgb(9,15,29));getWindow().setNavigationBarColor(Color.rgb(9,15,29));
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN|android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        LinearLayout panel=new LinearLayout(this);panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(20),dp(20),dp(20),dp(32));panel.setBackgroundColor(Color.rgb(9,15,29));
        panel.setFocusableInTouchMode(true);
        ImageView logo=new ImageView(this);logo.setImageResource(getResources().getIdentifier("jojo_icon","drawable",getPackageName()));
        logo.setContentDescription("JoJo logo");panel.addView(logo,new LinearLayout.LayoutParams(dp(64),dp(64)));
        label(panel,"JoJo",34,Color.WHITE).setTypeface(null,android.graphics.Typeface.BOLD);
        label(panel,"YOUR PHONE. YOUR ASSISTANT.",12,Color.rgb(98,229,216));
        label(panel,"Shared memory. Separate device controls.",15,Color.rgb(164,182,207));
        LinearLayout status=card(panel,"This phone","USB companion • laptop backend required");
        connectionStatus=label(status,"Tap Check connection to verify pairing.",14,Color.WHITE);
        permissionStatus=label(status,"",13,Color.rgb(164,182,207));
        button(status,"Check connection",this::checkConnection);
        LinearLayout controls=card(panel,"Voice controls","Say JoJo after starting. Stop affects this phone only.");
        button(controls,"Start listening",()->{
            if(getSharedPreferences("jojo",0).getString("key","").isEmpty()){
                Toast.makeText(this,"Save your pairing key first",Toast.LENGTH_LONG).show();return;
            }
            getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",true).apply();startListening(true);refreshStatus();
        });
        LinearLayout replyCard=card(panel,"Latest reply","Same selected laptop voice • no automatic voice substitution");
        lastReply=label(replyCard,"Your latest response appears here.",14,Color.WHITE);
        LinearLayout pairing=card(panel,"Connect your laptop","The same private key connects this phone to your JoJo memory.");
        EditText key=new EditText(this);key.setHint("Paste pairing key");key.setHintTextColor(Color.rgb(144,161,185));
        key.setTextColor(Color.WHITE);key.setSingleLine();key.setTextSize(14);
        key.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        key.setText(getSharedPreferences("jojo",0).getString("key",""));pairing.addView(key);
        button(pairing,"Save pairing",()->{
            String value=key.getText().toString().trim();
            if(!value.matches("[A-Za-z0-9_-]{30,100}")){Toast.makeText(this,"Paste the complete key from laptop Settings",Toast.LENGTH_LONG).show();return;}
            getSharedPreferences("jojo",0).edit().putString("key",value).apply();key.clearFocus();
            ((android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(key.getWindowToken(),0);
            checkConnection();
        });
        LinearLayout access=card(panel,"Permissions","You choose what JoJo can access. Screen control is needed for the edge glow and app actions.");
        button(access,"Enable screen control",()->startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button(access,"Phone app permissions",()->startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName()))));
        LinearLayout look=card(panel,"Appearance","Animated cyan, violet and pink edges. Center animation is off by default.");
        Switch centerToggle=new Switch(this);centerToggle.setText("Show center animation");centerToggle.setTextColor(Color.WHITE);centerToggle.setMinHeight(dp(48));
        centerToggle.setChecked(getSharedPreferences("jojo",0).getBoolean("overlay_center",false));look.addView(centerToggle);
        centerToggle.setOnCheckedChangeListener((b,v)->getSharedPreferences("jojo",0).edit().putBoolean("overlay_center",v).apply());
        LinearLayout local=card(panel,"On this device","Limited local tools work without the laptop. Full voice and AI need the USB backend.");
        button(local,"Open local essentials",()->startActivity(new Intent(this,JojoOfflineActivity.class)));
        LinearLayout advanced=card(panel,"Advanced settings","Optional notifications, background operation and account removal.");
        LinearLayout options=new LinearLayout(this);options.setOrientation(LinearLayout.VERTICAL);options.setVisibility(android.view.View.GONE);
        button(advanced,"Show / hide advanced",()->options.setVisibility(options.getVisibility()==android.view.View.VISIBLE?android.view.View.GONE:android.view.View.VISIBLE));advanced.addView(options);
        button(options,"Background battery settings",()->startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)));
        button(options,"Local encrypted PIN vault",()->startActivity(new Intent(this,PinVaultActivity.class)));
        EditText apps=new EditText(this);apps.setTextColor(Color.WHITE);apps.setHintTextColor(Color.LTGRAY);apps.setHint("Notification package allowlist");
        apps.setText(getSharedPreferences("jojo",0).getString("notification_apps","com.whatsapp"));options.addView(apps);
        Switch notifications=new Switch(this);notifications.setText("Notification summaries");notifications.setTextColor(Color.WHITE);notifications.setMinHeight(dp(48));
        notifications.setChecked(getSharedPreferences("jojo",0).getBoolean("notifications_enabled",false));options.addView(notifications);
        notifications.setOnCheckedChangeListener((b,v)->{
            getSharedPreferences("jojo",0).edit().putBoolean("notifications_enabled",v).putString("notification_apps",apps.getText().toString().trim()).apply();
            JojoNotificationService.clear();if(v)startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
        });
        button(options,"Clear notification buffer",()->JojoNotificationService.clear());
        button(options,"Uninstall from this phone",()->new android.app.AlertDialog.Builder(this).setTitle("Uninstall JoJo?")
            .setMessage("Android will ask before removing JoJo and its private phone data. Laptop memory and Firestore data are kept. Leave Keep app data unchecked to remove phone data.")
            .setNegativeButton("Cancel",null).setPositiveButton("Continue",(d,w)->{
                stopJoJo();if(ScreenService.instance!=null)ScreenService.instance.disableSelf();
                startActivity(new Intent(Intent.ACTION_UNINSTALL_PACKAGE,android.net.Uri.parse("package:"+getPackageName())));
            }).show());
        label(panel,"Phone Stop and laptop Deactivate are separate. Switching off the laptop or unplugging USB disconnects this companion. After reboot, use Resume JoJo in notifications.",12,Color.rgb(164,182,207));
        label(panel,"JoJo • Native Android companion",12,Color.rgb(98,229,216));
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(panel);
        LinearLayout screen=new LinearLayout(this);screen.setOrientation(LinearLayout.VERTICAL);screen.setBackgroundColor(Color.rgb(9,15,29));
        screen.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout footer=new LinearLayout(this);footer.setOrientation(LinearLayout.VERTICAL);footer.setPadding(dp(20),0,dp(20),dp(10));
        button(footer,"Stop phone assistant",()->{stopJoJo();refreshStatus();});screen.addView(footer);
        setContentView(screen);panel.requestFocus();refreshStatus();
    }
    private void refreshStatus(){
        if(permissionStatus==null)return;
        if(lastReply!=null){String reply=VoiceService.latestReply;String error=VoiceService.latestError;lastReply.setText((reply.isEmpty()?"Your latest response appears here.":reply)+(error.isEmpty()?"":"\n\n"+error));}
        boolean mic=checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED;
        permissionStatus.setText("Microphone: "+(mic?"allowed":"not allowed")+"  •  Screen control: "+(ScreenService.instance!=null?"on":"off")+"\nPhone listening: "+(VoiceService.isRunning()?"on":"off"));
    }
    private void checkConnection(){
        if(checking)return;
        String key=getSharedPreferences("jojo",0).getString("key","");
        if(key.isEmpty()){connectionStatus.setText("Not paired. Save your laptop pairing key below.");return;}
        checking=true;connectionStatus.setText("Checking USB connection…");
        new Thread(()->{
            String message;java.net.HttpURLConnection c=null;
            try{
                c=(java.net.HttpURLConnection)new java.net.URL("http://127.0.0.1:8000/api/mobile/status").openConnection();
                c.setConnectTimeout(4000);c.setReadTimeout(4000);c.setRequestProperty("X-JoJo-Key",key);
                int code=c.getResponseCode();
                if(code==401)message="Pairing key rejected. Copy the current key from laptop Settings.";
                else if(code==403)message="Mobile capability is disabled in laptop Skills.";
                else if(code==404)message="Laptop backend needs an update/restart.";
                else if(code!=200)message="Connection error ("+code+"). Try again.";
                else {
                    java.io.ByteArrayOutputStream bytes=new java.io.ByteArrayOutputStream();
                    try(java.io.InputStream in=c.getInputStream()){byte[] chunk=new byte[1024];int n;while((n=in.read(chunk))!=-1){bytes.write(chunk,0,n);if(bytes.size()>8192)throw new java.io.IOException("Unexpected response");}}
                    org.json.JSONObject result=new org.json.JSONObject(bytes.toString("UTF-8"));
                    message="Paired • USB connected\nLaptop assistant: "+(result.optBoolean("laptop_active")?"active":"deactivated; phone service ready");
                    if(!result.optBoolean("owner_enrolled"))message+="\nEnroll owner voice in laptop Settings before voice commands.";
                }
            }catch(Exception e){message="Laptop service unavailable. Check USB, unlock the phone and start the JoJo backend.";}
            finally{if(c!=null)c.disconnect();}
            final String text=message;ui.post(()->{checking=false;if(!destroyed){connectionStatus.setText(text);refreshStatus();}});
        },"JoJo connection check").start();
    }
    @Override protected void onPause(){ui.removeCallbacks(refresh);super.onPause();}
    @Override protected void onDestroy(){destroyed=true;ui.removeCallbacks(refresh);super.onDestroy();}
    @Override protected void onPostResume(){
        super.onPostResume();ui.removeCallbacks(refresh);ui.post(refresh);
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
        JojoNotificationService.clear();
        getSharedPreferences("jojo",0).edit().putBoolean("notifications_enabled",false).apply();
        getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",false).apply();
        VoiceService.stopNow();
        stopService(new Intent(this,VoiceService.class));
        getSystemService(android.app.NotificationManager.class).cancel(9);
        if(ScreenService.instance!=null){ScreenService.instance.clearInstall();ScreenService.instance.show("sleeping");}
        Toast.makeText(this,"JoJo stopped. Tap Start listening to resume.",Toast.LENGTH_LONG).show();
    }
    void button(LinearLayout panel,String text,Runnable action){
        Button b=new Button(this);b.setText(text);b.setAllCaps(false);b.setTextSize(15);b.setGravity(android.view.Gravity.CENTER);b.setMinHeight(dp(50));
        boolean primary=text.equals("Start listening");boolean stop=text.equals("Stop phone assistant");
        b.setTextColor(primary?Color.rgb(9,15,29):Color.WHITE);
        b.setBackground(surface(primary?Color.rgb(98,229,216):stop?Color.rgb(100,38,58):Color.rgb(37,51,74),12));
        b.setPadding(dp(12),dp(8),dp(12),dp(8));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.topMargin=dp(10);panel.addView(b,lp);
        b.setOnClickListener(v->{try{action.run();}catch(android.content.ActivityNotFoundException unavailable){Toast.makeText(this,"This settings screen is unavailable on your phone",Toast.LENGTH_LONG).show();}});
    }
}
