package app.jojo.nativevoice;

import java.text.Normalizer;
import java.util.Locale;

final class Policy {
    private static final String[] BLOCKED = {"paytm", "amazonpay", "flipkartpaylater", "binance", "trustwallet", "trustapp", "wallet",
        "phonepe", "googlepay", "gpay", "bhim", "cred", "metamask", "coinbase", "bybit", "bitget", "kucoin",
        "kraken", "coindcx", "wazirx", "coinswitch", "zerodha", "kite", "groww", "upstox", "angelone", "robinhood",
        "trading", "bank", "yono", "payment", "comgoogleandroidappsnbupaisauser", "comgoogleandroidappswalletnfcrel",
        "inorgnpciupiapp", "comdreamplugandroidapp", "बाइनेंस", "पेटीएम"};
    static boolean payment(String value) {
        String s=Normalizer.normalize(value==null?"":value,Normalizer.Form.NFKC).toLowerCase(Locale.ROOT);
        return java.util.regex.Pattern.compile("\\b(checkout|check out|payment|pay|place order|buy now|upi|cvv|otp|card number|credit card|debit card|expiry date|billing details)\\b|भुगतान|पेमेंट|खरीदें|ओटीपी").matcher(s).find();
    }
    static boolean install(String value){return java.util.regex.Pattern.compile("\\binstall\\b|इंस्टॉल|इंस्टाल",java.util.regex.Pattern.CASE_INSENSITIVE).matcher(value).find();}
    static boolean blocked(String value) {
        String s = Normalizer.normalize(value == null ? "" : value, Normalizer.Form.NFKC).toLowerCase(Locale.ROOT).replaceAll("[\\s_.:/\\-\\p{Cf}]", "");
        for (String word : BLOCKED) if (s.contains(word)) return true;
        return false;
    }
}
