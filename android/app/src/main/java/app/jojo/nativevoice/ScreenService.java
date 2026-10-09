package app.jojo.nativevoice;

import android.accessibilityservice.AccessibilityService;
import android.graphics.PixelFormat;
import android.os.Bundle;
import android.view.*;
import android.view.accessibility.*;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import org.json.JSONObject;
import java.util.*;

public class ScreenService extends AccessibilityService {
    static volatile ScreenService instance;
    private final ArrayList<AccessibilityNodeInfo> nodes=new ArrayList<>();
    private AmbientView overlay;
    private WindowManager windows;
    private String observedPackage="";
    private String installPackage="",installName="";
    private long installDeadline=0;
    private JSONObject lastReplyAction;
    private final SavedPinUnlocker savedUnlock=new SavedPinUnlocker(this);
    void clearInstall(){installPackage="";installName="";installDeadline=0;}
    @Override public void onServiceConnected(){ instance=this;windows=(WindowManager)getSystemService(WINDOW_SERVICE); }
    @Override public void onAccessibilityEvent(AccessibilityEvent event){
        if(event.getPackageName()!=null && restrictedPackage(event.getPackageName().toString())) show("sleeping");
    }
    @Override public void onInterrupt(){ show("sleeping"); }
    @Override public void onDestroy(){ show("sleeping");instance=null;super.onDestroy(); }
    void show(String state){
        if(state.equals("sleeping")) { if(overlay!=null){windows.removeView(overlay);overlay=null;} return; }
        if(overlay==null){
            overlay=new AmbientView(this);
            WindowManager.LayoutParams p=new WindowManager.LayoutParams(-1,-1,WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE|WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,PixelFormat.TRANSLUCENT);
            windows.addView(overlay,p);
        }
        overlay.status=state;overlay.invalidate();
    }
    String currentPackage(){AccessibilityNodeInfo root=getRootInActiveWindow();return root==null?"":String.valueOf(root.getPackageName());}
    boolean restrictedPackage(String pkg){
        if(Policy.blocked(pkg))return true;
        try{return Policy.blocked(getPackageManager().getApplicationLabel(getPackageManager().getApplicationInfo(pkg,0)).toString());}
        catch(Exception e){return true;}
    }
    JSONObject snapshot() throws Exception {
        android.app.KeyguardManager keyguard=getSystemService(android.app.KeyguardManager.class);
        if(keyguard!=null&&(keyguard.isDeviceLocked()||keyguard.isKeyguardLocked())){
            nodes.clear();observedPackage="";
            return new JSONObject().put("device_locked",true).put("screen","").put("package","").put("saved_unlock_scope",new PinVault(this).configured("device")?"device":"");
        }
        nodes.clear(); AccessibilityNodeInfo root=getRootInActiveWindow(); observedPackage=root==null?"":String.valueOf(root.getPackageName());
        JSONObject value=new JSONObject();value.put("package",observedPackage);
        boolean auth=authScreen(root,0);
        value.put("unlock_verified_id",savedUnlock.verifiedId(false,auth,observedPackage));
        if(observedPackage.equals(getPackageName()))return value.put("screen","");
        String role="";
        if(observedPackage.equals("com.whatsapp")||observedPackage.equals("com.whatsapp.w4b"))role="whatsapp";
        else if(observedPackage.equals(android.provider.Telephony.Sms.getDefaultSmsPackage(this)))role="messages";
        else {android.telecom.TelecomManager telecom=getSystemService(android.telecom.TelecomManager.class);if(telecom!=null&&observedPackage.equals(telecom.getDefaultDialerPackage()))role="calls";}
        value.put("app_role",role);
        if(restrictedPackage(observedPackage)) {value.put("package","restricted payment app");value.put("screen","Restricted app; no screen content captured.");return value;}
        if(auth) {value.put("auth_required",true);value.put("saved_unlock_scope",new PinVault(this).configured(observedPackage)?observedPackage:"");value.put("screen","");return value;}
        if(sensitiveScreen(root,0)) {value.put("handoff",true);value.put("screen","Private payment or credential screen; content withheld.");return value;}
        StringBuilder text=new StringBuilder(); if(root!=null)walk(root,text,0);
        value.put("screen",text.toString());value.put("apps",installedApps());
        if(lastReplyAction!=null&&replyMatches(lastReplyAction,false)){
            boolean bubble=false,draft=false;
            for(AccessibilityNodeInfo n:nodes){
                if(String.valueOf(n.getText()).equals(lastReplyAction.optString("reply_body"))){
                    if(n.isEditable())draft=true;else bubble=true;
                }
            }
            if(bubble&&!draft)value.put("reply_verified_id",lastReplyAction.optString("reply_id"));
        }
        return value;
    }
    String label(AccessibilityNodeInfo node){return String.valueOf(node.getText()==null?"":node.getText())+" "+String.valueOf(node.getContentDescription()==null?"":node.getContentDescription());}
    boolean authScreen(AccessibilityNodeInfo node,int depth){
        if(node==null||depth>25)return false;
        if(node.isVisibleToUser()&&(node.isPassword()||label(node).toLowerCase(Locale.ROOT).matches(".*(unlock with fingerprint|use fingerprint|authenticate to unlock|whatsapp locked|फिंगरप्रिंट).*")))return true;
        for(int i=0;i<node.getChildCount();i++)if(authScreen(node.getChild(i),depth+1))return true;
        return false;
    }
    boolean sensitiveScreen(AccessibilityNodeInfo node,int depth){
        if(node==null||depth>25)return false;
        if(node.isVisibleToUser()){
            String s=label(node).toLowerCase(Locale.ROOT).trim();
            if(node.isPassword() || s.matches(".*(card number|cvv|expiry date|upi pin|enter otp|one.time password|unlock with fingerprint|use fingerprint|authenticate to unlock|whatsapp locked|कार्ड नंबर|ओटीपी|फिंगरप्रिंट).*"))return true;
            if(s.matches("(secure )?(checkout|payment|payment method|payment options|select payment method|भुगतान|पेमेंट)")||(node.isHeading()&&Policy.payment(s)))return true;
        }
        for(int i=0;i<node.getChildCount();i++)if(sensitiveScreen(node.getChild(i),depth+1))return true;
        return false;
    }
    boolean storeMatches(){
        if(installPackage.isEmpty()||android.os.SystemClock.elapsedRealtime()>installDeadline)return false;
        for(AccessibilityNodeInfo n:nodes){
            String text=label(n).trim();
            if(text.equalsIgnoreCase(installName)||text.equals(installPackage))return true;
        }return false;
    }
    boolean uniqueInstallTarget(AccessibilityNodeInfo target){
        int count=0;boolean found=false;
        for(AccessibilityNodeInfo n:nodes){
            if(n.refresh()&&n.isVisibleToUser()&&label(n).trim().matches("(?i)(install|इंस्टॉल|इंस्टाल)")){
                count++;if(n.equals(target))found=true;
            }
        }return count==1&&found;
    }
    Intent systemIntent(String app){
        switch(app){
            case "contacts":return new Intent(Intent.ACTION_VIEW,android.provider.ContactsContract.Contacts.CONTENT_URI);
            case "dialer":return new Intent(Intent.ACTION_DIAL);
            case "messages":return new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_MESSAGING);
            case "gallery":return new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_GALLERY);
            case "settings":return new Intent(android.provider.Settings.ACTION_SETTINGS);
            case "wifi":return new Intent(android.provider.Settings.ACTION_WIFI_SETTINGS);
            case "bluetooth":return new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS);
            case "display":return new Intent(android.provider.Settings.ACTION_DISPLAY_SETTINGS);
            default:throw new IllegalArgumentException("Unknown system app");
        }
    }
    void walk(AccessibilityNodeInfo node,StringBuilder text,int depth){
        if(node==null||depth>25||nodes.size()>=160||text.length()>14000)return;
        if(node.isVisibleToUser()){
            int id=nodes.size();nodes.add(node);
            String label=node.isPassword()?"[password field]":String.valueOf(node.getText()==null?"":node.getText())+" "+String.valueOf(node.getContentDescription()==null?"":node.getContentDescription());
            text.append(id).append(": ").append(label.substring(0,Math.min(1000,label.length()))).append(label.length()>1000?" [truncated]":"").append(" clickable=").append(node.isClickable()).append(" editable=").append(node.isEditable()).append(" scrollable=").append(node.isScrollable()).append('\n');
        }
        for(int i=0;i<node.getChildCount();i++)walk(node.getChild(i),text,depth+1);
    }
    String installedApps(){
        StringBuilder s=new StringBuilder();Intent launcher=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        for(ResolveInfo app:getPackageManager().queryIntentActivities(launcher,0)){
            String pkg=app.activityInfo.packageName,label=app.loadLabel(getPackageManager()).toString();
            if(!Policy.blocked(pkg+" "+label)&&s.length()<11000)s.append(label).append(" = ").append(pkg).append('\n');
        }return s.toString();
    }
    String execute(JSONObject action){
        try{
            String current=currentPackage();
            String type=action.optString("type");
            if(type.equals("prepare_unlock"))return savedUnlock.prepare(action);
            if(type.equals("unlock_saved"))return savedUnlock.execute(action);
            if(type.equals("lock_device")){
                clearInstall();lastReplyAction=null;show("sleeping");
                return performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)?"lock requested; verify device state":"failed: system rejected lock";
            }
            android.app.KeyguardManager keyguard=getSystemService(android.app.KeyguardManager.class);
            if(keyguard!=null&&(keyguard.isDeviceLocked()||keyguard.isKeyguardLocked()))return "handoff: device authentication required";
            if(type.equals("leave_app")){
                if(!current.equals(action.optString("package")))return "already outside requested app";
                return performGlobalAction(GLOBAL_ACTION_HOME)?"home sent; verify next screen":"failed: Home not accepted";
            }
            // Only the authenticated backend's owner-confirmation branch emits this action.
            if(type.equals("open_store")){
                String pkg=action.optString("package"),name=action.optString("name");
                if(!action.optBoolean("install_approved")||!pkg.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")||name.isEmpty()||Policy.blocked(pkg+" "+name))return "failed: install not approved";
                if(restrictedPackage(current)||sensitiveScreen(getRootInActiveWindow(),0))return "handoff: private foreground";
                clearInstall();
                startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("market://details?id="+pkg)).setPackage("com.android.vending").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                installPackage=pkg;installName=name;installDeadline=android.os.SystemClock.elapsedRealtime()+300000;
                return "Approved app Play Store page requested; verify exact app name before Install";
            }
            if(current.isEmpty()||!current.equals(observedPackage)) return "failed: foreground changed; obtain a new screen";
            if(restrictedPackage(current)||Policy.blocked(action.toString()))return "failed: restricted app or action";
            if(sensitiveScreen(getRootInActiveWindow(),0))return "handoff: payment or credential screen";
            if(type.equals("wait"))return "waiting; verify progress on next observation";
            if(type.equals("open_system")){
                startActivity(systemIntent(action.optString("app")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                return "System app requested; verify next screen";
            }
            if(type.equals("open")){
                String pkg=action.getString("package");
                String label=getPackageManager().getApplicationLabel(getPackageManager().getApplicationInfo(pkg,0)).toString();
                if(Policy.blocked(pkg+" "+label))return "failed: restricted app";
                Intent intent=getPackageManager().getLaunchIntentForPackage(pkg);
                if(intent==null)return "failed: app not installed or launchable";
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(intent);return "launch requested; verify next screen";
            }
            if(type.equals("back"))return performGlobalAction(GLOBAL_ACTION_BACK)?"back sent; verify next screen":"failed: back";
            int index=action.optInt("node",-1);
            if(index<0||index>=nodes.size())return "failed: node is not visible";
            AccessibilityNodeInfo node=nodes.get(index);
            if(!node.refresh()||!node.isVisibleToUser()||node.isPassword())return "failed: stale, hidden or password node";
            if(!current.equals(String.valueOf(node.getPackageName())))return "failed: node belongs to another app";
            if(Policy.blocked(String.valueOf(node.getText())+" "+node.getContentDescription()))return "failed: restricted target";
            if(Policy.payment(label(node)))return "handoff: payment target";
            if(action.optBoolean("read_only")&&!readOnlyTarget(action,node))return "failed: reading cannot send, call or modify chats";
            if(!action.optString("reply_id").isEmpty()){
                if(type.equals("click")&&label(node).toLowerCase(Locale.ROOT).matches(".*(voice message|audio message|sticker|record audio|वॉइस मैसेज).*"))return "failed: only dictated text reply authorized";
                if(type.equals("type")&&action.optString("text").equals(action.optString("reply_body"))&&!replyMatches(action,false))return "failed: reply recipient not verified";
            }
            // A Play Store page can only be controlled during this exact approved install.
            if(current.equals("com.android.vending") && (!storeMatches()||!type.equals("click")||!uniqueInstallTarget(node)))return "failed: store action needs exact approved app and one unambiguous free Install button";
            if(Policy.install(label(node))&&!current.equals("com.android.vending"))return "failed: installation allowed only through approved Play Store flow";
            boolean ok=false,replySubmitted=false;
            if(type.equals("click")){
                boolean sendTarget=isSend(node);
                for(int i=0;i<5&&node!=null;i++,node=node.getParent()){
                    if(Policy.blocked(label(node)))return "failed: restricted target";
                    if(Policy.payment(label(node)))return "handoff: payment target";
                    if(action.optBoolean("read_only")&&!readOnlyTarget(action,node)&&!(action.optString("read_mode").equals("calls")&&label(node).trim().isEmpty()))return "failed: read-only parent target";
                    sendTarget=sendTarget||isSend(node);
                    if(node.isClickable()){
                        if(!action.optString("reply_id").isEmpty()&&sendTarget){
                            if(!replyMatches(action,true))return "failed: reply recipient/body not verified";
                            android.content.SharedPreferences prefs=getSharedPreferences("jojo",0);
                            if(action.optString("reply_id").equals(prefs.getString("last_reply_attempt","")))return "failed: send already attempted; verify manually, no duplicate send";
                            if(!prefs.edit().putString("last_reply_attempt",action.optString("reply_id")).commit())return "failed: could not reserve send";
                            replySubmitted=true;
                        }
                        ok=node.performAction(AccessibilityNodeInfo.ACTION_CLICK);break;
                    }
                }
            }else if(type.equals("type")){
                Bundle args=new Bundle();args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,action.optString("text"));ok=node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,args);
            }else if(type.equals("scroll"))ok=node.performAction(action.optString("direction").equals("up")?AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD:AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
            if(ok&&current.equals("com.android.vending"))clearInstall();
            if(ok&&replySubmitted){lastReplyAction=new JSONObject(action.toString());return "reply send requested; verify next screen";}
            return ok?"action accepted; verify next screen":"failed: app did not accept action";
        }catch(Exception e){return "failed: "+e.getClass().getSimpleName();}
    }
    boolean isSend(AccessibilityNodeInfo node){return label(node).trim().matches("(?i)(send|send message|send sms|send text|भेजें|भेजो|भेजना)(\\s+.*)?");}
    boolean readOnlyTarget(JSONObject action,AccessibilityNodeInfo node){
        String s=label(node).trim().toLowerCase(Locale.ROOT),type=action.optString("type");
        if(type.equals("type"))return s.matches(".*(search|खोज|ढूंढ).*");
        if(!type.equals("click"))return true;
        if(action.optString("read_mode").equals("calls"))return s.matches("calls|recents|recent|missed|all|history|call history|हाल ही के|मिस्ड");
        return !java.util.regex.Pattern.compile("\\b(send|reply|call|delete|archive|forward)\\b|भेज|जवाब|कॉल|डिलीट").matcher(s).find();
    }
    boolean replyMatches(JSONObject action,boolean requireBody){
        if(!currentPackage().equals(action.optString("reply_package")))return false;
        boolean title=false,body=!requireBody;
        for(AccessibilityNodeInfo n:nodes){
            if(!n.refresh()||!n.isVisibleToUser())continue;
            String id=n.getViewIdResourceName()==null?"":n.getViewIdResourceName();
            if((n.isHeading()||id.matches(".*(conversation_contact_name|conversation_name|conversation_title|toolbar_title)$"))&&label(n).trim().equalsIgnoreCase(action.optString("reply_recipient")))title=true;
            if(n.isEditable()&&!n.isPassword()&&String.valueOf(n.getText()).equals(action.optString("reply_body")))body=true;
        }
        return title&&body;
    }
}
