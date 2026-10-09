package app.jojo.nativevoice;

import android.app.*;
import android.os.Bundle;
import android.content.Intent;
import android.text.InputType;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.util.*;

/** Owner authenticates with Android before adding/removing PINs. No reveal button. */
public class PinVaultActivity extends Activity {
    private boolean authenticated=false;
    @Override protected void onPause(){super.onPause();if(authenticated){authenticated=false;finish();}}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",false).apply();
        stopService(new Intent(this,VoiceService.class));
        KeyguardManager manager=getSystemService(KeyguardManager.class);
        Intent confirm=manager.createConfirmDeviceCredentialIntent("JoJo local PIN vault","Confirm ownership to manage saved PINs");
        if(confirm==null){Toast.makeText(this,"Set a device screen lock first",Toast.LENGTH_LONG).show();finish();return;}
        startActivityForResult(confirm,8);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request!=8||result!=RESULT_OK){finish();return;}
        authenticated=true;editor();
    }
    private void editor(){
        LinearLayout panel=new LinearLayout(this);panel.setOrientation(1);panel.setPadding(30,40,30,24);
        panel.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        TextView info=new TextView(this);info.setText("Local PIN vault · optional\nPIN stays on this phone, encrypted with Android Keystore. Never sent to AI, laptop or Firestore.\nVoice replay can fool speaker matching; enabling saved-PIN unlock weakens the protection of a manual PIN. Fingerprint-only and inaccessible PIN screens still need you.\nAfter reboot, first unlock manually. Listening is stopped while editing. Restart it yourself afterwards.");panel.addView(info);
        ArrayList<String> scopes=new ArrayList<>(),names=new ArrayList<>();scopes.add("device");names.add("This phone (System UI PIN)");
        for(android.content.pm.ResolveInfo app:getPackageManager().queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),0)){
            String pkg=app.activityInfo.packageName,name=app.loadLabel(getPackageManager()).toString();
            if(!Policy.blocked(pkg+" "+name)&&!pkg.equals(getPackageName())&&!scopes.contains(pkg)){scopes.add(pkg);names.add(name+" · "+pkg);}
        }
        Spinner select=new Spinner(this);select.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,names));panel.addView(select);
        EditText pin=new EditText(this);pin.setHint("PIN (4–16 digits)");pin.setSingleLine();pin.setSaveEnabled(false);pin.setLongClickable(false);
        pin.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        pin.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        pin.setImeOptions(EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING|EditorInfo.IME_ACTION_DONE);panel.addView(pin);
        Button save=new Button(this);save.setText("Enable saved-PIN unlock for this target");panel.addView(save);
        save.setOnClickListener(v->{
            if(!authenticated)return;
            int length=pin.length();if(length<4||length>16){Toast.makeText(this,"Use 4–16 digits",Toast.LENGTH_SHORT).show();return;}
            byte[] bytes=new byte[length];
            for(int i=0;i<length;i++){char c=pin.getText().charAt(i);if(c<'0'||c>'9'){Arrays.fill(bytes,(byte)0);return;}bytes[i]=(byte)c;}
            try{new PinVault(this).save(scopes.get(select.getSelectedItemPosition()),bytes);Toast.makeText(this,"Saved locally. PIN will not be displayed or spoken.",Toast.LENGTH_LONG).show();}
            catch(Exception e){Toast.makeText(this,"Vault save failed; no unlock enabled",Toast.LENGTH_LONG).show();}
            finally{Arrays.fill(bytes,(byte)0);pin.getText().clear();}
        });
        Button remove=new Button(this);remove.setText("Delete saved PIN / disable this target");panel.addView(remove);
        remove.setOnClickListener(v->{if(authenticated){new PinVault(this).remove(scopes.get(select.getSelectedItemPosition()));pin.getText().clear();Toast.makeText(this,"Saved PIN removed",Toast.LENGTH_SHORT).show();}});
        ScrollView scroll=new ScrollView(this);scroll.addView(panel);setContentView(scroll);
    }
}
