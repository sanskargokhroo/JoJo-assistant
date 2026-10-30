package app.jojo.nativevoice;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.widget.*;
import org.json.*;

/** Native, paired management. No secret is returned by the server or prefilled. */
public class JojoManagementActivity extends Activity {
    private LinearLayout content;
    private TextView status;
    private boolean closed=false;
    private final java.util.ArrayList<Switch> saving=new java.util.ArrayList<>();
    private int dp(int n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}
    private TextView text(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Color.WHITE);t.setPadding(0,dp(10),0,dp(8));content.addView(t);return t;}
    private Button button(String title,Runnable action){Button b=new Button(this);b.setText(title);b.setAllCaps(false);content.addView(b,new LinearLayout.LayoutParams(-1,dp(52)));b.setOnClickListener(v->action.run());return b;}
    private EditText input(String hint,boolean secret){EditText e=new EditText(this);e.setHint(hint);e.setHintTextColor(Color.LTGRAY);e.setTextColor(Color.WHITE);e.setSingleLine();if(secret)e.setInputType(129);content.addView(e);return e;}
    @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().setFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE,android.view.WindowManager.LayoutParams.FLAG_SECURE);
        content=new LinearLayout(this);content.setOrientation(1);content.setPadding(dp(20),dp(20),dp(20),dp(24));content.setBackgroundColor(Color.rgb(9,15,29));
        ScrollView scroll=new ScrollView(this);scroll.addView(content);setContentView(scroll);
        button("‹ Back to JoJo",this::finish);text("skills".equals(getIntent().getStringExtra("page"))?"Skills & plugins":"AI & memory",26);
        status=text("Connecting to your paired laptop…",14);load();
    }
    private interface Result{void accept(JSONObject value);}
    private void call(String route,JSONObject data,Result result){
        new Thread(()->{java.net.HttpURLConnection c=null;JSONObject response=null;String error="";
            try{c=(java.net.HttpURLConnection)new java.net.URL("http://127.0.0.1:8000/api/mobile/management"+route).openConnection();c.setConnectTimeout(4000);c.setReadTimeout(8000);
                c.setRequestProperty("X-JoJo-Key",getSharedPreferences("jojo",0).getString("key",""));
                if(data!=null){c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");try(java.io.OutputStream out=c.getOutputStream()){out.write(data.toString().getBytes("UTF-8"));}}
                int code=c.getResponseCode();if(code!=200)throw new java.io.IOException("Settings request failed ("+code+"). Check pairing and backend version.");
                java.io.ByteArrayOutputStream bytes=new java.io.ByteArrayOutputStream();try(java.io.InputStream in=c.getInputStream()){byte[] b=new byte[2048];int n;while((n=in.read(b))!=-1){bytes.write(b,0,n);if(bytes.size()>131072)throw new java.io.IOException("Response too large");}}
                response=new JSONObject(bytes.toString("UTF-8"));
            }catch(Exception e){error="Cannot save or load settings. Check USB and laptop connection.";}finally{if(c!=null)c.disconnect();}
            final JSONObject value=response;final String problem=error;runOnUiThread(()->{if(closed)return;if(value==null){status.setText(problem+" Reopen this page to refresh saved switches.");for(Switch toggle:saving)toggle.setEnabled(true);saving.clear();return;}result.accept(value);});
        },"JoJo settings").start();
    }
    private JSONObject field(String name,Object value){JSONObject o=new JSONObject();try{o.put(name,value);}catch(JSONException ignored){}return o;}
    private void load(){call("",null,data->{
        status.setText("Connected • private paired settings");
        if("skills".equals(getIntent().getStringExtra("page"))){
            text("Shared backend switches. Phone and PC start/stop remain separate.",14);
            JSONArray list=data.optJSONArray("skills");if(list==null)return;
            for(int i=0;i<list.length();i++){JSONObject skill=list.optJSONObject(i);if(skill==null)continue;String id=skill.optString("id");
                Switch toggle=new Switch(this);toggle.setText(skill.optString("name"));toggle.setTextColor(Color.WHITE);toggle.setMinHeight(dp(52));toggle.setChecked(skill.optBoolean("enabled"));content.addView(toggle);
                text(skill.optString("description"),12);
                if(id.equals("desktop")||id.equals("mobile")){toggle.setEnabled(false);continue;}
                toggle.setOnCheckedChangeListener((v,on)->{toggle.setEnabled(false);saving.add(toggle);status.setText("Saving…");call("/skills",field(id,on),r->{saving.remove(toggle);toggle.setEnabled(true);status.setText(r.optString("message"));});});
            }return;
        }
        text("Active: "+data.optString("provider")+" / "+data.optString("model"),16);
        text(data.optBoolean("key_configured")?"API key configured • hidden":"No active API key",14);
        Spinner provider=new Spinner(this);provider.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"gemini","openai","anthropic"}));content.addView(provider);
        String current=data.optString("provider");provider.setSelection(current.equals("openai")?1:current.equals("anthropic")?2:0);
        EditText model=input("Model ID",false);model.setText(data.optString("model"));EditText key=input("New API key (write-only)",true);
        button("Save model & key",()->{if(key.length()==0||model.length()==0){status.setText("Enter a model ID and new API key.");return;}
            JSONObject values=field("provider",provider.getSelectedItem().toString());try{values.put("model",model.getText().toString());values.put("api_key",key.getText().toString());}catch(JSONException ignored){}
            status.setText("Saving securely…");call("/model",values,r->{key.setText("");status.setText(r.optString("message"));});});
        text("Changes require a laptop backend restart. Firebase credentials are managed in PC Model & Firebase setup.",13);
        Switch memory=new Switch(this);memory.setText("Remember task outcomes");memory.setTextColor(Color.WHITE);memory.setMinHeight(dp(56));memory.setChecked(data.optBoolean("remember_tasks",true));content.addView(memory);
        memory.setOnCheckedChangeListener((v,on)->call("/memory",field("remember_tasks",on),r->status.setText(r.optString("message"))));
        text("Relevant outcomes help future tasks. Current screen and permissions are checked again; actions are never replayed automatically. Private sessions are not stored. Review or delete history in PC Memory & workspace.",13);
    });}
    @Override public void onDestroy(){closed=true;super.onDestroy();}
}
