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

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

class BVBWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("BVB Monitor")
        self.root.geometry("680x780")
        self.root.attributes("-topmost", True)

        self.today_str = date.today().strftime("%Y-%m-%d")
        self.history_file = os.path.join(DATA_DIR, f"intraday_history_{self.today_str}.json")
        self.history = self.load_history()
        
        self.last_variations = {}
        self.previous_values = {}
        self.countdown = 60
        self.market_status = "Necunoscut"
        self.stopped_for_today = False

        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill="both", expand=True)

        self.header_frame = tk.Frame(self.main_frame)
        self.header_frame.pack(fill="x", pady=5)

        self.label_market = tk.Label(self.header_frame, text="Piață: ...", font=("Arial", 9, "bold"))
        self.label_market.pack(side="left", padx=(10, 5))

        self.label_status = tk.Label(self.header_frame, text="Update: ...", font=("Arial", 9))
        self.label_status.pack(side="left", padx=5)
        
        self.label_countdown = tk.Label(self.header_frame, text="Next: 60s", font=("Arial", 9), fg="gray")
        self.label_countdown.pack(side="left", padx=5)

        # Tooltip handling
        self.tw = None

        tk.Label(self.main_frame, text="Indici", font=("Arial", 10, "bold"), fg="blue").pack()
        self.frame_ic = tk.Frame(self.main_frame)
        self.frame_ic.pack(padx=10, fill="x")
        self.table_ic = CustomTable(self.frame_ic, ["Indice", "Valoare", "Var%", "Evolutie"], [120, 120, 120, 150], self)

        tk.Label(self.main_frame, text="Acțiuni (Top 20 - Real Time)", font=("Arial", 10, "bold"), fg="darkgreen").pack(pady=(10, 5))
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


class CustomTable:
    def __init__(self, parent, columns, widths, app):
        self.parent = parent
        self.columns = columns
        self.widths = widths
        self.app = app
        self.rows_data = []
        self.sort_col = ""
        self.sort_rev = False

        self.header_frame = tk.Frame(parent, bg="#d3d3d3")
        self.header_frame.pack(fill="x")
        self.body_frame = tk.Frame(parent, bg="white")
        self.body_frame.pack(fill="both", expand=True)
        
        for i, (c, w) in enumerate(zip(self.columns, self.widths)):
            btn = tk.Button(self.header_frame, text=c, relief="raised", bd=1, font=("Arial", 9, "bold"),
                            command=lambda _c=c: self.sort_by(_c))
            btn.grid(row=0, column=i, sticky="nsew")
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
            
            fg_color = "green" if var_num > 0 else "red" if var_num < 0 else "black"
            
            is_changed = False
            prev = self.app.previous_values.get(current_key)
            if prev and (prev[0] != price_num or prev[1] != var_num):
                is_changed = True
            
            self.app.previous_values[current_key] = (price_num, var_num)
            
            if table_type == "Indici":
                row_dict = {"Simbol": name, "Valoare": disp_prc, "Var%": disp_var, "_fg": fg_color, "_changed": is_changed, "_raw_price": price_num, "_raw_var": var_num}
            else:
                row_dict = {"Simbol": name, "Pret": disp_prc, "Var%": disp_var, "Valoare": disp_val, "BET": "*" if name in self.app.bet_components else "", "_fg": fg_color, "_changed": is_changed, "_raw_price": price_num, "_raw_var": var_num, "_raw_val": val_num}
            new_data.append(row_dict)

        self.rows_data = new_data
        self.render_rows()

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
        
        for idx, row in enumerate(data_to_render):
            bg_color = "#ffffcc" if row.get("_changed") else ("#f9f9f9" if idx % 2 == 0 else "white")
            row_frame = tk.Frame(self.body_frame, bg=bg_color)
            row_frame.grid(row=idx, column=0, columnspan=len(self.columns), sticky="nsew")
            
            for c_idx, col in enumerate(self.columns):
                cell_bg = bg_color
                if col == "Evolutie":
                    canv = tk.Canvas(row_frame, width=self.widths[c_idx], height=24, bg=cell_bg, highlightthickness=0)
                    canv.grid(row=0, column=c_idx, padx=1, pady=1, sticky="nsew")
                    
                    ref_price = None
                    last_p = row.get("_raw_price", 0)
                    last_v = row.get("_raw_var", 0)
                    if last_p > 0 and last_v != 0:
                        ref_price = last_p / (1 + (last_v / 100.0))
                        
                    self.draw_sparkchart(canv, row["Simbol"], row["_fg"], ref_price)
                    canv.bind("<Motion>", lambda e, s=row["Simbol"], c=canv: self.on_hover(e, s, c))
                    canv.bind("<Leave>", self.app.hide_tooltip)
                else:
                    if col == "#":
                        text = str(idx + 1)
                        fg = "#555555"
                    else:
                        text = row.get(col, "")
                        if col == "Indice":
                            text = row.get("Simbol", "") # map Simbol to Indice
                        fg = row.get("_fg") if col == "Var%" else "black"
                        
                    if col == "BET" and text == "*":
                        fg = "blue"
                    
                    cursor_style = ""
                    font_style = ("Arial", 9)
                    if col == "Simbol":
                        cursor_style = "hand2"
                        font_style = ("Arial", 9, "underline")
                        
                    lbl = tk.Label(row_frame, text=text, bg=cell_bg, fg=fg, font=font_style, cursor=cursor_style)
                    lbl.grid(row=0, column=c_idx, padx=1, pady=1, sticky="nsew")
                    
                    if col == "Simbol":
                        lbl.bind("<Button-1>", lambda e, s=row.get("Simbol", ""): webbrowser.open_new(f"https://bvb.ro/FinancialInstruments/Details/FinancialInstrumentsDetails.aspx?s={s}"))
                row_frame.columnconfigure(c_idx, minsize=self.widths[c_idx])

        self.app.root.after(8000, self.clear_highlights)

    def draw_sparkchart(self, canvas, symbol, color_hint, ref_price=None):
        canvas.delete("all")
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
            
        canvas.create_line(0, ref_y, w, ref_y, fill="#a0a0a0", dash=(2, 2))
        
        for side, seg in segments:
            if len(seg) < 2:
                continue
            poly_pts = [(seg[0][0], ref_y)] + seg + [(seg[-1][0], ref_y)]
            fill_c = "#c8e6c9" if side == "green" else "#ffcdd2"
            line_c = "green" if side == "green" else "red"
            canvas.create_polygon(poly_pts, fill=fill_c, outline="")
            canvas.create_line(seg, fill=line_c, width=1.5)
            
        if coords:
            last_x, last_y = coords[-1]
            last_side = "green" if last_y <= ref_y else "red"
            last_line_c = "green" if last_side == "green" else "red"
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

    def clear_highlights(self):
        changed = False
        for row in self.rows_data:
            if row.get("_changed"):
                row["_changed"] = False
                changed = True
        if changed:
            self.render_rows()

if __name__ == "__main__":
    root = tk.Tk()
    app = BVBWidget(root)
    root.mainloop()
