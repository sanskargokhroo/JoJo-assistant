package app.jojo.nativevoice;

import android.os.Bundle;
import android.view.accessibility.AccessibilityNodeInfo;
import java.util.*;
import org.json.JSONObject;

/** One bounded attempt on the normal, visible PIN UI. No lock/biometric bypass. */
final class SavedPinUnlocker {
    private final ScreenService service;
    private String pendingScope="",pendingId="";
    SavedPinUnlocker(ScreenService service){this.service=service;}
    String prepare(JSONObject action){
        long age=System.currentTimeMillis()-action.optLong("issued_ms");
        if(action.optString("command_id").isEmpty()||age < -5000||age>20000)return "unlock unavailable: expired command";
        String scope=action.optString("scope");
        if(scope.equals("foreground"))scope=service.currentPackage();
        if(!new PinVault(service).configured(scope))return "unlock unavailable: local vault not configured";
        try{
            if(scope.equals("device"))service.startActivity(new android.content.Intent(service,UnlockPromptActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
            else if(!scope.equals(service.currentPackage())){
                if(service.restrictedPackage(scope))return "unlock unavailable: restricted app";
                android.content.Intent launch=service.getPackageManager().getLaunchIntentForPackage(scope);
                if(launch==null)return "unlock unavailable: app not launchable";
                service.startActivity(launch.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
            }
            return "unlock preparing: normal authentication screen requested";
        }catch(Exception e){return "unlock unavailable: show the PIN screen manually";}
    }
    private ArrayList<AccessibilityNodeInfo> visible(AccessibilityNodeInfo root){
        ArrayList<AccessibilityNodeInfo> nodes=new ArrayList<>();ArrayDeque<AccessibilityNodeInfo> todo=new ArrayDeque<>();
        if(root!=null)todo.add(root);
        for(int count=0;!todo.isEmpty()&&count<300;count++){
            AccessibilityNodeInfo n=todo.remove();if(n.isVisibleToUser())nodes.add(n);
            for(int i=0;i<n.getChildCount();i++){AccessibilityNodeInfo c=n.getChild(i);if(c!=null)todo.add(c);}
        }return nodes;
    }
    String execute(JSONObject action){
        String scope=action.optString("scope"),id=action.optString("command_id");byte[] pin=null;
        try{
            long age=System.currentTimeMillis()-action.optLong("issued_ms");
            if(id.isEmpty()||age < -5000||age>20000)return "unlock unavailable: expired command";
            boolean device=scope.equals("device");
            android.app.KeyguardManager keyguard=service.getSystemService(android.app.KeyguardManager.class);
            boolean locked=keyguard!=null&&(keyguard.isDeviceLocked()||keyguard.isKeyguardLocked());
            if(device&&!locked)return "unlock unnecessary: phone already unlocked";
            String pkg=service.currentPackage();
            if(scope.equals("foreground"))scope=pkg;
            if((device&&!pkg.equals("com.android.systemui"))||(!device&&(!pkg.equals(scope)||locked||service.restrictedPackage(pkg))))return "unlock unavailable: open the configured target's normal PIN screen";
            PinVault vault=new PinVault(service);
            if(!vault.configured(scope))return "unlock unavailable: configure the local PIN vault first";
            ArrayList<AccessibilityNodeInfo> nodes=visible(service.getRootInActiveWindow());
            boolean pinPage=device;ArrayList<AccessibilityNodeInfo> fields=new ArrayList<>();AccessibilityNodeInfo submit=null;
            HashMap<Integer,AccessibilityNodeInfo> digits=new HashMap<>();
            for(AccessibilityNodeInfo n:nodes){
                String label=service.label(n).trim().toLowerCase(Locale.ROOT),rid=n.getViewIdResourceName()==null?"":n.getViewIdResourceName();
                if(n.isPassword()&&n.getText()!=null&&n.getText().length()>0)return "unlock unavailable: PIN field already contains input; clear it manually";
                if(label.matches(".*(enter pin|unlock|app locked|पिन दर्ज|अनलॉक).*"))pinPage=true;
                if(Policy.payment(label))return "unlock unavailable: payment/OTP entry remains restricted";
                if(n.isPassword()&&n.isEditable()&&(!device||rid.matches(".*:(id)/(pinEntry|passwordEntry|pin_entry)$")))fields.add(n);
                if(device&&n.isClickable()&&rid.matches("com\\.android\\.systemui:id/key[0-9]"))digits.put(rid.charAt(rid.length()-1)-'0',n);
                if(n.isClickable()&&(label.matches("unlock|confirm|ok|done|अनलॉक|ठीक|पुष्टि")||rid.endsWith("/key_enter")))submit=n;
            }
            boolean keypad=device&&digits.size()==10;
            if(!pinPage||(fields.size()!=1&&!keypad))return "unlock unavailable: supported accessible PIN field not found; fingerprint-only/custom screens need manual authentication";
            if(!vault.reserve(scope,id))return "unlock unavailable: previous attempt unresolved; authenticate and re-save PIN locally before another attempt";
            pin=vault.decrypt(scope);
            pendingScope=scope;pendingId=id;
            if(keypad){
                for(byte digit:pin){
                    AccessibilityNodeInfo button=digits.get(digit-'0');
                    if(!service.currentPackage().equals(pkg)||button==null||!button.refresh()||!button.isVisibleToUser()||!button.performAction(AccessibilityNodeInfo.ACTION_CLICK))return "unlock unavailable: keypad interrupted; no retry";
                }
            }else{
                Bundle args=new Bundle();args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,new String(pin,java.nio.charset.StandardCharsets.US_ASCII));
                if(!fields.get(0).performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,args))return "unlock unavailable: system did not accept PIN input; no retry";
            }
            if(submit!=null&&submit.refresh()&&submit.isVisibleToUser()&&service.currentPackage().equals(pkg))submit.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            return "unlock submitted: verification pending; PIN not returned";
        }catch(Exception e){return "unlock unavailable: vault or system refused; no retry";}
        finally{if(pin!=null)Arrays.fill(pin,(byte)0);}
    }
    String verifiedId(boolean deviceLocked,boolean authRequired,String pkg){
        if(pendingId.isEmpty())return "";
        boolean verified=pendingScope.equals("device")?!deviceLocked:!deviceLocked&&!authRequired&&pendingScope.equals(pkg);
        if(!verified)return "";
        new PinVault(service).verified(pendingScope);String id=pendingId;pendingId="";pendingScope="";return id;
    }
}
