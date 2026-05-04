import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk  # 콤보박스 스크롤을 위한 표준 라이브러리 추가
from tkinter import filedialog
import keyboard
import winsound
import threading
import requests
import json
import os
import pystray
import io
from PIL import Image, ImageDraw, ImageGrab

# Pygame 초기화 및 환영 메시지 숨기기
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
pygame.mixer.init()

# 테마 설정
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "timer_config.json"

class ModernTimerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("스마트 쿨타임 봇 (Discord Ver.)")
        self.geometry("420x780") 
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self.is_running = False
        self.is_alarm_state = False
        self.time_left = 0
        self.total_time = 0
        self.alarm_time = 0
        
        self.overlay_window = None
        self.red_bg = None
        
        self.target_key = "f9"
        self._drag_data = {"x": 0, "y": 0}
        self._resize_data = {}
        self._is_resizing = False
        self._resize_mode = ""
        self.RESIZE_MARGIN = 15
        self.MIN_SIZE = 100

        self.setup_ttk_style() # 다크 테마 콤보박스 스타일 초기화
        self.setup_tray_icon()
        self.load_config()
        self.setup_ui()

    def setup_ttk_style(self):
        """표준 콤보박스를 CustomTkinter 다크 테마에 맞게 커스텀"""
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        
        style.configure("Dark.TCombobox",
                        fieldbackground="#343638",
                        background="#2b2b2b",
                        foreground="white",
                        arrowcolor="white",
                        bordercolor="#1a1a1a",
                        insertcolor="white")
        
        # 드롭다운 리스트 박스(펼쳐졌을 때의 창) 디자인 설정
        self.option_add('*TCombobox*Listbox.background', '#343638')
        self.option_add('*TCombobox*Listbox.foreground', 'white')
        self.option_add('*TCombobox*Listbox.selectBackground', '#1f538d')
        self.option_add('*TCombobox*Listbox.selectForeground', 'white')
        self.option_add('*TCombobox*Listbox.font', 'Helvetica 11')

    def setup_tray_icon(self):
        image = Image.new('RGB', (64, 64), color=(30, 30, 30))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), outline=(0, 255, 255), width=5)
        menu = pystray.Menu(pystray.MenuItem("설정 열기", self.show_from_tray), pystray.MenuItem("종료", self.quit_app))
        self.tray_icon = pystray.Icon("TimerBot", image, "스마트 쿨타임 봇", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def load_config(self):
        self.config = {
            "key": "f9", "total_min": "2", "total_sec": "0", "alarm_min": "0", "alarm_sec": "10", 
            "show_overlay": True, "screen_fx": True, "sound_fx": True, "volume": 0.5, "mp3_path": "",
            "dc_enable": False, "dc_screen": False, "discord_webhook": "",
            "overlay_w": 160, "overlay_h": 160, "overlay_x": 100, "overlay_y": 100
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: self.config.update(json.load(f))
            except: pass
        self.target_key = self.config["key"]

    def save_config(self):
        with open(CONFIG_FILE, "w") as f: json.dump(self.config, f)

    def setup_ui(self):
        self.title_label = ctk.CTkLabel(self, text="타이머 상세 설정", font=("Helvetica", 24, "bold"))
        self.title_label.pack(pady=(20, 15))
        
        # 1. 단축키
        key_frame = ctk.CTkFrame(self, fg_color="transparent")
        key_frame.pack(fill="x", padx=25, pady=5)
        ctk.CTkLabel(key_frame, text="단축키 설정:", font=("Helvetica", 14, "bold")).pack(side="left")
        self.key_btn = ctk.CTkButton(key_frame, text=f"[{self.target_key}] 단축키 변경", width=120, command=self.wait_for_key)
        self.key_btn.pack(side="right")
        
        # 2. 컴팩트 드롭다운 시간 설정 (사이드바 적용)
        time_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        time_frame.pack(fill="x", padx=25, pady=10, ipadx=5, ipady=5)
        
        self.total_min_var = ctk.StringVar(value=f"{self.config['total_min']}분")
        self.total_sec_var = ctk.StringVar(value=f"{self.config['total_sec']}초")
        self.create_combo_time_input(time_frame, "총 쿨타임 시간:", self.total_min_var, self.total_sec_var, suffix_m="분", suffix_s="초")
        
        self.alarm_min_var = ctk.StringVar(value=f"{self.config['alarm_min']}분")
        self.alarm_sec_var = ctk.StringVar(value=f"{self.config['alarm_sec']}초")
        self.create_combo_time_input(time_frame, "미리 알림 시점:", self.alarm_min_var, self.alarm_sec_var, suffix_m="분", suffix_s="초")

        # 3. 알림 효과 및 MP3 설정
        fx_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        fx_frame.pack(fill="x", padx=25, pady=5, ipadx=5, ipady=5)
        
        sw_row = ctk.CTkFrame(fx_frame, fg_color="transparent")
        sw_row.pack(fill="x", padx=10, pady=(10, 5))
        
        self.show_overlay_var = ctk.BooleanVar(value=self.config["show_overlay"])
        self.screen_fx_var = ctk.BooleanVar(value=self.config.get("screen_fx", True))
        self.sound_fx_var = ctk.BooleanVar(value=self.config.get("sound_fx", True))
        
        sw_font = ("Helvetica", 12, "bold")
        ctk.CTkSwitch(sw_row, text="시계 띄우기", variable=self.show_overlay_var, font=sw_font, command=self.toggle_overlay).pack(side="left")
        ctk.CTkSwitch(sw_row, text="화면 붉게", variable=self.screen_fx_var, font=sw_font).pack(side="left", padx=10)
        ctk.CTkSwitch(sw_row, text="MP3 소리", variable=self.sound_fx_var, font=sw_font).pack(side="left")

        vol_row = ctk.CTkFrame(fx_frame, fg_color="transparent")
        vol_row.pack(fill="x", padx=10, pady=(5, 5))
        ctk.CTkLabel(vol_row, text="볼륨 조절:", font=("Helvetica", 12)).pack(side="left")
        self.volume_slider = ctk.CTkSlider(vol_row, from_=0.0, to=1.0, command=self.on_volume_change)
        self.volume_slider.set(self.config.get("volume", 0.5))
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=10)

        mp3_row = ctk.CTkFrame(fx_frame, fg_color="transparent")
        mp3_row.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkLabel(mp3_row, text="소리 파일:", font=("Helvetica", 12)).pack(side="left")
        
        self.mp3_path_var = ctk.StringVar(value=self.config.get("mp3_path", ""))
        self.mp3_entry = ctk.CTkEntry(mp3_row, textvariable=self.mp3_path_var, width=190, state="readonly")
        self.mp3_entry.pack(side="left", padx=10)
        ctk.CTkButton(mp3_row, text="찾아보기", width=60, font=("Helvetica", 12, "bold"), command=self.browse_mp3).pack(side="left")

        # 4. 디스코드 설정
        dc_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        dc_frame.pack(fill="x", padx=25, pady=15, ipadx=5, ipady=5)
        
        switch_frame = ctk.CTkFrame(dc_frame, fg_color="transparent")
        switch_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        self.dc_enable_var = ctk.BooleanVar(value=self.config["dc_enable"])
        ctk.CTkSwitch(switch_frame, text="디스코드 알림", font=("Helvetica", 13, "bold"), variable=self.dc_enable_var).pack(side="left")
        
        self.dc_screen_var = ctk.BooleanVar(value=self.config["dc_screen"])
        ctk.CTkSwitch(switch_frame, text="화면 스샷 포함", font=("Helvetica", 13, "bold"), variable=self.dc_screen_var).pack(side="right")
        
        self.dc_webhook_entry = self.create_input_group(dc_frame, "디스코드 웹훅 URL", self.config.get("discord_webhook", ""))

        self.start_btn = ctk.CTkButton(self, text="저장 및 활성화", font=("Helvetica", 16, "bold"), height=45, command=self.activate_bot)
        self.start_btn.pack(pady=10)

    def create_combo_time_input(self, parent, label_text, min_var, sec_var, suffix_m="분", suffix_s="초"):
        """최대 높이가 제한되고 스크롤바가 적용된 하이브리드 콤보박스 생성"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=8)
        
        ctk.CTkLabel(frame, text=label_text, font=("Helvetica", 13, "bold"), width=110, anchor="w").pack(side="left")
        
        values = [f"{i}{suffix_m}" for i in range(60)]
        sec_values = [f"{i}{suffix_s}" for i in range(60)]
        
        # height=8 옵션을 주어 8개까지만 보이고 우측 스크롤바가 생기도록 설정
        min_cb = ttk.Combobox(frame, textvariable=min_var, values=values, width=6, height=8, style="Dark.TCombobox")
        min_cb.pack(side="left", padx=(0, 5))
        
        sec_cb = ttk.Combobox(frame, textvariable=sec_var, values=sec_values, width=6, height=8, style="Dark.TCombobox")
        sec_cb.pack(side="left")

        # 마우스 휠을 굴려 숫자를 조절하는 기능 연결
        def on_scroll(event, var, suffix):
            try:
                val = int(var.get().replace(suffix, ""))
            except ValueError:
                val = 0
            if event.delta > 0: val = min(59, val + 1)
            else: val = max(0, val - 1)
            var.set(f"{val}{suffix}")

        min_cb.bind("<MouseWheel>", lambda e: on_scroll(e, min_var, suffix_m))
        sec_cb.bind("<MouseWheel>", lambda e: on_scroll(e, sec_var, suffix_s))

    def create_input_group(self, parent, label_text, default_value):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame, text=label_text, font=("Helvetica", 12)).pack(anchor="w")
        entry = ctk.CTkEntry(frame, width=320)
        entry.insert(0, default_value); entry.pack()
        return entry

    def browse_mp3(self):
        filename = filedialog.askopenfilename(
            title="알람 소리 선택",
            filetypes=[("오디오 파일", "*.mp3 *.wav"), ("모든 파일", "*.*")]
        )
        if filename:
            self.mp3_path_var.set(filename)

    def wait_for_key(self):
        self.key_btn.configure(text="키 입력 대기 중...", fg_color="red"); self.update()
        def key_listener():
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                self.target_key = event.name
                self.after(0, lambda: self.key_btn.configure(text=f"[{self.target_key}] 변경", fg_color=["#3a7ebf", "#1f538d"]))
        threading.Thread(target=key_listener, daemon=True).start()

    def on_volume_change(self, value):
        try: pygame.mixer.music.set_volume(value)
        except: pass

    def toggle_overlay(self):
        if self.show_overlay_var.get():
            if self.overlay_window is None: self.show_overlay()
        else:
            self.close_overlay()

    def close_overlay(self, event=None):
        if self.overlay_window:
            self.overlay_window.destroy(); self.overlay_window = None
        self.show_overlay_var.set(False)
        self.config["show_overlay"] = False
        self.save_config()

    def activate_bot(self):
        t_min = int(self.total_min_var.get().replace("분", ""))
        t_sec = int(self.total_sec_var.get().replace("초", ""))
        a_min = int(self.alarm_min_var.get().replace("분", ""))
        a_sec = int(self.alarm_sec_var.get().replace("초", ""))
        
        self.total_time = (t_min * 60) + t_sec
        self.alarm_time = (a_min * 60) + a_sec
        
        self.config.update({
            "key": self.target_key, "total_min": str(t_min), "total_sec": str(t_sec), 
            "alarm_min": str(a_min), "alarm_sec": str(a_sec), 
            "show_overlay": self.show_overlay_var.get(),
            "screen_fx": self.screen_fx_var.get(), "sound_fx": self.sound_fx_var.get(), "volume": self.volume_slider.get(),
            "mp3_path": self.mp3_path_var.get(),
            "dc_enable": self.dc_enable_var.get(), "dc_screen": self.dc_screen_var.get(),
            "discord_webhook": self.dc_webhook_entry.get()
        })
        self.save_config()
        self.toggle_overlay()
        
        keyboard.unhook_all()
        keyboard.add_hotkey(self.target_key, self.on_hotkey_pressed)
        self.hide_to_tray()

    def on_hotkey_pressed(self):
        self.time_left = self.total_time
        if not self.is_running:
            self.is_running = True; self.is_alarm_state = False
            if self.show_overlay_var.get() and self.overlay_window: self.after(0, self._redraw_clock)
            self.after(0, self.update_timer)
        else:
            if self.is_alarm_state: self.after(0, self.reset_alarm_visuals)

    def show_overlay(self):
        if self.overlay_window is not None: return
        self.overlay_window = ctk.CTkToplevel(self)
        w, h = self.config.get("overlay_w", 160), self.config.get("overlay_h", 160)
        x, y = self.config.get("overlay_x", 100), self.config.get("overlay_y", 100)
        self.overlay_window.geometry(f"{w}x{h}+{x}+{y}")
        self.overlay_window.overrideredirect(True)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.attributes("-alpha", 0.7)
        self.overlay_window.configure(fg_color="#1a1a1a")

        self.canvas = tk.Canvas(self.overlay_window, bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<Motion>", self._update_cursor)

        self._redraw_clock()

    def _get_resize_mode(self, x, y, w, h):
        m = self.RESIZE_MARGIN
        mode = ""
        if y < m: mode += "N"
        elif y > h - m: mode += "S"
        if x < m: mode += "W"
        elif x > w - m: mode += "E"
        return mode

    def _update_cursor(self, event):
        if not self.overlay_window: return
        w, h = self.overlay_window.winfo_width(), self.overlay_window.winfo_height()
        mode = self._get_resize_mode(event.x, event.y, w, h)
        if mode in ["N", "S"]: self.overlay_window.config(cursor="size_ns")
        elif mode in ["W", "E"]: self.overlay_window.config(cursor="size_we")
        elif mode in ["NW", "SE"]: self.overlay_window.config(cursor="size_nw_se")
        elif mode in ["NE", "SW"]: self.overlay_window.config(cursor="size_ne_sw")
        else: self.overlay_window.config(cursor="hand2")

    def _on_mouse_down(self, event):
        w, h = self.overlay_window.winfo_width(), self.overlay_window.winfo_height()
        mode = self._get_resize_mode(event.x, event.y, w, h)
        if mode:
            self._is_resizing = True; self._resize_mode = mode
            self._resize_data = {"rx": event.x_root, "ry": event.y_root, "x": self.overlay_window.winfo_x(), "y": self.overlay_window.winfo_y(), "w": w, "h": h}
        else:
            self._is_resizing = False; self._drag_data = {"x": event.x, "y": event.y}

    def _on_mouse_drag(self, event):
        if self._is_resizing:
            dx, dy = event.x_root - self._resize_data["rx"], event.y_root - self._resize_data["ry"]
            w, h, x, y, mode = self._resize_data["w"], self._resize_data["h"], self._resize_data["x"], self._resize_data["y"], self._resize_mode
            new_w, new_h, new_x, new_y = w, h, x, y
            
            if "E" in mode: new_w = max(self.MIN_SIZE, w + dx)
            if "S" in mode: new_h = max(self.MIN_SIZE, h + dy)
            if "W" in mode:
                new_w = w - dx
                if new_w >= self.MIN_SIZE: new_x = x + dx
                else: new_w, new_x = self.MIN_SIZE, x + (w - self.MIN_SIZE)
            if "N" in mode:
                new_h = h - dy
                if new_h >= self.MIN_SIZE: new_y = y + dy
                else: new_h, new_y = self.MIN_SIZE, y + (h - self.MIN_SIZE)
                
            self.overlay_window.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
            self._redraw_clock()
            self.config["overlay_w"], self.config["overlay_h"] = new_w, new_h
            self.config["overlay_x"], self.config["overlay_y"] = new_x, new_y
        else:
            del_x, del_y = event.x - self._drag_data["x"], event.y - self._drag_data["y"]
            new_x, new_y = self.overlay_window.winfo_x() + del_x, self.overlay_window.winfo_y() + del_y
            self.overlay_window.geometry(f"+{new_x}+{new_y}")
            self.config["overlay_x"], self.config["overlay_y"] = new_x, new_y

    def _redraw_clock(self):
        if not self.overlay_window: return
        self.canvas.delete("all")
        w, h = self.overlay_window.winfo_width(), self.overlay_window.winfo_height()
        if w < 10: w, h = self.config.get("overlay_w", 160), self.config.get("overlay_h", 160)

        size = min(w, h)
        margin = size * 0.06
        width = size * 0.05
        offset_x, offset_y = (w - size) / 2, (h - size) / 2
        coord = (offset_x + margin, offset_y + margin, offset_x + size - margin, offset_y + size - margin)

        self.canvas.create_oval(coord, outline="#333333", width=width)
        
        arc_color = "red" if self.is_alarm_state else "#00e5ff"
        text_color = "#ff4444" if self.is_alarm_state else "white"
        
        display_val = str(self.time_left) if self.is_running else str(self.total_time)
        text_val = "임박!" if self.is_alarm_state else display_val

        if self.is_running and self.total_time > 0:
            extent = (self.time_left / self.total_time) * 360
        else:
            extent = 360

        self.arc = self.canvas.create_arc(coord, start=90, extent=extent, outline=arc_color, width=width, style=tk.ARC)
        
        font_size = int(size * (0.18 if self.is_alarm_state else 0.22))
        self.text_id = self.canvas.create_text(w/2, h/2, text=text_val, fill=text_color, font=("Helvetica", font_size, "bold"))

        btn_size = int(size * 0.09)
        self.canvas.create_text(w - 20, 20, text="✕", fill="#666666", font=("Helvetica", max(12, btn_size), "bold"), tags="close_btn")
        self.canvas.tag_bind("close_btn", "<Enter>", lambda e: self.canvas.itemconfig("close_btn", fill="white"))
        self.canvas.tag_bind("close_btn", "<Leave>", lambda e: self.canvas.itemconfig("close_btn", fill="#666666"))
        self.canvas.tag_bind("close_btn", "<Button-1>", self.close_overlay)

    def update_timer(self):
        if not self.is_running: return

        if self.time_left > 0:
            if self.show_overlay_var.get() and self.overlay_window is not None:
                if self.total_time > 0:
                    extent = (self.time_left / self.total_time) * 360
                    try: self.canvas.itemconfig(self.arc, extent=extent)
                    except: pass
                if not self.is_alarm_state:
                    try: self.canvas.itemconfig(self.text_id, text=str(self.time_left))
                    except: pass
            
            if self.time_left == self.alarm_time and not self.is_alarm_state:
                self.trigger_alarm()
                
            self.time_left -= 1
            self.after(1000, self.update_timer)
        else:
            self.end_timer()

    def end_timer(self):
        self.is_running = False; self.is_alarm_state = False
        if self.red_bg: self.red_bg.destroy(); self.red_bg = None
        
        try: pygame.mixer.music.stop() 
        except: pass

        if self.show_overlay_var.get() and self.overlay_window:
            self.time_left = self.total_time
            self._redraw_clock()

    def play_alarm_sound(self):
        try:
            mp3_path = self.mp3_path_var.get()
            if mp3_path and os.path.exists(mp3_path):
                pygame.mixer.music.load(mp3_path)
                pygame.mixer.music.set_volume(self.volume_slider.get())
                pygame.mixer.music.play()
            else:
                winsound.Beep(1500, 800)
        except Exception as e:
            winsound.Beep(1500, 800)

    def trigger_alarm(self):
        self.is_alarm_state = True
        if self.show_overlay_var.get() and self.overlay_window: self._redraw_clock() 
        
        if self.screen_fx_var.get():
            self.red_bg = tk.Toplevel(self)
            self.red_bg.attributes("-fullscreen", True) 
            self.red_bg.attributes("-topmost", True)
            self.red_bg.configure(bg="#8B0000")
            self.red_bg.attributes("-alpha", 0.0) 
            
            if self.show_overlay_var.get() and self.overlay_window: self.overlay_window.lift()
            
            self.flash_alpha = 0.0; self.fade_in = True
            self.fade_alarm_bg()
        
        if self.sound_fx_var.get():
            threading.Thread(target=self.play_alarm_sound, daemon=True).start()
        
        if self.dc_enable_var.get() and self.config.get("discord_webhook"):
            threading.Thread(target=self.send_discord_msg, daemon=True).start()

    def fade_alarm_bg(self):
        if not self.is_alarm_state or self.red_bg is None: return
        if self.fade_in:
            self.flash_alpha += 0.015
            if self.flash_alpha >= 0.35: self.fade_in = False
        else:
            self.flash_alpha -= 0.015
            if self.flash_alpha <= 0.0:
                self.red_bg.destroy(); self.red_bg = None
                return
        self.red_bg.attributes("-alpha", self.flash_alpha)
        self.after(40, self.fade_alarm_bg)

    def reset_alarm_visuals(self):
        self.is_alarm_state = False
        if self.red_bg: self.red_bg.destroy(); self.red_bg = None
        
        try: pygame.mixer.music.stop() 
        except: pass

        if self.show_overlay_var.get(): self._redraw_clock()

    def send_discord_msg(self):
        webhook_url = self.config['discord_webhook']
        message_content = f"@everyone 🚨 지정 알림 도달! (남은 시간: {self.alarm_time}초)"
        try:
            if self.dc_screen_var.get():
                screenshot = ImageGrab.grab().convert("RGB")
                img_buffer = io.BytesIO()
                screenshot.save(img_buffer, format="JPEG", quality=70)
                img_buffer.seek(0)
                requests.post(webhook_url, data={"content": message_content}, files={"file": ("capture.jpg", img_buffer, "image/jpeg")}, timeout=5)
            else:
                requests.post(webhook_url, json={"content": message_content}, timeout=3)
        except Exception as e:
            print("디스코드 전송 실패:", e)

    def hide_to_tray(self): self.withdraw()
    def show_from_tray(self, icon, item): self.after(0, self.deiconify)
    def quit_app(self, icon, item): self.tray_icon.stop(); self.after(0, self.destroy); os._exit(0)

if __name__ == "__main__":
    app = ModernTimerApp()
    app.mainloop()