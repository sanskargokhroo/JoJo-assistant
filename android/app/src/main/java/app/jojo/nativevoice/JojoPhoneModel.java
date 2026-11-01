package app.jojo.nativevoice;

import android.content.Context;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Scanner;

final class JojoPhoneModel {
    private static JSONObject workflows;

    private static synchronized String procedure(Context context,String command) throws Exception {
        if(workflows==null){
            int id=context.getResources().getIdentifier("jojo_workflows","raw",context.getPackageName());
            try(InputStream in=context.getResources().openRawResource(id);
                Scanner reader=new Scanner(in,"UTF-8").useDelimiter("\\A")){
                workflows=new JSONObject(reader.next());
            }
        }
        String name=command.split("\\s+",2)[0].substring(1).replaceFirst("^jojo:","");
        for(String prefix:new String[]{"","command/","workflow/","agent/","skill/"}){
            if(workflows.has(prefix+name))return workflows.getString(prefix+name);
        }
        throw new IllegalArgumentException("Unknown workflow. Try /jojo:plan or /jojo:python-review.");
    }

    static String ask(Context context,String task,String model,String key) throws Exception {
        if(!model.matches("[a-zA-Z0-9._-]+"))throw new IllegalArgumentException("Enter a valid Gemini model ID.");
        String instructions="You are JoJo running on the user's Android phone ("+android.os.Build.MODEL+
            "). Answer in the user's language. Work with the supplied text. You cannot access laptop files or perform device actions in this response.";
        if(task.startsWith("/"))instructions+="\nUse this workflow as a reference:\n"+procedure(context,task);
        JSONObject body=new JSONObject().put("systemInstruction",content(instructions))
            .put("contents",new JSONArray().put(content(task)));
        HttpsURLConnection c=(HttpsURLConnection)new URL("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent").openConnection();
        try{
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(90000);
            c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");
            c.setRequestProperty("x-goog-api-key",key);
            try(java.io.OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}
            int code=c.getResponseCode();
            if(code!=200)return "Phone AI request failed ("+code+"). Check your model, API key and quota.";
            try(Scanner reader=new Scanner(c.getInputStream(),"UTF-8").useDelimiter("\\A")){
                JSONArray parts=new JSONObject(reader.next()).getJSONArray("candidates").getJSONObject(0).getJSONObject("content").getJSONArray("parts");
                StringBuilder reply=new StringBuilder();
                for(int i=0;i<parts.length();i++)if(!parts.getJSONObject(i).optBoolean("thought"))reply.append(parts.getJSONObject(i).optString("text"));
                return reply.length()==0?"The model returned no text.":reply.toString();
            }
        }finally{c.disconnect();}
    }

    private static JSONObject content(String text) throws Exception {
        return new JSONObject().put("parts",new JSONArray().put(new JSONObject().put("text",text)));
    }
}
