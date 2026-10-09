package app.jojo.nativevoice;

import android.app.*;
import android.content.Intent;
import android.media.*;
import android.os.*;
import android.speech.tts.TextToSpeech;
import android.util.Base64;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.*;

public class VoiceService extends Service {
    private static volatile VoiceService instance;
    private volatile HttpURLConnection connection;
    static void stopNow(){
        VoiceService service=instance;
        if(service==null)return;
        service.running=false;
        JojoNotificationService.clear();
        service.session="";
        if(service.connection!=null){try{service.connection.disconnect();}catch(Exception ignored){}}
        AudioRecord audio=service.recorder;
        if(audio!=null){try{audio.stop();}catch(Exception ignored){}}
        if(service.tts!=null)service.tts.stop();
        if(service.worker!=null)service.worker.interrupt();
        if(ScreenService.instance!=null)ScreenService.instance.clearInstall();
        service.show("sleeping");
    }
    private volatile boolean running=false;
    private volatile AudioRecord recorder;
    private final Handler main=new Handler(Looper.getMainLooper());
    private TextToSpeech tts;
    private volatile boolean ttsReady=false;
    private String session="";
    private long lastActive=0;
    private Thread worker;
    private PowerManager.WakeLock listeningLock;
    private final Runnable renewListeningLock=new Runnable(){public void run(){
        if(running&&listeningLock!=null){listeningLock.acquire(10*60*1000L);main.postDelayed(this,5*60*1000L);}
    }};
    @Override public IBinder onBind(Intent i){return null;}
    @Override public int onStartCommand(Intent intent,int flags,int id){
        if(intent!=null&&"stop".equals(intent.getAction())){getSharedPreferences("jojo",0).edit().putBoolean("listen_enabled",false).apply();stopNow();stopSelf();return START_NOT_STICKY;}
        if(!getSharedPreferences("jojo",0).getBoolean("listen_enabled",false)){stopSelf();return START_NOT_STICKY;}
        if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED){stopSelf();return START_NOT_STICKY;}
        if(running)return START_STICKY;
        NotificationManager nm=getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("voice","JoJo voice",NotificationManager.IMPORTANCE_LOW));
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,VoiceService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(this,"voice").setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("JoJo · waiting for wake word")
            .setContentText("Microphone active. Tap Stop to end listening.").addAction(new Notification.Action.Builder(null,"Stop",stop).build()).setOngoing(true).build();
        try{startForeground(7,notification);}catch(SecurityException|IllegalStateException unavailable){stopSelf();return START_NOT_STICKY;}
        tts=new TextToSpeech(this,status->{if(status==TextToSpeech.SUCCESS){tts.setLanguage(Locale.forLanguageTag("hi-IN"));ttsReady=true;}});
        running=true;
        instance=this;
        listeningLock=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"JoJo:Listening");
        listeningLock.setReferenceCounted(false);renewListeningLock.run();
        worker=new Thread(this::listen,"JoJo voice");worker.start();return START_STICKY;
    }
    @Override public void onDestroy(){
        stopNow();instance=null;
        running=false;
        main.removeCallbacks(renewListeningLock);
        if(listeningLock!=null&&listeningLock.isHeld())listeningLock.release();
        AudioRecord active=recorder;if(active!=null){try{active.stop();}catch(Exception ignored){}}
        if(worker!=null)worker.interrupt();
        if(tts!=null){tts.stop();tts.shutdown();}show("sleeping");super.onDestroy();
    }
    private void show(String state){main.post(()->{if(ScreenService.instance!=null)ScreenService.instance.show(state);});}
    private <T>T onMain(Callable<T> callback) throws Exception {
        FutureTask<T> task=new FutureTask<>(callback);main.post(task);return task.get(4,TimeUnit.SECONDS);
    }
    private JSONObject screen() throws Exception {return onMain(()->{
        if(ScreenService.instance==null)throw new IllegalStateException("Enable screen control");return ScreenService.instance.snapshot();});}
    private void say(String text) throws Exception {
        if(text.isEmpty())return;show("speaking");
        if(!ttsReady){main.post(()->android.widget.Toast.makeText(this,text,android.widget.Toast.LENGTH_LONG).show());return;}
        onMain(()->tts.speak(text,TextToSpeech.QUEUE_FLUSH,null,"jojo"));
        Thread.sleep(300);long deadline=SystemClock.elapsedRealtime()+30000;
        while(running&&tts.isSpeaking()&&SystemClock.elapsedRealtime()<deadline)Thread.sleep(100);
        Thread.sleep(350);
    }
    private JSONObject post(String path,JSONObject input) throws Exception {
        android.content.SharedPreferences prefs=getSharedPreferences("jojo",0);
        String device=prefs.getString("device_id","");
        if(device.isEmpty()){device=java.util.UUID.randomUUID().toString();prefs.edit().putString("device_id",device).apply();}
        input.put("device_id",device);
        HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:8000/api/mobile/"+path).openConnection();
        connection=c;
        if(!running)throw new InterruptedException("JoJo stopped");
        c.setConnectTimeout(5000);c.setReadTimeout(45000);c.setRequestMethod("POST");c.setDoOutput(true);
        c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("X-JoJo-Key",getSharedPreferences("jojo",0).getString("key",""));
        try{try(OutputStream out=c.getOutputStream()){out.write(input.toString().getBytes(StandardCharsets.UTF_8));}
            if(c.getResponseCode()!=200)throw new IOException("Server "+c.getResponseCode());
            try(InputStream in=c.getInputStream();ByteArrayOutputStream body=new ByteArrayOutputStream()){
                byte[] buffer=new byte[4096];int count;
                while((count=in.read(buffer))!=-1){body.write(buffer,0,count);if(body.size()>200000)throw new IOException("Response too large");}
                return new JSONObject(body.toString("UTF-8"));
            }
        }finally{c.disconnect();connection=null;}
    }
    private void handle(byte[] pcm) throws Exception {
        JSONObject input=new JSONObject();input.put("session",session);input.put("audio",Base64.encodeToString(pcm,Base64.NO_WRAP));
        if(!session.isEmpty())show("thinking");
        JSONObject response=post("voice",input);
        for(int steps=0;running&&steps<25;steps++){
            String state=response.optString("state","sleeping");
            if(response.has("session")){session=response.getString("session");lastActive=SystemClock.elapsedRealtime();}
            if(state.equals("sleeping")){show(state);return;}
            if(state.equals("access_denied")){session="";say(response.optString("reply"));show("access_denied");Thread.sleep(2000);show("sleeping");return;}
            JSONObject action=response.optJSONObject("action");
            if(action==null||action.optString("type").equals("finish")){
                onMain(()->{if(ScreenService.instance!=null)ScreenService.instance.clearInstall();return null;});
                say(response.optString("reply"));show(response.optBoolean("sleep_after")?"sleeping":"listening");return;
            }
            show("working");final JSONObject next=action;
            String result=action.optString("type").equals("observe")?"Fresh observation requested":onMain(()->{if(!running||ScreenService.instance==null)return "failed: service stopped";return ScreenService.instance.execute(next);});
            Thread.sleep(action.optString("type").equals("wait")?3500:650);
            input=screen();input.put("session",session);input.put("result",result);
            if(action.optBoolean("notifications",false))input.put("notifications",JojoNotificationService.snapshot(this));
            response=post("step",input);
        }
    }
    private void listen(){
        while(running){
            AudioRecord audio=null;
            try{
                int size=Math.max(3200,AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT));
                audio=new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,size*4);
                recorder=audio;if(audio.getState()!=AudioRecord.STATE_INITIALIZED)throw new IOException("Microphone unavailable");audio.startRecording();
                short[] block=new short[800];ByteArrayOutputStream utterance=new ByteArrayOutputStream();
                java.util.ArrayDeque<byte[]> preRoll=new java.util.ArrayDeque<>();int quiet=0,voiced=0;boolean speaking=false;
                while(running){
                    int n=audio.read(block,0,block.length);if(n<=0)throw new IOException("Audio stream stopped");
                    if(!session.isEmpty()&&SystemClock.elapsedRealtime()-lastActive>90000){session="";show("sleeping");}
                    double sum=0;byte[] bytes=new byte[n*2];for(int i=0;i<n;i++){sum+=(double)block[i]*block[i];bytes[2*i]=(byte)block[i];bytes[2*i+1]=(byte)(block[i]>>8);}
                    boolean loud=Math.sqrt(sum/n)>350;
                    if(!speaking){preRoll.add(bytes);while(preRoll.size()>6)preRoll.removeFirst();if(!loud)continue;speaking=true;for(byte[] b:preRoll)utterance.write(b);preRoll.clear();voiced=1;continue;}
                    utterance.write(bytes);if(loud){quiet=0;voiced++;}else quiet++;
                    if(quiet>=22||utterance.size()>=640000){
                        if(voiced>=5){audio.stop();audio.release();audio=null;recorder=null;handle(utterance.toByteArray());break;}
                        utterance.reset();speaking=false;quiet=0;voiced=0;
                    }
                }
            }catch(Exception e){
                if(running){session="";show("sleeping");main.post(()->android.widget.Toast.makeText(this,"JoJo: "+e.getMessage(),android.widget.Toast.LENGTH_LONG).show());try{Thread.sleep(2000);}catch(InterruptedException ignored){}}
            }finally{if(audio!=null){try{audio.stop();}catch(Exception ignored){}audio.release();}recorder=null;}
        }
    }
}
