package app.jojo.nativevoice;
import android.app.KeyguardManager;
import android.app.Notification;
import android.content.Context;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.LinkedHashMap;

/** Opt-in allowlisted notification buffer. No notification reply actions. */
public class JojoNotificationService extends NotificationListenerService {
    private static final LinkedHashMap<String,JSONObject> recent=new LinkedHashMap<>();
    public static synchronized void clear(){recent.clear();}
    private boolean allowed(String pkg){
        if(!getSharedPreferences("jojo",0).getBoolean("listen_enabled",false)||!getSharedPreferences("jojo",0).getBoolean("notifications_enabled",false)||Policy.blocked(pkg))return false;
        for(String name:getSharedPreferences("jojo",0).getString("notification_apps","com.whatsapp").split(","))if(pkg.equals(name.trim()))return true;
        return false;
    }
    @Override public void onNotificationPosted(StatusBarNotification item){
        if(!allowed(item.getPackageName())||getSystemService(KeyguardManager.class).isDeviceLocked())return;
        Notification n=item.getNotification();if((n.flags&Notification.FLAG_GROUP_SUMMARY)!=0)return;
        String title=String.valueOf(n.extras.getCharSequence(Notification.EXTRA_TITLE,""));
        String text=String.valueOf(n.extras.getCharSequence(Notification.EXTRA_TEXT,""));
        if((title+" "+text).toLowerCase(java.util.Locale.ROOT).matches("(?s).*(\\botp\\b|one.time.password|verification.code|security.code|passcode|\\bpin\\b|password|payment|upi|cvv).*"))return;
        try{
            JSONObject value=new JSONObject().put("package",item.getPackageName()).put("title",title.substring(0,Math.min(title.length(),150)))
                .put("text",text.substring(0,Math.min(text.length(),700))).put("timestamp",item.getPostTime());
            synchronized(JojoNotificationService.class){recent.remove(item.getKey());recent.put(item.getKey(),value);
                while(recent.size()>40)recent.remove(recent.keySet().iterator().next());}
        }catch(Exception ignored){}
    }
    @Override public void onNotificationRemoved(StatusBarNotification item){synchronized(JojoNotificationService.class){recent.remove(item.getKey());}}
    @Override public void onListenerDisconnected(){clear();}
    public static synchronized String snapshot(Context context){
        if(!context.getSharedPreferences("jojo",0).getBoolean("notifications_enabled",false)||context.getSystemService(KeyguardManager.class).isDeviceLocked())return "";
        JSONArray result=new JSONArray();
        for(JSONObject item:recent.values())if(System.currentTimeMillis()-item.optLong("timestamp")<24*60*60*1000L)result.put(item);
        return result.toString();
    }
}
