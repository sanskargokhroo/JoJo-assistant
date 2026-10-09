package app.jojo.nativevoice;

import android.content.Context;
import android.graphics.*;
import android.view.View;

final class AmbientView extends View {
    String status="listening";
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private Bitmap fog;
    private float[] angles,distances;
    private int[] pixels;
    private float fogScale;
    @Override protected void onSizeChanged(int w,int h,int oldW,int oldH){
        super.onSizeChanged(w,h,oldW,oldH);
        if(w<=0||h<=0)return;
        if(fog!=null)fog.recycle();
        // Same field as jojo_fog.py; bounded raster cost in portrait or landscape.
        int sw=Math.max(2,Math.round(w*240f/Math.max(w,h))),sh=Math.max(2,Math.round(h*240f/Math.max(w,h)));
        fog=Bitmap.createBitmap(sw,sh,Bitmap.Config.ARGB_8888);
        angles=new float[sw*sh];distances=new float[sw*sh];pixels=new int[sw*sh];
        fogScale=Math.max(.8f,Math.min(1.6f,h/1000f));
        for(int iy=0;iy<sh;iy++)for(int ix=0;ix<sw;ix++){
            float nx=ix/(float)(sw-1),ny=iy/(float)(sh-1);int p=iy*sw+ix;
            angles[p]=(float)Math.atan2(ny-.5,nx-.5);
            distances[p]=Math.min(Math.min(nx*w,(1-nx)*w),Math.min(ny*h,(1-ny)*h));
        }
    }
    private void drawFog(Canvas c,float t){
        if(fog==null)return;
        for(int i=0;i<pixels.length;i++){
            double a=angles[i],d=distances[i],s=fogScale;
            if(d>=185*s){pixels[i]=0;continue;}
            double swell=.5+.5*Math.sin(a*3-t*1.1+.65*Math.sin(a*5+t*.65));
            double depth=(65+65*swell)*s;
            double ripple=.78+.22*Math.sin(d/(21*s)-t*1.8+a*6);
            double alpha=(Math.exp(-Math.pow(d/depth,2)*2.5)*ripple*(135+40*swell)+45*Math.exp(-d/(8*s)))*Math.max(0,Math.min(1,(185*s-d)/(50*s)));
            double blend=.5+.5*Math.sin(a*2-t*.55+.5*Math.sin(a*4+t*.25)),pink=.5+.5*Math.sin(a*3+t*.45);
            pixels[i]=Color.argb((int)Math.min(220,alpha),(int)(65+100*blend+55*pink),(int)(100+120*(1-blend)),(int)(255-18*pink));
        }
        fog.setPixels(pixels,0,fog.getWidth(),0,0,fog.getWidth(),fog.getHeight());
        paint.setShader(null);paint.setAlpha(255);paint.setFilterBitmap(true);
        c.drawBitmap(fog,null,new RectF(0,0,getWidth(),getHeight()),paint);
    }
    AmbientView(Context c) { super(c); setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO); }
    @Override protected void onDraw(Canvas c) {
        float w=getWidth(),h=getHeight(),x=w/2,y=h/2,d=getResources().getDisplayMetrics().density,r=48*d;
        float t=android.os.SystemClock.uptimeMillis()/1000f;
        int[] colors={0xff53e5ed,0xff8778fa,0xfff779cd,0xff53e5ed};
        float speed=status.equals("speaking")?1.45f:status.equals("working")?1.15f:status.equals("thinking")?.85f:.65f;
        t*=speed;
        paint.setStyle(Paint.Style.FILL);
        drawFog(c,t);
        paint.setShader(null);paint.setStyle(Paint.Style.FILL);paint.setColor(0xf20d1529);c.drawCircle(x,y,r*1.35f,paint);
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(2*d);paint.setShader(new SweepGradient(x,y,colors,null));
        for(int j=0;j<7;j++) { Path p=new Path();for(int n=0;n<=100;n++){double a=n*Math.PI*2/100;float radius=r*(.8f+.12f*(float)Math.sin(3*a+t*2+j*.35)+.1f*(float)Math.cos(a*2-t+j*.4));float px=x+(float)Math.cos(a)*radius,py=y+(float)Math.sin(a)*radius;if(n==0)p.moveTo(px,py);else p.lineTo(px,py);}p.close();c.drawPath(p,paint);}
        paint.setShader(null);paint.setStyle(Paint.Style.FILL);paint.setColor(0xf210172a);c.drawRoundRect(x-135*d,y+88*d,x+135*d,y+128*d,20*d,20*d,paint);
        paint.setColor(Color.WHITE);paint.setTextAlign(Paint.Align.CENTER);paint.setTextSize(16*d);
        c.drawText(status.equals("access_denied")?"Aap mere boss nahi ho":"JoJo "+status+"…",x,y+114*d,paint);
        postInvalidateDelayed(33);
    }
}
