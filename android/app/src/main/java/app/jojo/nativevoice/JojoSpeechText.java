package app.jojo.nativevoice;

/** Speech-only cleanup; keep the original text for display and memory. */
final class JojoSpeechText {
    static String clean(String text){
        if(text==null)return "";
        text=text.replaceAll("\\[([^\\]]+)\\]\\([^)]*\\)","$1").replaceAll("https?://\\S+","");
        StringBuilder result=new StringBuilder();
        for(int offset=0;offset<text.length();){
            int cp=text.codePointAt(offset);offset+=Character.charCount(cp);
            if((cp>=0x1F000&&cp<=0x1FAFF)||(cp>=0x2600&&cp<=0x27BF)
                ||cp==0xFE0F||cp==0xFE0E||cp==0x200D||cp==0x20E3
                ||Character.getType(cp)==Character.OTHER_SYMBOL)continue;
            result.appendCodePoint(cp);
        }
        return result.toString().replaceAll("[`*#_]+","").replaceAll("\\s+"," ").trim();
    }
}
