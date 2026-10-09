package app.jojo.nativevoice;

import android.app.*;
import android.content.*;
import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;

/** Android disallows a microphone FGS from boot. Ask for a visible user tap. */
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context,Intent intent){
        String action=intent.getAction();
        if(!Intent.ACTION_BOOT_COMPLETED.equals(action)&&!Intent.ACTION_MY_PACKAGE_REPLACED.equals(action))return;
        if(!context.getSharedPreferences("jojo",0).getBoolean("listen_enabled",false))return;
        if(Build.VERSION.SDK_INT>=33&&context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;
        NotificationManager manager=context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("resume","JoJo startup",NotificationManager.IMPORTANCE_DEFAULT));
        PendingIntent open=PendingIntent.getActivity(context,9,new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        manager.notify(9,new Notification.Builder(context,"resume").setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Resume JoJo listening").setContentText("Tap to enable the microphone after restart. Laptop connection required.")
            .setContentIntent(open).setAutoCancel(true).build());
    }
}
