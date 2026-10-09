package app.jojo.nativevoice;

import android.content.Context;
import android.security.keystore.*;
import android.util.Base64;
import java.security.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.JSONObject;

/** Local-only, non-exportable Keystore key. No secret-returning IPC or network API. */
final class PinVault {
    private static final String ALIAS="jojo.local.pin.v1";
    private final Context context;
    PinVault(Context context){this.context=context;}
    private SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(!store.containsAlias(ALIAS)){
            KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).setRandomizedEncryptionRequired(true).build());
            generator.generateKey();
        }
        return (SecretKey)store.getKey(ALIAS,null);
    }
    private String identity(String scope) throws Exception {
        String pkg=scope.equals("device")?"com.android.systemui":scope;
        if(!scope.equals("device")&&Policy.blocked(scope))throw new SecurityException("Restricted app");
        android.content.pm.PackageInfo info=context.getPackageManager().getPackageInfo(pkg,android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES);
        byte[] cert=info.signingInfo.getApkContentsSigners()[0].toByteArray();
        return scope+":"+Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(cert),Base64.NO_WRAP);
    }
    boolean configured(String scope){return context.getSharedPreferences("pin_vault",0).contains(scope);}
    void save(String scope,byte[] pin) throws Exception {
        String identity=identity(scope);
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        cipher.updateAAD(identity.getBytes(StandardCharsets.UTF_8));
        JSONObject record=new JSONObject().put("identity",identity).put("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP))
            .put("ciphertext",Base64.encodeToString(cipher.doFinal(pin),Base64.NO_WRAP));
        if(!context.getSharedPreferences("pin_vault",0).edit().putString(scope,record.toString()).remove("blocked:"+scope).commit())throw new IllegalStateException("Save failed");
    }
    byte[] decrypt(String scope) throws Exception {
        JSONObject record=new JSONObject(context.getSharedPreferences("pin_vault",0).getString(scope,"{}"));
        String identity=identity(scope);
        if(!identity.equals(record.getString("identity")))throw new SecurityException("App identity changed");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(record.getString("iv"),Base64.NO_WRAP)));
        cipher.updateAAD(identity.getBytes(StandardCharsets.UTF_8));
        return cipher.doFinal(Base64.decode(record.getString("ciphertext"),Base64.NO_WRAP));
    }
    boolean reserve(String scope,String commandId){
        android.content.SharedPreferences p=context.getSharedPreferences("pin_vault",0);
        java.util.Set<String> used=new java.util.HashSet<>(p.getStringSet("used_commands",java.util.Collections.emptySet()));
        if(commandId.isEmpty()||p.getBoolean("blocked:"+scope,false)||used.contains(commandId))return false;
        if(used.size()>=64)used.clear();
        used.add(commandId);
        return p.edit().putBoolean("blocked:"+scope,true).putStringSet("used_commands",used).commit();
    }
    void verified(String scope){context.getSharedPreferences("pin_vault",0).edit().remove("blocked:"+scope).apply();}
    void remove(String scope){context.getSharedPreferences("pin_vault",0).edit().remove(scope).remove("blocked:"+scope).apply();}
}
