import tkinter as tk
from tkinter import ttk
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, time, date
import re
import json
import os
import webbrowser
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import datetime
import hashlib
import winreg
import ctypes
import sys

def get_app_path():
    # Returns the folder where the script or .exe is located
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_app_path()

def set_dark_title_bar(window):
    # Enable dark title bar on Windows 10 (1809+) and Windows 11
    if os.name != 'nt': return
    try:
        window.update()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        get_parent = ctypes.windll.user32.GetParent
        hwnd = get_parent(window.winfo_id())
        rendering_policy = ctypes.c_int(1)
        set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
    except Exception:
        pass

def get_windows_theme():
    # Detects if Windows is in Dark Mode for apps
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, regtype = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except Exception:
        return "light" # Default fallback
def get_app_version():
    version_file = os.path.join(BASE_PATH, "data", "version.json")
    script_file = os.path.join(BASE_PATH, "bvb.py")
    
    # If running as EXE (frozen), we don't increment version automatically based on hash
    # because the source .py file might not be exactly where we expect or might be static.
    is_exe = hasattr(sys, 'frozen')
    
    current_hash = ""
    if not is_exe:
        hasher = hashlib.md5()
        try:
            if os.path.exists(script_file):
                with open(script_file, 'rb') as f:
                    buf = f.read()
                    hasher.update(buf)
                current_hash = hasher.hexdigest()
        except Exception:
            pass
        
    try:
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                data = json.load(f)
                saved_hash = data.get("hash", "")
                version = data.get("version", "1.0.1")
                
            if not is_exe and current_hash and current_hash != saved_hash:
                parts = version.split('.')
                if len(parts) == 3:
                    parts[-1] = str(int(parts[-1]) + 1)
                    new_version = ".".join(parts)
                else:
                    new_version = version + ".1"
                    
                with open(version_file, 'w') as f:
                    json.dump({"version": new_version, "hash": current_hash}, f, indent=4)
                return new_version
            return version
        else:
            if not os.path.exists(os.path.join(BASE_PATH, "data")):
                os.makedirs(os.path.join(BASE_PATH, "data"))
            version = "1.0.1"
            with open(version_file, 'w') as f:
                json.dump({"version": version, "hash": current_hash}, f, indent=4)
            return version
    except Exception:
        return "1.0.1"

APP_VERSION = get_app_version()

DATA_DIR = os.path.join(BASE_PATH, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

class BVBWidget:
    def __init__(self, root):
        self.root = root
        theme = get_windows_theme()
        bg_col = "#121212" if theme == "dark" else "#f0f0f0"
        fg_col = "#e0e0e0" if theme == "dark" else "#000000"
        
        self.root.title(f"BVB Monitor v{APP_VERSION}")
        self.root.geometry("680x780")
        self.root.attributes("-topmost", True)
        self.root.configure(bg=bg_col)
        
        # Tooltip handling - MUST BE BEFORE ANY TABLE INIT
        self.tw = None

        self.today_str = date.today().strftime("%Y-%m-%d")
        self.history_file = os.path.join(DATA_DIR, f"intraday_history_{self.today_str}.json")
        self.history = self.load_history()
        
        self.last_variations = {}
        self.previous_values = {}
        self.countdown = 60
        self.market_status = "Necunoscut"
        self.stopped_for_today = False

        self.main_frame = tk.Frame(root, bg=bg_col)
        self.main_frame.pack(fill="both", expand=True)

        self.header_frame = tk.Frame(self.main_frame, bg=bg_col)
        self.header_frame.pack(fill="x", pady=5)

        self.label_market = tk.Label(self.header_frame, text="Piață: ...", font=("Arial", 9, "bold"), bg=bg_col, fg=fg_col)
        self.label_market.pack(side="left", padx=(10, 5))

        self.label_status = tk.Label(self.header_frame, text="Update: ...", font=("Arial", 9), bg=bg_col, fg=fg_col)
        self.label_status.pack(side="left", padx=5)
        
        self.label_countdown = tk.Label(self.header_frame, text="Next: 60s", font=("Arial", 9), fg="gray", bg=bg_col)
        self.label_countdown.pack(side="left", padx=5)

        # Theme Switcher
        self.dark_mode_var = tk.BooleanVar(value=(theme == "dark"))
        self.check_theme = tk.Checkbutton(self.header_frame, text="Dark Mode", variable=self.dark_mode_var,
                                          command=self.toggle_theme, bg=bg_col, fg=fg_col,
                                          selectcolor="#444444" if theme=="dark" else "white", 
                                          activebackground=bg_col, activeforeground=fg_col)
        self.check_theme.pack(side="right", padx=10)
        
        if theme == "dark":
            set_dark_title_bar(self.root)

        # Tooltip handling
        self.tw = None
        self.frame_ic = tk.Frame(self.main_frame, bg=bg_col)
        self.frame_ic.pack(padx=10, fill="x")
        self.table_ic = CustomTable(self.frame_ic, ["Indice", "Valoare", "Var%", "Evolutie"], [120, 120, 120, 150], self)

        tk.Label(self.main_frame, text="Acțiuni (Top 20 - Real Time)", font=("Arial", 10, "bold"), fg="darkgreen", bg=bg_col).pack(pady=(10, 5))
        self.frame_ctd = tk.Frame(self.main_frame)
        self.frame_ctd.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        self.table_ctd = CustomTable(self.frame_ctd, ["#", "Simbol", "Pret", "Var%", "Valoare", "BET", "Evolutie"], [30, 75, 80, 100, 110, 35, 120], self)

        self.bet_components = self.fetch_bet_components()
        self.update_data()
        self.tick()

    def fetch_bet_components(self):
        try:
            r = requests.get("https://bvb.ro/FinancialInstruments/Indices/IndicesProfiles", timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            tables = pd.read_html(StringIO(r.text))
            for df in tables:
                if "Simbol" in df.columns and "Societate" in df.columns:
                    return set(df["Simbol"].astype(str).tolist())
        except Exception as e:
            print("Eroare la preluarea componentelor BET:", e)
        # Fallback list if fetching fails
        return {"TLV", "H2O", "SNP", "SNG", "BRD", "SNN", "TGN", "EL", "M", "DIGI", "TTS", "WINE", "BVB", "TRP", "ONE", "AQ", "SFC", "FP", "COTE", "PREB"}

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Eroare la citire istoric (posibil corupt). Va incepe un fisier nou: {e}")
                pass
        return {}

    def save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f)
        except Exception as e:
            print("Eroare la salvare istoric:", e)

    def is_market_hours(self):
        now = datetime.now()
        if now.weekday() >= 5: return False
        current_time = now.time()
        return time(9, 45) <= current_time <= time(18, 15)

    def fetch_market_status(self, html):
        try:
            match = re.search(r'id="statusMarket"[^>]*>(.*?)</span>', html, re.IGNORECASE)
            if match: return match.group(1).strip()
        except: pass
        return "Necunoscut"

    def fetch_data(self):
        headers = {'User-Agent': 'Mozilla/5.0'}
        indices, stocks_dict = [], {}
        session = requests.Session()
        session.headers.update(headers)
        
        try:
            r1 = session.get("https://www.bvb.ro", timeout=10)
            self.market_status = self.fetch_market_status(r1.text)
            
            pattern_idx = re.compile(r"i=([A-Z-]+)'.*?>(.*?)</span>.*?id='sp.*?'>(.*?)</span>.*?<span.*?>(.*?)</span>", re.DOTALL)
            idx_matches = pattern_idx.findall(r1.text)
            seen = set()
            for m in idx_matches:
                symbol, name, val, var = m
                if symbol not in seen:
                    indices.append([symbol, val, var])
                    seen.add(symbol)
        except: pass

        if not self.stopped_for_today:
            try:
                r2 = session.get("https://www.bvb.ro/TradingAndStatistics/Trading/CurrentTradingDay", timeout=10)
                tables = pd.read_html(StringIO(r2.text))
                for df in tables:
                    if "Simbol" in df.columns and "Valoare" in df.columns:
                        for _, row in df.iterrows():
                            try:
                                s = str(row["Simbol"])
                                if s == "Simbol" or len(s) > 10: continue
                                stocks_dict[s] = [s, row["Pret"], row["Var. (%)"], row["Valoare"]]
                            except: continue

                r3 = session.get("https://www.bvb.ro/TradingAndStatistics/Trading/CurrentTradingDay?tab=Unitati%20de%20fond", timeout=10)
                tables_etf = pd.read_html(StringIO(r3.text))
                for df in tables_etf:
                    if "Simbol" in df.columns and "Valoare" in df.columns:
                        for _, row in df.iterrows():
                            try:
                                s = str(row["Simbol"])
                                if s == "Simbol" or len(s) > 10: continue
                                stocks_dict[s] = [s, row["Pret"], row["Var. (%)"], row["Valoare"]]
                            except: continue
            except: pass

        all_stocks = list(stocks_dict.values())
        all_stocks.sort(key=lambda x: self.clean_numeric(x[3]), reverse=True)
        return indices, all_stocks[:20]

    def update_data(self):
        current_date_str = date.today().strftime("%Y-%m-%d")
        if current_date_str != self.today_str:
            self.today_str = current_date_str
            self.history_file = os.path.join(DATA_DIR, f"intraday_history_{self.today_str}.json")
            self.history = self.load_history()

        indices, stocks = self.fetch_data()
        now_str = datetime.now().strftime("%H:%M:%S")
        
        # update history
        for row in indices:
            sym = str(row[0])
            val = self.clean_numeric(row[1])
            self.add_to_history(sym, now_str, val)
            
        for row in stocks:
            sym = str(row[0])
            val = self.clean_numeric(row[1]) / 10000.0
            self.add_to_history(sym, now_str, val)

        self.save_history()

        # Update Tables
        self.table_ic.update_rows(indices, "Indici")
        self.table_ctd.update_rows(stocks, "Acțiuni")
        
        now = datetime.now()
        self.label_status.config(text=f"Update: {now.strftime('%H:%M:%S')}")
        self.label_market.config(text=f"Piață: {self.market_status}")
        
        ms_lower = self.market_status.lower()
        if "deschis" in ms_lower: self.label_market.config(fg="green")
        elif "inchis" in ms_lower or "închis" in ms_lower: self.label_market.config(fg="red")
        else: self.label_market.config(fg="orange")

        if ("inchis" in ms_lower or "închis" in ms_lower) and now.time() > time(10, 0):
            self.stopped_for_today = True

    def add_to_history(self, symbol, current_time, val):
        if symbol not in self.history:
            self.history[symbol] = []
        
        hm = current_time[:5]
        if self.history[symbol]:
            # Always ensure the list is sorted after an update or add
            def get_m(t):
                p = t.split(':')
                return int(p[0])*60 + int(p[1])
            
            # Find if there is already a point in the same minute
            found = False
            for p in reversed(self.history[symbol]):
                if p['time'][:5] == hm:
                    p['time'] = current_time
                    p['price'] = val
                    found = True
                    break
            
            if not found:
                self.history[symbol].append({"time": current_time, "price": val})
                
            self.history[symbol].sort(key=lambda x: get_m(x['time']))
        else:
            self.history[symbol].append({"time": current_time, "price": val})

    def toggle_theme(self):
        # Update the theme and refresh UI
        self.apply_theme()
        # Refresh all tables
        self.table_ic.render_rows()
        self.table_ctd.render_rows()

    def apply_theme(self):
        theme = "dark" if self.dark_mode_var.get() else "light"
        bg_col = "#121212" if theme == "dark" else "#f0f0f0"
        fg_col = "#e0e0e0" if theme == "dark" else "#000000"
        
        self.root.configure(bg=bg_col)
        if theme == "dark":
            set_dark_title_bar(self.root)
        
        self.main_frame.configure(bg=bg_col)
        self.header_frame.configure(bg=bg_col)
        
        self.label_market.configure(bg=bg_col, fg=fg_col)
        self.label_status.configure(bg=bg_col, fg=fg_col)
        self.label_countdown.configure(bg=bg_col)
        self.check_theme.configure(bg=bg_col, fg=fg_col, selectcolor=bg_col, activebackground=bg_col, activeforeground=fg_col)
        
        # We need to update existing labels in the main frame (like "Indici", "Actiuni")
        for widget in self.main_frame.winfo_children():
            if isinstance(widget, tk.Label):
                if "Indici" in widget.cget("text"):
                    widget.configure(bg=bg_col, fg="#4db8ff" if theme == "dark" else "blue")
                elif "Acțiuni" in widget.cget("text"):
                    widget.configure(bg=bg_col, fg="#81c784" if theme == "dark" else "darkgreen")
                else:
                    widget.configure(bg=bg_col, fg=fg_col)
            elif isinstance(widget, tk.Frame) and widget not in (self.header_frame, self.main_frame):
                widget.configure(bg=bg_col)

        # Also update table internal state
        for table in (self.table_ic, self.table_ctd):
            table.apply_theme_colors(theme)

    def tick(self):
        now = datetime.now()
        if not self.is_market_hours():
            self.stopped_for_today = False
            next_check = "Luni la 09:45" if now.weekday() >= 4 else "mâine la 09:45"
            self.label_countdown.config(text=f"Revenim {next_check}", fg="orange")
            self.root.after(60000, self.tick)
            return

        if self.stopped_for_today:
            self.label_countdown.config(text="Închisă azi. Revenim mâine.", fg="red")
            self.root.after(60000, self.tick)
            return

        if self.countdown > 0:
            self.countdown -= 1
            self.label_countdown.config(text=f"Next: {self.countdown}s", fg="gray")
            self.root.after(1000, self.tick)
        else:
            self.update_data()
            self.countdown = 60
            self.tick()

    def clean_numeric(self, val):
        if isinstance(val, (int, float)): return float(val)
        try:
            s = str(val).strip().replace('%', '').replace('+', '').replace('▲', '').replace('▼', '').strip()
            if '.' in s and ',' in s: s = s.replace('.', '').replace(',', '.')
            elif ',' in s: s = s.replace(',', '.')
            return float(s)
        except: return 0.0

    def get_evolution_arrow(self, symbol, current_var):
        curr = self.clean_numeric(current_var)
        prev = self.last_variations.get(symbol)
        arrow = ""
        if prev is not None:
            if curr > prev: arrow = " ▲"
            elif curr < prev: arrow = " ▼"
        self.last_variations[symbol] = curr
        return arrow

    # Tooltip functions
    def show_tooltip(self, text, x, y):
        self.hide_tooltip()
        self.tw = tk.Toplevel(self.root)
        self.tw.wm_overrideredirect(1)
        self.tw.attributes("-topmost", True)
        lbl = tk.Label(self.tw, text=text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=("Arial", 8))
        lbl.pack(ipadx=4, ipady=4)
        self.tw.wm_geometry(f"+{x+15}+{y+10}")

    def hide_tooltip(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None


class DetailedChartWindow:
    def __init__(self, app, symbol, ref_price=None):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title(f"Grafic Detaliat - {symbol} (v{APP_VERSION})")
        self.top.geometry("1000x600")
        self.top.minsize(600, 400)
        
        self.symbol = symbol
        self.history = app.history
        self.ref_price = ref_price
        
        # Create a matplotlib figure
        self.fig = Figure(figsize=(10, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.top)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        self.points_x = []
        self.points_times = []
        
        # Determine theme from app if available
        is_dark = self.app.dark_mode_var.get()

        if is_dark:
            set_dark_title_bar(self.top)
            
        self.draw_chart()
        
        # Bind native Tkinter motion event
        self.canvas.get_tk_widget().bind("<Motion>", self.on_tk_motion)

    def on_tk_motion(self, event):
        # Convert raw tk pixels to matplotlib data coordinates manually
        # Matplotlib y-axis is inverted relative to Tkinter
        canvas_width = self.canvas_widget.winfo_width()
        canvas_height = self.canvas_widget.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
            
        # Get bounding box of the axes in figure pixels
        bbox = self.ax.bbox
        
        # Check if mouse is inside the axes box
        # Matplotlib Origin is bottom-left. Tkinter is top-left.
        mpl_y = canvas_height - event.y
        
        if mpl_y < bbox.y0 or mpl_y > bbox.y1 or event.x < bbox.x0 or event.x > bbox.x1:
            if hasattr(self, 'annot'):
                self.annot.set_text("Plasați mouse-ul pe grafic pentru detalii")
                if self.vline.get_visible():
                    self.vline.set_visible(False)
                    self.hline.set_visible(False)
                    self.hover_point.set_visible(False)
                self.canvas.draw()
            return
            
        # Transform pixels back to data coordinates
        inv = self.ax.transData.inverted()
        data_x, data_y = inv.transform((event.x, mpl_y))

        # Pass it as a mocked Matplotlib event block
        class MockEvent: pass
        mock_event = MockEvent()
        mock_event.inaxes = self.ax
        mock_event.xdata = data_x
        mock_event.ydata = data_y
        
        self.on_hover(mock_event)

    def is_dark(self):
        return self.app.dark_mode_var.get()

    def draw_chart(self):
        self.ax.clear()
        
        theme = "dark" if self.is_dark() else "light"
        bg_color = "#121212" if theme == "dark" else "#ffffff"
        fig_bg = "#121212" if theme == "dark" else "#f8f9fa"
        text_color = "#e0e0e0" if theme == "dark" else "#333333"
        grid_color = "#2a2a2a" if theme == "dark" else "#e0e0e0"
        ref_line_color = "#444444" if theme == "dark" else "#a0a0a0"
        crosshair_color = "#888888" if theme == "dark" else "#999999"
        
        pts = self.history.get(self.symbol, [])
        if not pts:
            self.ax.text(0.5, 0.5, "Nu există date.", ha='center', va='center', color=text_color, transform=self.ax.transAxes)
            self.canvas.draw()
            return
            
        ref_price = self.ref_price
        if ref_price is None or ref_price <= 0:
            ref_price = pts[0]['price']

        def get_mins(t_str):
            parts = t_str.split(':')
            m = (int(parts[0]) - 10) * 60 + int(parts[1]) + (float(parts[2]) / 60.0 if len(parts)>2 else 0)
            return max(0, min(m, 495.0))

        pts = sorted(pts, key=lambda p: get_mins(p['time']))
        
        # Prepare data
        times_str = [p['time'] for p in pts]
        prices = [p['price'] for p in pts]
        self.points_x = [get_mins(t) / 60.0 + 10.0 for t in times_str]
        self.points_y = prices
        self.points_times = times_str
        
        # Plot styling
        self.ax.grid(True, linestyle='--', alpha=0.4, color=grid_color)
        self.ax.set_facecolor(bg_color)
        self.fig.patch.set_facecolor(fig_bg)
        
        # Draw the reference line
        self.ax.axhline(y=ref_price, color=ref_line_color, linestyle='--', linewidth=1.5, zorder=1)
        
        # Advanced coloring: Fill between
        fill_up = "#1b3321" if theme == "dark" else "#e8f5e9"
        fill_down = "#3e1b1b" if theme == "dark" else "#ffebee"
        
        self.ax.fill_between(self.points_x, self.points_y, ref_price, where=[p >= ref_price for p in self.points_y], 
                             facecolor=fill_up, interpolate=True, alpha=0.5)
        self.ax.fill_between(self.points_x, self.points_y, ref_price, where=[p <= ref_price for p in self.points_y], 
                             facecolor=fill_down, interpolate=True, alpha=0.5)
        
        import numpy as np
        x = np.array(self.points_x)
        y = np.array(self.points_y)
        from matplotlib.collections import LineCollection
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        
        colors = []
        green = "#4caf50" if theme == "dark" else "#2e7d32"
        red = "#f44336" if theme == "dark" else "#c62828"
        for i in range(len(y)-1):
            if (y[i] + y[i+1])/2 >= ref_price: colors.append(green)
            else: colors.append(red)
                
        lc = LineCollection(segments, colors=colors, linewidths=2, antialiaseds=True, zorder=3)
        self.ax.add_collection(lc)
        
        # Initialize annotation elements
        self.annot = self.ax.text(0, 0, "",
                                  ha="left", va="top",
                                  bbox=dict(boxstyle="round", fc=bg_color, ec=ref_line_color, alpha=0.9),
                                  color=text_color, fontsize=10, zorder=100, visible=False)
        
        # Pre-hover message in a fixed corner
        self.msg_annot = self.ax.text(0.98, 0.95, "Mișcați mouse-ul pe grafic pentru detalii", 
                                      transform=self.ax.transAxes, ha="right", va="top",
                                      color=text_color, alpha=0.7, fontsize=9)
        
        self.vline, = self.ax.plot([], [], color=crosshair_color, linestyle='--', alpha=0.3, zorder=99, visible=False)
        self.hline, = self.ax.plot([], [], color=crosshair_color, linestyle='--', alpha=0.3, zorder=99, visible=False)
        dot_color = "#ffffff" if theme == "dark" else "#000000"
        self.hover_point, = self.ax.plot([], [], 'o', color=dot_color, markersize=6, zorder=101, visible=False)
        
        # Formatting
        self.ax.set_xlim(10.0, 18.25)
        self.ax.set_xticks(np.arange(10, 19, 1))
        self.ax.set_xticklabels([f"{int(h):02d}:00" for h in np.arange(10, 19, 1)], color=text_color)
        self.ax.tick_params(colors=text_color)
        
        def price_fmt(x, pos):
            return f"{x:,.4f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        self.ax.yaxis.set_major_formatter(ticker.FuncFormatter(price_fmt))
        
        all_prices = self.points_y + [ref_price]
        min_p, max_p = min(all_prices), max(all_prices)
        diff_p = (max_p - min_p) or 1
        self.ax.set_ylim(min_p - diff_p * 0.1, max_p + diff_p * 0.1)
        
        for spine in self.ax.spines.values():
            spine.set_color(grid_color)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        
        import matplotlib.transforms as mtransforms
        trans = mtransforms.blended_transform_factory(self.ax.transAxes, self.ax.transData)
        self.ax.text(-0.01, ref_price, price_fmt(ref_price, None), color=ref_line_color, fontweight='bold', 
                     ha='right', va='center', transform=trans, fontsize=9, 
                     bbox=dict(facecolor=fig_bg, edgecolor='none', pad=0))

        self.fig.tight_layout()
        # Final redraw with position update
        self.canvas.draw()

    def on_hover(self, event):
        if not self.points_x or event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            if hasattr(self, 'annot'):
                self.annot.set_visible(False)
                if hasattr(self, 'msg_annot'):
                    self.msg_annot.set_visible(True)
                if self.vline.get_visible():
                    self.vline.set_visible(False)
                    self.hline.set_visible(False)
                    self.hover_point.set_visible(False)
                self.canvas.draw()
            return
            
        # Find closest point by x-coordinate for DATA
        distances = [abs(px - event.xdata) for px in self.points_x]
        min_dist = min(distances)
        idx = distances.index(min_dist)
        snapped_x = self.points_x[idx]
        snapped_y = self.points_y[idx]
        time_str = self.points_times[idx]
        
        ref = self.ref_price
        var_pct = 0
        if ref and ref > 0:
            var_pct = (snapped_y - ref) / ref * 100
        sign = "+" if var_pct > 0 else ""
        
        price_str = f"{snapped_y:,.4f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        text = f"Ora: {time_str[:5]}\nPreț: {price_str}"
        if ref and ref > 0:
            text += f"\nVar: {sign}{var_pct:.2f}%"
            
        self.annot.set_text(text)
        
        # Dynamic positioning - FOLLOW MOUSE, but flip if near edge
        x_min, x_max = self.ax.get_xlim()
        ha = "left"
        offset = 0.01 * (x_max - x_min) # 1% offset instead of 5%
        if event.xdata > (x_min + x_max) / 2:
            ha = "right"
            offset = -offset
            
            
        # Position the tooltip box at literal mouse coordinates (with offset)
        # Top-left of tooltip at mouse
        self.annot.set_position((event.xdata + offset, event.ydata))
        self.annot.set_ha(ha)
        self.annot.set_va("top")
        self.annot.set_visible(True)
        
        if hasattr(self, 'msg_annot'):
            self.msg_annot.set_visible(False)
        
        # Crosshair lines STILL SNAP
        y_min, y_max = self.ax.get_ylim()
        self.vline.set_data([snapped_x, snapped_x], [y_min, y_max])
        self.hline.set_data([x_min, x_max], [snapped_y, snapped_y])
        self.vline.set_visible(True)
        self.hline.set_visible(True)
        self.hover_point.set_data([snapped_x], [snapped_y])
        self.hover_point.set_visible(True)
        
        self.canvas.draw()


class CustomTable:
    def __init__(self, parent, columns, widths, app):
        self.parent = parent
        self.columns = columns
        self.widths = widths
        self.app = app
        self.rows_data = []
        self.row_widgets = [] # Store references: (frame, {column_name: widget})
        self.sort_col = ""
        self.sort_rev = False

        app_theme = "dark" if self.app.dark_mode_var.get() else "light"
        self.apply_theme_colors(app_theme)

        self.header_frame = tk.Frame(parent, bg=self.header_bg)
        self.header_frame.pack(fill="x")
        self.body_frame = tk.Frame(parent, bg=self.body_bg)
        self.body_frame.pack(fill="both", expand=True)
        
        self.render_header()

    def apply_theme_colors(self, theme):
        self.header_bg = "#2d2d30" if theme == "dark" else "#d3d3d3"
        self.header_fg = "#ffffff" if theme == "dark" else "#000000"
        self.body_bg = "#1e1e1e" if theme == "dark" else "white"
        self.text_fg = "#e0e0e0" if theme == "dark" else "black"
        self.row_alt_bg = "#252526" if theme == "dark" else "#f2f2f2"
        self.highlight_bg = "#082846" if theme == "dark" else "#ffffcc"
        self.neutral_fg = "#aaaaaa" if theme == "dark" else "#555555"
        
        if hasattr(self, 'header_frame'):
            self.header_frame.configure(bg=self.header_bg)
        if hasattr(self, 'body_frame'):
            self.body_frame.configure(bg=self.body_bg)
        self.render_header()

    def render_header(self):
        if not hasattr(self, 'header_frame'): return
        for widget in self.header_frame.winfo_children():
            widget.destroy()

        for i, (c, w) in enumerate(zip(self.columns, self.widths)):
            btn = tk.Button(self.header_frame, text=c, relief="flat", bd=0, 
                            font=("Arial", 9, "bold"), bg=self.header_bg, fg=self.header_fg,
                            activebackground=self.header_bg, activeforeground=self.header_fg,
                            command=lambda _c=c: self.sort_by(_c))
            btn.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
            self.header_frame.columnconfigure(i, minsize=w)
            self.body_frame.columnconfigure(i, minsize=w)

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = col
            self.sort_rev = False
        self.render_rows()

    def update_rows(self, data, table_type):
        new_data = []
        for row in data:
            name = str(row[0])
            var_raw = row[2]
            var_num = self.app.clean_numeric(var_raw)
            current_key = (table_type, name)
            
            if table_type == "Indici":
                val_num = self.app.clean_numeric(row[1])
                price_num = val_num
            else:
                val_num = self.app.clean_numeric(row[3])
                price_num = self.app.clean_numeric(row[1]) / 10000.0
                var_num = var_num / 100.0
                
            if name == "EAI" and var_num == 0.0:
                var_num = (price_num - 8.4075) / 8.4075 * 100.0

            disp_prc = f"{price_num:,.4f}".replace(',', 'X').replace('.', ',').replace('X', '.') if table_type != "Indici" else f"{val_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            arrow = self.app.get_evolution_arrow(name, var_num)
            disp_var = f"{'+' if var_num > 0 else ''}{var_num:.2f}%{arrow}"
            disp_val = f"{val_num:,.0f}".replace(',', '.') if table_type != "Indici" else ""
            
            fg_color = "#4caf50" if var_num > 0 else "#f44336" if var_num < 0 else self.neutral_fg
            
            highlight_step = 0
            prev = self.app.previous_values.get(current_key)
            if prev and (prev[0] != price_num or prev[1] != var_num):
                highlight_step = 110 # 100 steps of solid (10s at 100ms) + 10 steps of fade
            
            self.app.previous_values[current_key] = (price_num, var_num)
            
            if table_type == "Indici":
                row_dict = {"Simbol": name, "Valoare": disp_prc, "Var%": disp_var, "_fg": fg_color, "_highlight": highlight_step, "_raw_price": price_num, "_raw_var": var_num}
            else:
                row_dict = {"Simbol": name, "Pret": disp_prc, "Var%": disp_var, "Valoare": disp_val, "BET": "*" if name in self.app.bet_components else "", "_fg": fg_color, "_highlight": highlight_step, "_raw_price": price_num, "_raw_var": var_num, "_raw_val": val_num}
            new_data.append(row_dict)

        self.rows_data = new_data
        self.render_rows()
        if any(r.get("_highlight", 0) > 0 for r in self.rows_data):
            self.app.root.after(100, self.fade_highlights)

    def fade_highlights(self):
        changed = False
        for idx, row in enumerate(self.rows_data):
            if row.get("_highlight", 0) > 0:
                row["_highlight"] -= 1
                self.update_row_visuals(idx)
                changed = True
        if changed:
            self.app.root.after(100, self.fade_highlights)

    def update_row_visuals(self, row_idx):
        if row_idx >= len(self.row_widgets): return
        row = self.rows_data[row_idx]
        frame, widgets = self.row_widgets[row_idx]
        
        base_color = self.row_alt_bg if row_idx % 2 == 0 else self.body_bg
        step = row.get("_highlight", 0)
        
        bg_color = base_color
        if step > 10:
            bg_color = self.highlight_bg
        elif step > 0:
            try:
                def hex_to_rgb(h): return [int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
                c1 = hex_to_rgb(self.highlight_bg)
                c2_raw = base_color
                if c2_raw == "white": c2_raw = "#ffffff"
                c2 = hex_to_rgb(c2_raw)
                mix = step / 10.0
                new_rgb = [int(c1[i]*mix + c2[i]*(1-mix)) for i in range(3)]
                bg_color = f'#{new_rgb[0]:02x}{new_rgb[1]:02x}{new_rgb[2]:02x}'
            except:
                bg_color = self.highlight_bg
        
        frame.configure(bg=bg_color)
        for col_name, w in widgets.items():
            try:
                w.configure(bg=bg_color)
            except:
                pass

    def render_rows(self):
        for widget in self.body_frame.winfo_children():
            widget.destroy()

        data_to_render = self.rows_data.copy()
        
        if self.sort_col:
            def sort_key(d):
                if self.sort_col in ("Valoare", "Pret"):
                    return d.get("_raw_val") if self.sort_col == "Valoare" and "_raw_val" in d else d.get("_raw_price")
                elif self.sort_col == "Var%":
                    return d.get("_raw_var")
                return d.get(self.sort_col, "")
            try:
                data_to_render.sort(key=sort_key, reverse=self.sort_rev)
            except:
                pass
        
        self.row_widgets = []
        for idx, row in enumerate(data_to_render):
            base_color = self.row_alt_bg if idx % 2 == 0 else self.body_bg
            step = row.get("_highlight", 0)
            
            bg_color = base_color
            if step > 10:
                bg_color = self.highlight_bg
            elif step > 0:
                try:
                    def hex_to_rgb(h): return [int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
                    c1 = hex_to_rgb(self.highlight_bg)
                    c2_raw = base_color
                    if c2_raw == "white": c2_raw = "#ffffff"
                    c2 = hex_to_rgb(c2_raw)
                    mix = step / 10.0
                    new_rgb = [int(c1[i]*mix + c2[i]*(1-mix)) for i in range(3)]
                    bg_color = f'#{new_rgb[0]:02x}{new_rgb[1]:02x}{new_rgb[2]:02x}'
                except:
                    bg_color = self.highlight_bg
            
            row_frame = tk.Frame(self.body_frame, bg=bg_color)
            row_frame.grid(row=idx, column=0, columnspan=len(self.columns), sticky="nsew")
            
            widgets_map = {}
            for c_idx, col in enumerate(self.columns):
                cell_bg = bg_color
                if col == "Evolutie":
                    canv = tk.Canvas(row_frame, width=self.widths[c_idx], height=24, bg=cell_bg, highlightthickness=0, cursor="hand2")
                    canv.grid(row=0, column=c_idx, padx=1, pady=1, sticky="nsew")
                    
                    ref_price = None
                    last_p = row.get("_raw_price", 0)
                    last_v = row.get("_raw_var", 0)
                    if last_p > 0 and last_v != 0:
                        ref_price = last_p / (1 + (last_v / 100.0))
                        
                    self.draw_sparkchart(canv, row["Simbol"], row["_fg"], ref_price)
                    canv.bind("<Motion>", lambda e, s=row["Simbol"], c=canv: self.on_hover(e, s, c))
                    canv.bind("<Leave>", self.app.hide_tooltip)
                    canv.bind("<Button-1>", lambda e, s=row["Simbol"], ref=ref_price: DetailedChartWindow(self.app, s, ref))
                    widgets_map[col] = canv
                else:
                    if col == "#":
                        text = str(idx + 1)
                        fg = "#555555"
                    else:
                        text = row.get(col, "")
                        if col == "Indice":
                            text = row.get("Simbol", "")
                        fg = row.get("_fg") if col == "Var%" else self.text_fg
                        
                    if col == "BET" and text == "*":
                        fg = "#00bcff" if get_windows_theme() == "dark" else "blue"
                    
                    cursor_style = ""
                    font_style = ("Arial", 9)
                    if col == "Simbol":
                        cursor_style = "hand2"
                        font_style = ("Arial", 9, "underline")
                        
                    lbl = tk.Label(row_frame, text=text, bg=cell_bg, fg=fg, font=font_style, cursor=cursor_style)
                    lbl.grid(row=0, column=c_idx, padx=1, pady=1, sticky="nsew")
                    
                    if col == "Simbol":
                        lbl.bind("<Button-1>", lambda e, s=row.get("Simbol", ""): webbrowser.open_new(f"https://bvb.ro/FinancialInstruments/Details/FinancialInstrumentsDetails.aspx?s={s}"))
                    widgets_map[col] = lbl
                row_frame.columnconfigure(c_idx, minsize=self.widths[c_idx])
            self.row_widgets.append((row_frame, widgets_map))

    def draw_sparkchart(self, canvas, symbol, color_hint, ref_price=None):
        canvas.delete("all")
        theme = "dark" if self.app.dark_mode_var.get() else "light"
        bg_c = "#121212" if theme == "dark" else canvas.master.cget("bg")
        canvas.configure(bg=bg_c)
        
        w = int(canvas['width'])
        h = int(canvas['height'])
            
        pts = self.app.history.get(symbol, [])
        if not pts:
            return
            
        if ref_price is None or ref_price <= 0:
            ref_price = pts[0]['price']
            
        def get_mins(t_str):
            parts = t_str.split(':')
            m = (int(parts[0]) - 10) * 60 + int(parts[1]) + (float(parts[2]) / 60.0 if len(parts)>2 else 0)
            return max(0, min(m, 495.0))  # Capped between 10:00 and 18:15

        pts = sorted(pts, key=lambda p: get_mins(p['time']))

        prices = [p['price'] for p in pts]
        prices.append(ref_price)
        min_p, max_p = min(prices), max(prices)
        if min_p == max_p:
            min_p -= 1
            max_p += 1
            
        coords = []
        for p in pts:
            m = get_mins(p['time'])
            x = max(0, min(m * w / 495.0, w))
            y = h - (p['price'] - min_p) / (max_p - min_p) * (h - 4) - 2
            coords.append((x, y))
            
        ref_y = h - (ref_price - min_p) / (max_p - min_p) * (h - 4) - 2

        def get_intersection(x1, y1, x2, y2, y_ref):
            if y1 == y2: return x1
            return x1 + (x2 - x1) * (y_ref - y1) / (y2 - y1)

        segments = []
        current_segment = []
        current_side = None

        for i in range(len(coords)):
            x, y = coords[i]
            side = "green" if y <= ref_y else "red"
            
            if current_side is None:
                current_side = side
                current_segment.append((x, y))
            elif current_side == side:
                current_segment.append((x, y))
            else:
                ix = get_intersection(coords[i-1][0], coords[i-1][1], x, y, ref_y)
                current_segment.append((ix, ref_y))
                segments.append((current_side, current_segment))
                current_side = side
                current_segment = [(ix, ref_y), (x, y)]

        if current_segment:
            segments.append((current_side, current_segment))
            
        ref_color = "#555555" if theme == "dark" else "#a0a0a0"
        canvas.create_line(0, ref_y, w, ref_y, fill=ref_color, dash=(2, 2))
        
        fill_up = "#1b3321" if theme == "dark" else "#e8f5e9"
        fill_down = "#3e1b1b" if theme == "dark" else "#ffebee"
        line_green = "#4caf50" if theme == "dark" else "green"
        line_red = "#f44336" if theme == "dark" else "red"
        
        for side, seg in segments:
            if len(seg) < 2:
                continue
            poly_pts = [(seg[0][0], ref_y)] + seg + [(seg[-1][0], ref_y)]
            fill_c = fill_up if side == "green" else fill_down
            line_c = line_green if side == "green" else line_red
            canvas.create_polygon(poly_pts, fill=fill_c, outline="")
            canvas.create_line(seg, fill=line_c, width=1.5)
            
        if coords:
            last_x, last_y = coords[-1]
            last_side = "green" if last_y <= ref_y else "red"
            last_line_c = line_green if last_side == "green" else line_red
            canvas.create_oval(last_x-2, last_y-2, last_x+2, last_y+2, fill=last_line_c, outline="")

    def on_hover(self, event, symbol, canvas):
        pts = self.app.history.get(symbol, [])
        if not pts: return
        w = int(canvas['width'])
        
        def get_mins(t_str):
            parts = t_str.split(':')
            m = (int(parts[0]) - 10) * 60 + int(parts[1])
            return max(0, min(m, 495.0))
            
        mouse_mins = event.x / w * 495.0
        
        closest = None
        min_dist = 9999
        for p in pts:
            m = get_mins(p['time'])
            dist = abs(m - mouse_mins)
            if dist < min_dist:
                min_dist = dist
                closest = p
                
        if closest and min_dist < 40: 
             price_str = f"{closest['price']:,.4f}".replace(',', 'X').replace('.', ',').replace('X', '.')
             
             # Calculate variation at this point
             var_str = ""
             current_price = closest['price']
             
             # Try to find the reference price from the main table data
             ref_price = None
             
             if ref_price is None:
                 # Find the current variation from the table to reverse-engineer ref price
                 for row in self.rows_data:
                     if row.get("Simbol") == symbol:
                         current_latest_price = row.get("_raw_price", 0)
                         current_latest_var = row.get("_raw_var", 0) # e.g. 1.35 for 1.35%
                         if current_latest_price > 0 and current_latest_var != 0:
                             ref_price = current_latest_price / (1 + (current_latest_var / 100.0))
                         elif current_latest_price > 0 and current_latest_var == 0:
                             # If BVB reports 0%, assume opening price was reference if no prior history
                             if pts:
                                 ref_price = pts[0]['price']
                         break
             
             if ref_price and ref_price > 0:
                 var_pct = (current_price - ref_price) / ref_price * 100
                 sign = "+" if var_pct > 0 else ""
                 var_str = f"\nVar: {sign}{var_pct:.2f}%"
                 
             self.app.show_tooltip(f"Ora: {closest['time'][:5]}\nPreț: {price_str}{var_str}", event.x_root, event.y_root)
        else:
             self.app.hide_tooltip()



if __name__ == "__main__":
    root = tk.Tk()
    app = BVBWidget(root)
    root.mainloop()
