package app.jojo.nativevoice;

import android.app.*;
import android.os.Bundle;
import android.view.WindowManager;

/** Shows the OS's own authentication UI; does not dismiss a secure lock itself. */
public class UnlockPromptActivity extends Activity {
    @Override public void onCreate(Bundle state){
        super.onCreate(state);setShowWhenLocked(true);setTurnScreenOn(true);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        getSystemService(KeyguardManager.class).requestDismissKeyguard(this,new KeyguardManager.KeyguardDismissCallback(){
            @Override public void onDismissSucceeded(){finish();}
            @Override public void onDismissCancelled(){finish();}
            @Override public void onDismissError(){finish();}
        });
        new android.os.Handler(getMainLooper()).postDelayed(()->finish(),15000);
    }
}
