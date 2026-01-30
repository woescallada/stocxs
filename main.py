import customtkinter as ctk
import json
import os
import threading
import yfinance as yf
import pandas as pd
import ta
from tkinter import messagebox
from datetime import datetime

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

JSON_FILE = "mis_acciones.json"
EXCEL_FILE = "stocks.xlsx"

# --- CLASE TOOLTIP ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule_show)
        self.widget.bind("<Leave>", self.hide_tooltip)
        self.widget.bind("<ButtonPress>", self.hide_tooltip)

    def schedule_show(self, event=None):
        self.unschedule()
        self.id = self.widget.after(500, self.show_tooltip) 

    def unschedule(self):
        id = self.id
        self.id = None
        if id: self.widget.after_cancel(id)

    def show_tooltip(self, event=None):
        if self.tooltip_window: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        frame = ctk.CTkFrame(self.tooltip_window, fg_color="#FFFFE0", border_width=1, border_color="black")
        frame.pack()
        ctk.CTkLabel(frame, text=self.text, text_color="#000", padx=10, pady=5, font=("Arial", 11)).pack()

    def hide_tooltip(self, event=None):
        self.unschedule()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🦅 Sniper Pro: The Advisor Edition")
        self.geometry("1750x850") # Un poco más ancho para la nueva columna

        self.is_running = False
        self.auto_refresh_active = True 
        
        self.tickers = []
        self.load_data()

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # PANEL IZQUIERDO
        self.left_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.left_frame, text="🦅 COMMAND CENTER", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        self.lbl_source = ctk.CTkLabel(self.left_frame, text="Modo: Asesor Activo 🤖", text_color="#00ffea")
        self.lbl_source.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Input
        self.input_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self.entry_ticker = ctk.CTkEntry(self.input_frame, placeholder_text="Añadir: AAPL...")
        self.entry_ticker.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.btn_add = ctk.CTkButton(self.input_frame, text="+", width=30, command=self.add_manual_ticker)
        self.btn_add.pack(side="right")

        self.switch_auto = ctk.CTkSwitch(self.left_frame, text="Auto-Refresh (30m)", command=self.toggle_auto_refresh)
        self.switch_auto.select()
        self.switch_auto.grid(row=3, column=0, padx=20, pady=20)

        self.lbl_count = ctk.CTkLabel(self.left_frame, text=f"Stocks: {len(self.tickers)}", font=ctk.CTkFont(weight="bold"))
        self.lbl_count.grid(row=4, column=0, padx=20, pady=5, sticky="w")

        self.scroll_tickers = ctk.CTkScrollableFrame(self.left_frame)
        self.scroll_tickers.grid(row=5, column=0, padx=20, pady=5, sticky="nsew")

        self.btn_analyze = ctk.CTkButton(self.left_frame, text="⚡ CONSULTAR ASESOR", height=50, 
                                         font=ctk.CTkFont(size=16, weight="bold"), 
                                         fg_color="#006400", hover_color="#004d00",
                                         command=self.manual_scan)
        self.btn_analyze.grid(row=6, column=0, padx=20, pady=20, sticky="ew")

        # PANEL DERECHO
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self.top_bar = ctk.CTkFrame(self.right_frame, fg_color="#222", height=50)
        self.top_bar.pack(fill="x")
        self.lbl_status = ctk.CTkLabel(self.top_bar, text="Esperando datos...", font=ctk.CTkFont(size=14))
        self.lbl_status.pack(side="left", padx=20, pady=10)
        self.lbl_last_update = ctk.CTkLabel(self.top_bar, text="", text_color="#aaaaaa")
        self.lbl_last_update.pack(side="right", padx=20)

        self.results_area = ctk.CTkScrollableFrame(self.right_frame)
        self.results_area.pack(fill="both", expand=True, padx=20, pady=20)

        self.refresh_ticker_list_ui()
        self.start_auto_timer()

    # --- DATA ---
    def load_data(self):
        loaded_tickers = set()
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE)
                loaded_tickers.update([str(x).strip().upper() for x in df.iloc[:, 0].dropna().tolist() if str(x).strip()])
            except: pass
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r") as f: loaded_tickers.update(json.load(f))
            except: pass
        self.tickers = list(loaded_tickers)

    def save_json(self):
        try:
            with open(JSON_FILE, "w") as f: json.dump(self.tickers, f)
        except: pass

    def add_manual_ticker(self):
        txt = self.entry_ticker.get().upper().replace(',', ' ')
        changed = False
        for n in [x.strip() for x in txt.split() if x.strip()]:
            if n not in self.tickers:
                self.tickers.append(n)
                changed = True
        if changed:
            self.save_json()
            self.refresh_ticker_list_ui()
        self.entry_ticker.delete(0, 'end')

    def remove_ticker(self, ticker):
        if ticker in self.tickers:
            self.tickers.remove(ticker)
            self.save_json()
            self.refresh_ticker_list_ui()

    def refresh_ticker_list_ui(self):
        self.lbl_count.configure(text=f"Stocks: {len(self.tickers)}")
        for w in self.scroll_tickers.winfo_children(): w.destroy()
        for t in self.tickers:
            row = ctk.CTkFrame(self.scroll_tickers, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=t, width=60, anchor="w").pack(side="left")
            ctk.CTkButton(row, text="✕", width=25, height=20, fg_color="#442222", hover_color="#ff0000", command=lambda x=t: self.remove_ticker(x)).pack(side="right")

    def toggle_auto_refresh(self): self.auto_refresh_active = bool(self.switch_auto.get())
    def start_auto_timer(self):
        if self.auto_refresh_active and not self.is_running: self.manual_scan()
        self.after(1800000, self.start_auto_timer)

    # --- ANÁLISIS ---
    def manual_scan(self):
        if self.is_running: return
        if not self.tickers: return messagebox.showwarning("!", "Añade acciones.")
        self.is_running = True
        self.btn_analyze.configure(state="disabled", text="⏳ PROCESANDO...", fg_color="#555")
        threading.Thread(target=self.run_analysis_thread, daemon=True).start()

    def run_analysis_thread(self):
        results = []
        for i, ticker in enumerate(self.tickers):
            self.lbl_status.configure(text=f"Analizando {i+1}/{len(self.tickers)}: {ticker}")
            data = self.analyze_stock(ticker)
            if data: results.append(data)
        self.after(0, lambda: self.render_results(results))

    def analyze_stock(self, ticker):
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="6mo") # Necesitamos un poco más de datos para MACD fiable
            if len(df) < 50: return None
            
            info = t.info
            price = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            
            # --- Indicadores Técnicos ---
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
            atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
            
            # MACD (Importante para la señal)
            macd = ta.trend.MACD(df['Close'])
            macd_diff = macd.macd_diff().iloc[-1] # Histograma
            
            # Volumen
            vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            rvol = vol / avg_vol if avg_vol > 0 else 0

            # --- CÁLCULO DEL SCORE (Calidad 0-100) ---
            score = 0
            float_shares = info.get('floatShares', 0)
            if float_shares > 0 and float_shares < 20_000_000: score += 15
            if rvol > 2: score += 20
            if price > sma50: score += 15
            score = max(0, min(100, int(score + 40))) # Base 40

            # --- CÁLCULO DEL ASESOR (Señal -100% a +100%) ---
            signal = 0
            
            # 1. Tendencia (Peso: 40%)
            if price > sma50: signal += 30
            else: signal -= 30
            
            # 2. Momentum MACD (Peso: 20%)
            if macd_diff > 0: signal += 20
            else: signal -= 20
            
            # 3. RSI Extremo (Reversión a la media)
            if rsi < 30: signal += 40      # Oportunidad de oro (rebote)
            elif rsi > 75: signal -= 40    # Peligro de caída
            elif rsi > 50: signal += 10    # Fuerza relativa
            else: signal -= 10
            
            # 4. Amplificador de Volumen
            if rvol > 3:
                # Si la señal ya es positiva, el volumen la confirma
                if signal > 0: signal += 20
                # Si es negativa, el volumen confirma la caída
                else: signal -= 20

            # Limitar a -100 y +100
            signal_pct = max(-100, min(100, int(signal)))

            # Texto y Color del Asesor
            adv_text = "MANTENER"
            adv_col = "white"
            
            if signal_pct >= 80:
                adv_text = "💎 COMPRA FUERTE"
                adv_col = "#00ffea" # Cyan Neon
            elif signal_pct >= 30:
                adv_text = "🟢 COMPRAR"
                adv_col = "#00ff00" # Verde
            elif signal_pct <= -80:
                adv_text = "🆘 VENTA FUERTE"
                adv_col = "#ff0000" # Rojo Puro
            elif signal_pct <= -30:
                adv_text = "🟠 VENDER"
                adv_col = "#ff8800" # Naranja
            else:
                adv_text = "⚪ MANTENER"
                adv_col = "#cccccc"

            # Targets
            stop = price - (2 * atr)
            target = price + (3 * atr)
            potencial = ((target - price) / price) * 100

            # Variaciones para la tabla
            pct_1d = ((price - prev) / prev) * 100
            
            return {
                "Ticker": ticker, "Price": price, "Score": score,
                "SignalPct": signal_pct, "AdvText": adv_text, "AdvCol": adv_col,
                "Pct1D": pct_1d, "RVol": rvol,
                "Stop": stop, "Target": target, "Potencial": potencial
            }
        except: return None

    def render_results(self, results):
        self.is_running = False
        self.btn_analyze.configure(state="normal", text="⚡ CONSULTAR ASESOR", fg_color="#006400")
        self.lbl_last_update.configure(text=f"Act: {datetime.now().strftime('%H:%M')}")
        self.lbl_status.configure(text="Análisis completado.")

        for w in self.results_area.winfo_children(): w.destroy()
        if not results: return
        
        # Ordenar por Señal del Asesor (Lo más fuerte arriba)
        results.sort(key=lambda x: x['SignalPct'], reverse=True)

        cols = [
            ("Ticker", 60, "Símbolo"),
            ("ASESOR 🤖", 160, "Recomendación basada en confluencia técnica.\n+100%: Compra Agresiva\n-100%: Venta Agresiva"),
            ("Confianza", 70, "% de seguridad en la dirección."),
            ("Score", 50, "Calidad Técnica (0-100)"),
            ("Precio", 70, "Precio actual"),
            ("% Hoy", 60, "Variación diaria"),
            ("R.Vol", 50, "Volumen Relativo"),
            ("Target 🎯", 70, "Objetivo"),
            ("Potencial", 70, "Ganancia esperada"),
            ("Stop Loss", 70, "Stop de protección")
        ]

        h_frame = ctk.CTkFrame(self.results_area, fg_color="#333", height=40)
        h_frame.pack(fill="x", pady=(0, 5))

        for text, w, tip in cols:
            lbl = ctk.CTkLabel(h_frame, text=text, width=w, font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=2)
            ToolTip(lbl, tip)

        for res in results:
            # Color de fondo sutil según la señal
            bg = "#222"
            if res['SignalPct'] >= 80: bg = "#002b2b" # Fondo verdoso muy oscuro
            elif res['SignalPct'] <= -80: bg = "#2b0000" # Fondo rojizo muy oscuro

            row = ctk.CTkFrame(self.results_area, fg_color=bg)
            row.pack(fill="x", pady=2)

            self.mk_cell(row, res['Ticker'], 60, True)
            
            # Columna ASESOR
            adv_lbl = ctk.CTkLabel(row, text=res['AdvText'], width=160, text_color=res['AdvCol'], font=ctk.CTkFont(weight="bold"))
            adv_lbl.pack(side="left", padx=2)
            
            # Columna CONFIANZA %
            conf_text = f"{res['SignalPct']:+d}%"
            conf_col = res['AdvCol']
            self.mk_cell(row, conf_text, 70, bold=True, color=conf_col)

            # Score
            sc_col = "#00ff00" if res['Score'] >= 70 else "white"
            self.mk_cell(row, str(res['Score']), 50, color=sc_col)

            self.mk_cell(row, f"${res['Price']:.2f}", 70)
            self.mk_cell(row, f"{res['Pct1D']:+.1f}%", 60, color="#00ff00" if res['Pct1D']>0 else "#ff5555")
            
            rv_col = "#d000ff" if res['RVol'] > 3 else "white"
            self.mk_cell(row, f"{res['RVol']:.1f}x", 50, color=rv_col)

            self.mk_cell(row, f"${res['Target']:.2f}", 70, color="#7fff00")
            self.mk_cell(row, f"+{res['Potencial']:.1f}%", 70, color="#7fff00")
            self.mk_cell(row, f"${res['Stop']:.2f}", 70, color="#ffaaaa")

    def mk_cell(self, parent, text, w, bold=False, color="white"):
        f = ctk.CTkFont(weight="bold") if bold else ctk.CTkFont()
        ctk.CTkLabel(parent, text=text, width=w, text_color=color, font=f).pack(side="left", padx=2)

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()
