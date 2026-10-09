"""Native, non-activating, click-through Windows voice overlay (no webview)."""
import colorsys
import ctypes
import math
import os
import sys
import time
import tkinter as tk

def overlay_state(state):
    if state.get('microphone_paused'):
        return None
    status = state.get('status', 'sleeping')
    if status == 'access_denied':
        return 'access_denied'
    if not state.get('active_session'):
        return None
    if status == 'speaking':
        return 'speaking'
    task = state.get('task') or {}
    if task.get('status') in ('queued', 'running'):
        return 'working' if task.get('events') else 'thinking'
    return status if status in ('listening', 'thinking', 'working', 'authenticating') else 'listening'

class AmbientOverlay:
    def __init__(self, root):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title('JoJo Ambient')
        self.window.overrideredirect('--preview' not in sys.argv)
        self.window.configure(bg='#010203')
        self.window.attributes('-topmost', True)
        if os.name == 'nt':
            self.window.attributes('-transparentcolor', '#010203')
        self.canvas = tk.Canvas(self.window, bg='#010203', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.status, self.visible, self.denied_until = None, False, 0
        self.last_denial = None
        self.surface = self.renderer = None
        self.root.bind('<Destroy>', self.destroy_surface, add='+')
        self.root.after(33, self.animate)

    def destroy_surface(self, event):
        if event.widget == self.root and self.surface:
            self.surface.close()
            self.surface = None

    def native_flags(self):
        if os.name != 'nt' or '--preview' in sys.argv:
            return
        u = ctypes.windll.user32
        u.GetParent.argtypes = [ctypes.c_void_p]
        u.GetParent.restype = ctypes.c_void_p
        hwnd = u.GetParent(self.window.winfo_id())
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        flags = u.GetWindowLongW(hwnd, -20)
        u.SetWindowLongW(hwnd, -20, flags | 0x20 | 0x80000 | 0x8000000 | 0x80)
        u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        u.SetWindowPos(hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0, 0x13)
        # Keep JoJo's own overlay out of screen capture where Windows supports it.
        u.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        if '--preview' not in sys.argv:
            u.SetWindowDisplayAffinity(hwnd, 0x11)

    def update(self, state):
        status = overlay_state(state)
        if status == 'access_denied':
            marker = state.get('timestamp')
            if marker != self.last_denial:
                self.denied_until, self.last_denial = time.monotonic() + 3, marker
            if time.monotonic() > self.denied_until:
                status = None
        self.status = status
        if status and not self.visible:
            self.width, self.height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            if os.name == 'nt':
                if not self.surface:
                    from jojo_fog import FogRenderer, LayeredSurface
                    self.renderer = FogRenderer(self.width, self.height)
                    self.surface = LayeredSurface(self.width, self.height, '--preview' in sys.argv)
            else:
                self.window.geometry(f'{self.width}x{self.height}+0+0')
                self.window.deiconify()
            self.visible = True
        elif not status and self.visible:
            if self.surface:
                self.surface.hide()
            self.window.withdraw()
            self.visible = False

    @staticmethod
    def color(hue, brightness=1):
        r, g, b = colorsys.hsv_to_rgb(hue % 1, .62, brightness)
        return '#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255))

    def animate(self):
        if not self.root.winfo_exists():
            return
        if self.visible and self.surface:
            began = time.monotonic()
            self.surface.present(self.renderer.render(began, self.status))
            # Account for render time rather than adding it to every frame interval.
            self.root.after(max(8, round(50-(time.monotonic()-began)*1000)), self.animate)
            return
        if self.visible:
            c, w, h, t = self.canvas, self.width, self.height, time.monotonic()
            c.delete('all')
            # Thin moving ribbons on all four display edges; no opaque fullscreen panel.
            for n in range(64):
                a, b = n/64, (n+1)/64
                hue = a*.8 + t*.055
                for thick, bright in ((16, .16), (9, .35), (3, 1)):
                    color = self.color(hue, bright)
                    c.create_line(a*w, 1, b*w+1, 1, fill=color, width=thick)
                    c.create_line(w-1, a*h, w-1, b*h+1, fill=self.color(hue+.2, bright), width=thick)
                    c.create_line(a*w, h-1, b*w+1, h-1, fill=self.color(hue+.4, bright), width=thick)
                    c.create_line(1, a*h, 1, b*h+1, fill=self.color(hue+.6, bright), width=thick)
            x, y = w/2, h/2
            scale = max(.8, min(1.6, h/1000))
            r = 58*scale
            c.create_oval(x-r*1.36, y-r*1.36, x+r*1.36, y+r*1.36, fill='#0b1024', outline='#263459', width=1)
            speed = 3 if self.status == 'speaking' else 1.4
            for ring in range(7):
                points = []
                for n in range(97):
                    angle = n/96*math.tau
                    radius = r*(.72 + .1*math.sin(angle*3 + t*speed + ring*.3)
                        + .12*math.cos(angle*2-t*1.5+ring*.45))
                    points.extend((x+math.cos(angle)*radius, y+math.sin(angle)*radius))
                c.create_line(*points, fill=self.color(.51+ring*.055+t*.03), width=2.2*scale, smooth=True)
            label = 'Aap mere boss nahi ho' if self.status == 'access_denied' else 'JoJo ' + self.status + '…'
            c.create_rectangle(x-140*scale, y+96*scale, x+140*scale, y+136*scale, fill='#10172a', outline='#283457')
            c.create_text(x, y+116*scale, text=label, fill='#f1f5ff', font=('Segoe UI', int(13*scale), 'bold'))
        self.root.after(33 if self.visible else 150, self.animate)
