"""Soft animated RGBA edge fog and a native per-pixel-alpha Windows surface."""
import ctypes
from ctypes import wintypes as W
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class FogRenderer:
    def __init__(self, width, height):
        self.width, self.height = width, height
        small_w = min(480, width)
        small_h = max(1, round(height * small_w / width))
        yy, xx = np.mgrid[:small_h, :small_w].astype(np.float32)
        self.x = xx / max(1, small_w - 1)
        self.y = yy / max(1, small_h - 1)
        self.distance = np.minimum(np.minimum(self.x * width, (1-self.x)*width),
                                   np.minimum(self.y * height, (1-self.y)*height))
        self.angle = np.arctan2(self.y-.5, self.x-.5)
        self.scale = max(.8, min(1.6, height/1000))
        try:
            self.font = ImageFont.truetype(os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts/segoeuib.ttf'), round(16*self.scale))
        except OSError:
            self.font = ImageFont.load_default()

    def render(self, phase, status='listening', center=True):
        speed = {'speaking': 1.45, 'working': 1.15, 'thinking': .85}.get(status, .65)
        t = phase * speed
        a, d = self.angle, self.distance
        # Broad, travelling clouds taper smoothly into the desktop. Actual alpha,
        # not dark-colored opaque bands or a transparent color key.
        swell = .5 + .5*np.sin(a*3 - t*1.1 + .65*np.sin(a*5+t*.65))
        depth = (65 + 65*swell) * self.scale
        ripple = .78 + .22*np.sin(d/(21*self.scale) - t*1.8 + a*6)
        fog = np.exp(-np.square(d/depth)*2.5) * ripple
        feather = np.clip((185*self.scale-d)/(50*self.scale), 0, 1)
        alpha = np.clip((fog*(135+40*swell) + 45*np.exp(-d/(8*self.scale)))*feather, 0, 220)
        blend = .5+.5*np.sin(a*2-t*.55 + .5*np.sin(a*4+t*.25))
        pink = .5+.5*np.sin(a*3+t*.45)
        rgb = np.empty((*d.shape, 4), dtype=np.uint8)
        rgb[:,:,0] = 65 + 100*blend + 55*pink
        rgb[:,:,1] = 100 + 120*(1-blend)
        rgb[:,:,2] = 255 - 18*pink
        rgb[:,:,3] = alpha
        frame = Image.fromarray(rgb).resize((self.width,self.height), Image.Resampling.BILINEAR)
        if center:
            self.draw_center(frame, t, status)
        return frame

    def draw_center(self, frame, phase, status):
        # Supersample the small center element independently of the edge field.
        scale = self.scale
        side = round(340*scale)
        art = Image.new('RGBA', (side*2, side*2))
        draw = ImageDraw.Draw(art)
        cx, cy, r = side, round(145*scale), 110*scale
        draw.ellipse((cx-r*1.2,cy-r*1.2,cx+r*1.2,cy+r*1.2),fill=(12,18,38,225))
        for ring in range(7):
            points=[]
            for n in range(129):
                a=n/128*math.tau
                radius=r*(.73+.12*math.sin(a*3+phase+ring*.35)+.1*math.cos(a*2-phase*.8+ring*.4))
                points.append((cx+math.cos(a)*radius,cy+math.sin(a)*radius))
            draw.line(points,fill=(80+ring*23,225-ring*20,255,240),width=max(2,round(3*scale)),joint='curve')
        art=art.resize((side,side),Image.Resampling.LANCZOS)
        x,y=(self.width-side)//2,round(self.height/2-72.5*scale)
        frame.alpha_composite(art,(x,y))
        draw=ImageDraw.Draw(frame)
        label='Aap mere boss nahi ho' if status=='access_denied' else 'JoJo '+status+'…'
        cx=self.width/2;cy=self.height/2+108*scale
        draw.rounded_rectangle((cx-146*scale,cy-23*scale,cx+146*scale,cy+23*scale),radius=22*scale,fill=(13,21,40,228))
        draw.text((cx,cy),label,font=self.font,fill=(242,246,255,255),anchor='mm')


class POINT(ctypes.Structure):
    _fields_=[('x',W.LONG),('y',W.LONG)]
class SIZE(ctypes.Structure):
    _fields_=[('cx',W.LONG),('cy',W.LONG)]
class BLEND(ctypes.Structure):
    _fields_=[('op',W.BYTE),('flags',W.BYTE),('alpha',W.BYTE),('format',W.BYTE)]
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),
              ('compression',W.DWORD),('image_size',W.DWORD),('xppm',W.LONG),('yppm',W.LONG),('used',W.DWORD),('important',W.DWORD)]


class LayeredSurface:
    def __init__(self,width,height,preview=False):
        self.width,self.height=width,height
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.gdi=ctypes.WinDLL('gdi32',use_last_error=True)
        u,g=self.user,self.gdi
        u.CreateWindowExW.argtypes=[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,ctypes.c_void_p]
        u.CreateWindowExW.restype=W.HWND
        u.GetDC.argtypes=[W.HWND];u.GetDC.restype=W.HDC
        u.ReleaseDC.argtypes=[W.HWND,W.HDC]
        u.ShowWindow.argtypes=[W.HWND,ctypes.c_int]
        u.DestroyWindow.argtypes=[W.HWND]
        u.SetWindowDisplayAffinity.argtypes=[W.HWND,W.DWORD]
        u.UpdateLayeredWindow.argtypes=[W.HWND,W.HDC,ctypes.POINTER(POINT),ctypes.POINTER(SIZE),W.HDC,ctypes.POINTER(POINT),W.DWORD,ctypes.POINTER(BLEND),W.DWORD]
        u.UpdateLayeredWindow.restype=W.BOOL
        g.CreateCompatibleDC.argtypes=[W.HDC];g.CreateCompatibleDC.restype=W.HDC
        g.CreateDIBSection.argtypes=[W.HDC,ctypes.c_void_p,W.UINT,ctypes.POINTER(ctypes.c_void_p),W.HANDLE,W.DWORD];g.CreateDIBSection.restype=W.HBITMAP
        g.SelectObject.argtypes=[W.HDC,W.HGDIOBJ];g.SelectObject.restype=W.HGDIOBJ
        g.DeleteObject.argtypes=[W.HGDIOBJ];g.DeleteDC.argtypes=[W.HDC]
        flags=0x80000|0x20|0x8000000|0x8|(0x40000 if preview else 0x80)
        self.hwnd=u.CreateWindowExW(flags,'Static','JoJo Ambient',0x80000000,0,0,width,height,None,None,None,None)
        if not self.hwnd:raise ctypes.WinError(ctypes.get_last_error())
        self.screen=u.GetDC(None);self.dc=g.CreateCompatibleDC(self.screen)
        info=BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER),width,-height,1,32,0,width*height*4,0,0,0,0)
        self.bits=ctypes.c_void_p()
        self.bitmap=g.CreateDIBSection(self.screen,ctypes.byref(info),0,ctypes.byref(self.bits),None,0)
        if not self.bitmap:raise ctypes.WinError(ctypes.get_last_error())
        self.old=g.SelectObject(self.dc,self.bitmap)
        if not preview:u.SetWindowDisplayAffinity(self.hwnd,0x11)

    def present(self,frame):
        data=np.asarray(frame,dtype=np.uint8)
        out=np.empty_like(data)
        alpha=data[:,:,3].astype(np.uint16)
        for dest,src in ((0,2),(1,1),(2,0)):
            out[:,:,dest]=(data[:,:,src].astype(np.uint16)*alpha//255).astype(np.uint8)
        out[:,:,3]=data[:,:,3]
        raw=out.tobytes();ctypes.memmove(self.bits,raw,len(raw))
        ok=self.user.UpdateLayeredWindow(self.hwnd,self.screen,ctypes.byref(POINT(0,0)),ctypes.byref(SIZE(self.width,self.height)),
            self.dc,ctypes.byref(POINT(0,0)),0,ctypes.byref(BLEND(0,0,255,1)),2)
        if not ok:raise ctypes.WinError(ctypes.get_last_error())
        self.user.ShowWindow(self.hwnd,4)  # SW_SHOWNOACTIVATE

    def hide(self):
        self.user.ShowWindow(self.hwnd,0)

    def close(self):
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd);self.hwnd=None
            self.gdi.SelectObject(self.dc,self.old);self.gdi.DeleteObject(self.bitmap)
            self.gdi.DeleteDC(self.dc);self.user.ReleaseDC(None,self.screen)
