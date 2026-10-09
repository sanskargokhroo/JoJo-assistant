package app.jojo.nativevoice;

import android.app.*;
import android.content.Intent;
import android.os.*;
import android.speech.*;
import android.widget.*;
import java.util.*;

/** Standalone local essentials, gated by Android device authentication. */
public class JojoOfflineActivity extends Activity implements RecognitionListener {
    private boolean authenticated=false;
    private SpeechRecognizer recognizer;
    private TextView status;
    private EditText command;
    private final Map<String,String> apps=new LinkedHashMap<>();
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",false).apply();
        VoiceService.stopNow();stopService(new Intent(this,VoiceService.class));
        Intent confirm=getSystemService(KeyguardManager.class).createConfirmDeviceCredentialIntent("JoJo local essentials","Confirm ownership. These commands run on this phone without the laptop.");
        if(confirm==null){Toast.makeText(this,"Set a device screen lock first",Toast.LENGTH_LONG).show();finish();return;}
        startActivityForResult(confirm,18);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request!=18||result!=RESULT_OK){finish();return;}
        authenticated=true;build();
    }
    @Override protected void onPause(){super.onPause();if(authenticated){authenticated=false;finish();}}
    @Override protected void onDestroy(){if(recognizer!=null)recognizer.destroy();super.onDestroy();}
    private void build(){
        LinearLayout panel=new LinearLayout(this);panel.setOrientation(1);panel.setPadding(30,50,30,20);
        status=new TextView(this);status.setText("JoJo local essentials\nNo laptop or model API. Device authentication replaces voice matching in this explicit local mode.\nCommands: time, date, battery, lock phone, open <exact app name>, timer <minutes>.\nTap-to-talk needs Android 12+ and an installed on-device recognition service/language. Type if unavailable. Background wake listening is stopped.");panel.addView(status);
        command=new EditText(this);command.setHint("JoJo open Calculator");panel.addView(command);
        Button run=new Button(this);run.setText("Run local command");run.setOnClickListener(v->execute(command.getText().toString()));panel.addView(run);
        Button mic=new Button(this);mic.setText("Tap to speak locally");mic.setOnClickListener(v->listen());panel.addView(mic);
        for(android.content.pm.ResolveInfo app:getPackageManager().queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),0)){
            String name=app.loadLabel(getPackageManager()).toString(),pkg=app.activityInfo.packageName;
            if(!Policy.blocked(pkg+" "+name)&&!pkg.equals(getPackageName())){
                String label=name.toLowerCase(Locale.ROOT);
                // Duplicate labels must be selected by package, never guessed.
                if(apps.containsKey(label)){apps.put(label,"");}else apps.put(label,pkg);
                apps.put(pkg,pkg);
            }
        }
        ScrollView scroll=new ScrollView(this);scroll.addView(panel);setContentView(scroll);
    }
    private void execute(String raw){
        if(!authenticated||getSystemService(KeyguardManager.class).isDeviceLocked())return;
        String text=raw.trim().toLowerCase(Locale.ROOT).replaceFirst("^jojo[ ,:]*","");
        if(Policy.blocked(text)){status.setText("Restricted app/action. Please handle it manually.");return;}
        try{
            if(text.equals("time")||text.equals("date")){status.setText(java.text.DateFormat.getDateTimeInstance().format(new Date()));return;}
            if(text.equals("battery")){status.setText("Battery: "+getSystemService(BatteryManager.class).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)+"%");return;}
            if(text.equals("lock phone")){
                boolean ok=Build.VERSION.SDK_INT>=28&&ScreenService.instance!=null&&ScreenService.instance.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN);
                status.setText(ok?"Lock requested. Check the lock screen.":"Enable JoJo accessibility or use the power button.");return;
            }
            if(text.matches("timer [0-9]{1,3}")){
                int minutes=Integer.parseInt(text.substring(6));if(minutes<1||minutes>180){status.setText("Choose 1–180 minutes.");return;}
                startActivity(new Intent(android.provider.AlarmClock.ACTION_SET_TIMER).putExtra(android.provider.AlarmClock.EXTRA_LENGTH,minutes*60).putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI,false));return;
            }
            if(text.startsWith("open ")){
                String pkg=apps.get(text.substring(5).trim());
                if(pkg==null||pkg.isEmpty()){status.setText("App missing or label ambiguous. Use its exact installed package name.");return;}
                if(Policy.blocked(pkg))return;
                Intent launch=getPackageManager().getLaunchIntentForPackage(pkg);
                if(launch!=null){startActivity(launch);return;}
            }
            status.setText("Supported locally: time, date, battery, lock phone, open <app>, timer <minutes>. Advanced tasks need the paired assistant.");
        }catch(Exception error){status.setText("Action unavailable on this phone. Nothing was retried.");}
    }
    private void listen(){
        if(!authenticated)return;
        if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED){status.setText("Grant microphone permission from app settings, then reopen local essentials.");return;}
        if(Build.VERSION.SDK_INT<31||!SpeechRecognizer.isOnDeviceRecognitionAvailable(this)){status.setText("On-device speech unavailable. Type a local command; no cloud fallback is used.");return;}
        if(recognizer==null){recognizer=SpeechRecognizer.createOnDeviceSpeechRecognizer(this);recognizer.setRecognitionListener(this);}
        Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_LANGUAGE,"en-IN");
        try{recognizer.startListening(intent);}catch(Exception error){status.setText("Local microphone unavailable; type your command.");}
    }
    public void onResults(Bundle result){ArrayList<String> texts=result.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);if(texts!=null&&!texts.isEmpty()){command.setText(texts.get(0));status.setText("Review the recognized command, then tap Run. Voice alone does not execute it.");}}
    public void onError(int error){status.setText("Local recognition unavailable ("+error+"). Type a command or check installed speech languages.");}
    public void onReadyForSpeech(Bundle params){status.setText("JoJo listening locally…");}
    public void onBeginningOfSpeech(){} public void onRmsChanged(float value){} public void onBufferReceived(byte[] data){}
    public void onEndOfSpeech(){} public void onPartialResults(Bundle result){} public void onEvent(int type,Bundle data){}
}
