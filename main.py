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

# --- CLASE TOOLTIP (Para las descripciones al pasar el ratón) ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, fg_color="#FFFFE0", text_color="#000", 
                             corner_radius=5, padx=10, pady=5, font=("Arial", 11))
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🦅 Sniper Swing Trader (Pro Edition)")
        self.geometry("1650x850") 

        self.is_running = False
        self.auto_refresh_active = True 
        self.tickers = self.load_data_source()

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # PANEL IZQUIERDO
        self.left_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.left_frame, text="🦅 SWING COMMAND", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        self.lbl_source = ctk.CTkLabel(self.left_frame, text="Fuente: ...", text_color="gray")
        self.lbl_source.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Input Manual
        self.input_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self.entry_ticker = ctk.CTkEntry(self.input_frame, placeholder_text="Ticker...")
        self.entry_ticker.pack(side="left", fill="x", expand=True, padx=(0,5))
        ctk.CTkButton(self.input_frame, text="+", width=30, command=self.add_manual_ticker).pack(side="right")

        self.switch_auto = ctk.CTkSwitch(self.left_frame, text="Auto-Refresh (30m)", command=self.toggle_auto_refresh)
        self.switch_auto.select()
        self.switch_auto.grid(row=3, column=0, padx=20, pady=20)

        self.lbl_count = ctk.CTkLabel(self.left_frame, text=f"Stocks: {len(self.tickers)}", font=ctk.CTkFont(weight="bold"))
        self.lbl_count.grid(row=4, column=0, padx=20, pady=5, sticky="w")

        self.scroll_tickers = ctk.CTkScrollableFrame(self.left_frame)
        self.scroll_tickers.grid(row=5, column=0, padx=20, pady=5, sticky="nsew")

        self.btn_analyze = ctk.CTkButton(self.left_frame, text="⚡ ESCANEAR MERCADO", height=50, 
                                         font=ctk.CTkFont(size=16, weight="bold"), 
                                         fg_color="#006400", hover_color="#004d00",
                                         command=self.manual_scan)
        self.btn_analyze.grid(row=6, column=0, padx=20, pady=20, sticky="ew")

        # PANEL DERECHO
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self.top_bar = ctk.CTkFrame(self.right_frame, fg_color="#222", height=50)
        self.top_bar.pack(fill="x")
        self.lbl_status = ctk.CTkLabel(self.top_bar, text="Esperando órdenes...", font=ctk.CTkFont(size=14))
        self.lbl_status.pack(side="left", padx=20, pady=10)
        self.lbl_last_update = ctk.CTkLabel(self.top_bar, text="", text_color="#aaaaaa")
        self.lbl_last_update.pack(side="right", padx=20)

        self.results_area = ctk.CTkScrollableFrame(self.right_frame)
        self.results_area.pack(fill="both", expand=True, padx=20, pady=20)

        self.refresh_ticker_list_ui()
        self.update_source_label()
        self.start_auto_timer()

    # --- GESTIÓN DE DATOS ---
    def load_data_source(self):
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE)
                clean_list = [str(x).strip().upper() for x in df.iloc[:, 0].dropna().tolist() if str(x).strip()]
                self.using_excel = True
                return list(set(clean_list))
            except: pass
        self.using_excel = False
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r") as f: return json.load(f)
        return []

    def update_source_label(self):
        if self.using_excel:
            self.lbl_source.configure(text=f"📂 Excel: {EXCEL_FILE}", text_color="#4deeea")
            self.entry_ticker.configure(state="disabled")
        else:
            self.lbl_source.configure(text="📝 Manual (JSON)", text_color="#ffb84d")

    def save_json(self):
        if not self.using_excel:
            with open(JSON_FILE, "w") as f: json.dump(self.tickers, f)

    def add_manual_ticker(self):
        if self.using_excel: return
        txt = self.entry_ticker.get().upper().replace(',', ' ')
        for n in [x.strip() for x in txt.split() if x.strip()]:
            if n not in self.tickers: self.tickers.append(n)
        self.save_json()
        self.entry_ticker.delete(0, 'end')
        self.refresh_ticker_list_ui()

    def remove_ticker(self, ticker):
        if self.using_excel: return
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
            if not self.using_excel:
                ctk.CTkButton(row, text="x", width=20, fg_color="transparent", text_color="red", command=lambda x=t: self.remove_ticker(x)).pack(side="right")

    def toggle_auto_refresh(self): self.auto_refresh_active = bool(self.switch_auto.get())
    def start_auto_timer(self):
        if self.auto_refresh_active and not self.is_running: self.manual_scan()
        self.after(1800000, self.start_auto_timer)

    # --- ANÁLISIS ---
    def manual_scan(self):
        if self.is_running: return
        if self.using_excel: 
            self.tickers = self.load_data_source()
            self.refresh_ticker_list_ui()
        if not self.tickers: return messagebox.showwarning("!", "No hay acciones.")
        
        self.is_running = True
        self.btn_analyze.configure(state="disabled", text="⏳ ESCANEANDO...", fg_color="#555")
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
            # Pedimos 3 meses para tener margen de cálculo
            df = t.history(period="3mo") 
            if len(df) < 20: return None # Necesitamos mínimo 1 mes de trading
            
            # Precios Clave
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            close_5d = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
            close_15d = df['Close'].iloc[-16] if len(df) >= 16 else df['Close'].iloc[0]
            
            # Variaciones %
            pct_today = ((current_price - prev_close) / prev_close) * 100
            pct_5d = ((current_price - close_5d) / close_5d) * 100
            pct_15d = ((current_price - close_15d) / close_15d) * 100
            
            # Indicadores
            sma50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) > 50 else current_price
            atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
            rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
            
            # Volumen
            vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            rvol = vol / avg_vol if avg_vol > 0 else 0

            # 52 Week High (Aprox con lo que tenemos o fast_info)
            try: year_high = t.fast_info['year_high']
            except: year_high = df['High'].max()
            dist_high = ((year_high - current_price) / current_price) * 100

            # --- TARGETS SWING ---
            stop_loss = current_price - (2 * atr)
            target = current_price + (3 * atr) # Ratio 1.5
            potential = ((target - current_price) / current_price) * 100

            # --- VEREDICTO SWING ---
            verdict = "NEUTRAL"
            verdict_col = "white"

            # Logica de Trader
            if rsi > 75:
                verdict = "⚠️ SOBRECOMPRA"
                verdict_col = "#ff5555"
            elif pct_today > 15 and rvol > 2:
                verdict = "🚀 MOMENTUM" # Se está moviendo AHORA
                verdict_col = "#ffff00"
            elif pct_5d > 10 and pct_today < 0 and rsi < 60:
                verdict = "🛒 DIP BUY" # Tendencia alcista, día rojo (rebote)
                verdict_col = "#00ffea"
            elif pct_15d > 30 and current_price > sma50:
                verdict = "💎 TENDENCIA" # Tren en marcha
                verdict_col = "#00ff00"
            elif current_price < sma50 and pct_15d < -10:
                verdict = "❌ BAJISTA"
                verdict_col = "#ff0000"

            return {
                "Ticker": ticker, "Price": current_price,
                "Pct1D": pct_today, "Pct5D": pct_5d, "Pct15D": pct_15d,
                "RVol": rvol, "DistHigh": dist_high,
                "Verdict": verdict, "VerdictCol": verdict_col,
                "Stop": stop_loss, "Target": target, "Potencial": potential
            }
        except Exception as e: 
            print(f"Error {ticker}: {e}")
            return None

    def render_results(self, results):
        self.is_running = False
        self.btn_analyze.configure(state="normal", text="⚡ ESCANEAR MERCADO", fg_color="#006400")
        self.lbl_last_update.configure(text=f"Act: {datetime.now().strftime('%H:%M')}")
        self.lbl_status.configure(text="Listo.")

        for w in self.results_area.winfo_children(): w.destroy()
        if not results: return
        results.sort(key=lambda x: x['Pct1D'], reverse=True) # Ordenar por lo que se mueve HOY

        # --- CABECERAS CON TOOLTIPS ---
        # Definición: (Texto Mostrado, Ancho, Texto Tooltip)
        cols = [
            ("Ticker", 60, "Símbolo de la acción"),
            ("VEREDICTO", 120, "Opinión del Algoritmo basada en tendencia y momentum."),
            ("Precio", 70, "Precio actual de mercado."),
            ("% Hoy", 70, "Variación intradía. ¿Se mueve hoy?"),
            ("% 5D", 70, "Variación en 1 semana. ¿Tiene consistencia?"),
            ("% 15D", 70, "Variación en 3 semanas. Tendencia a medio plazo."),
            ("R.Vol", 60, "Volumen Relativo.\n>1: Más interés de lo normal.\n>3: ¡Explosivo!"),
            ("Target 🎯", 80, "Objetivo de venta técnica (Techo probable)."),
            ("Potencial", 70, "% de ganancia hasta el Target."),
            ("Stop Loss", 80, "Vende aquí si baja para proteger capital.")
        ]

        h_frame = ctk.CTkFrame(self.results_area, fg_color="#333", height=40)
        h_frame.pack(fill="x", pady=(0, 5))

        for text, w, tip in cols:
            lbl = ctk.CTkLabel(h_frame, text=text, width=w, font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=2)
            ToolTip(lbl, tip) # <-- AQUI SE AÑADE LA MAGIA DEL HOVER

        # --- FILAS ---
        for res in results:
            bg = "#222"
            if "MOMENTUM" in res['Verdict']: bg = "#2d2d00" # Fondo amarillento oscuro
            elif "DIP BUY" in res['Verdict']: bg = "#002d2d" # Fondo cyan oscuro

            row = ctk.CTkFrame(self.results_area, fg_color=bg)
            row.pack(fill="x", pady=2)

            self.mk_cell(row, res['Ticker'], 60, True)
            
            v_lbl = ctk.CTkLabel(row, text=res['Verdict'], width=120, text_color=res['VerdictCol'], font=ctk.CTkFont(weight="bold"))
            v_lbl.pack(side="left")

            self.mk_cell(row, f"${res['Price']:.2f}", 70)

            # Colores condicionales para porcentajes
            self.mk_cell(row, f"{res['Pct1D']:+.1f}%", 70, color=self.get_col(res['Pct1D']))
            self.mk_cell(row, f"{res['Pct5D']:+.1f}%", 70, color=self.get_col(res['Pct5D']))
            self.mk_cell(row, f"{res['Pct15D']:+.1f}%", 70, color=self.get_col(res['Pct15D']))
            
            # RVol en morado si es alto (Penny stock action)
            rv_col = "#d000ff" if res['RVol'] > 3 else "white"
            self.mk_cell(row, f"{res['RVol']:.1f}x", 60, color=rv_col)

            self.mk_cell(row, f"${res['Target']:.2f}", 80, color="#7fff00", bold=True)
            self.mk_cell(row, f"+{res['Potencial']:.1f}%", 70, color="#7fff00")
            self.mk_cell(row, f"${res['Stop']:.2f}", 80, color="#ffaaaa")

    def get_col(self, val): return "#00ff00" if val > 0 else "#ff5555"

    def mk_cell(self, parent, text, w, bold=False, color="white"):
        f = ctk.CTkFont(weight="bold") if bold else ctk.CTkFont()
        ctk.CTkLabel(parent, text=text, width=w, text_color=color, font=f).pack(side="left", padx=2)

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()
