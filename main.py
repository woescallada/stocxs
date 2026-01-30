import customtkinter as ctk
import json
import os
import threading
import yfinance as yf
import pandas as pd
import ta
from tkinter import messagebox
from datetime import datetime

# --- CONFIGURACIÓN ESTILO ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

JSON_FILE = "mis_acciones.json"
EXCEL_FILE = "stocks.xlsx"

# --- TOOLTIPS ---
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

class OracleApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🏛️ THE ORACLE: Swing Trading System")
        self.geometry("1750x900")

        self.is_running = False
        self.market_condition = "NEUTRAL" # BULLISH, BEARISH, NEUTRAL
        self.market_score = 0 # -10 a +10
        self.tickers = []
        self.load_data()

        # --- LAYOUT PRINCIPAL ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === PANEL DE MANDO (Izquierda) ===
        self.left_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.left_frame, text="🏛️ ORACLE OS", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(30, 10))
        ctk.CTkLabel(self.left_frame, text="By Warren 'Gemini' Buffett", text_color="gray").pack(pady=(0, 20))

        # Input
        input_box = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        input_box.pack(pady=10, padx=20, fill="x")
        self.entry_ticker = ctk.CTkEntry(input_box, placeholder_text="Añadir (ej: TSLA)")
        self.entry_ticker.pack(side="left", fill="x", expand=True, padx=(0,5))
        ctk.CTkButton(input_box, text="+", width=30, command=self.add_manual_ticker).pack(side="right")

        # Lista
        self.lbl_count = ctk.CTkLabel(self.left_frame, text=f"Cartera: {len(self.tickers)} activos", font=ctk.CTkFont(weight="bold"))
        self.lbl_count.pack(pady=5, padx=20, anchor="w")
        
        self.scroll_tickers = ctk.CTkScrollableFrame(self.left_frame)
        self.scroll_tickers.pack(fill="both", expand=True, padx=20, pady=10)

        # Botón Maestro
        self.btn_analyze = ctk.CTkButton(self.left_frame, text="🔍 ANÁLISIS DIARIO", height=60, 
                                         font=ctk.CTkFont(size=16, weight="bold"), 
                                         fg_color="#1a1a1a", border_width=2, border_color="#00ffea",
                                         hover_color="#333",
                                         command=self.manual_scan)
        self.btn_analyze.pack(padx=20, pady=30, fill="x")

        # === PANEL DE DATOS (Derecha) ===
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        # HEADER: ESTADO DEL MERCADO (EL OJO DE SAURON)
        self.market_frame = ctk.CTkFrame(self.right_frame, fg_color="#111", height=80, corner_radius=10)
        self.market_frame.pack(fill="x", padx=20, pady=10)
        
        self.lbl_market_status = ctk.CTkLabel(self.market_frame, text="ESPERANDO ANÁLISIS DE MERCADO (SPY & VIX)...", 
                                              font=ctk.CTkFont(size=18, weight="bold"), text_color="gray")
        self.lbl_market_status.place(relx=0.5, rely=0.5, anchor="center")

        # RESULTADOS
        self.results_area = ctk.CTkScrollableFrame(self.right_frame)
        self.results_area.pack(fill="both", expand=True, padx=20, pady=10)

        self.refresh_ticker_list_ui()

    # --- DATA & GESTIÓN ---
    def load_data(self):
        loaded = set()
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE)
                loaded.update([str(x).strip().upper() for x in df.iloc[:, 0].dropna().tolist() if str(x).strip()])
            except: pass
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r") as f: loaded.update(json.load(f))
            except: pass
        self.tickers = list(loaded)

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
        self.lbl_count.configure(text=f"Cartera: {len(self.tickers)} activos")
        for w in self.scroll_tickers.winfo_children(): w.destroy()
        for t in self.tickers:
            row = ctk.CTkFrame(self.scroll_tickers, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=t, width=60, anchor="w").pack(side="left")
            ctk.CTkButton(row, text="x", width=25, height=20, fg_color="#442222", hover_color="red", command=lambda x=t: self.remove_ticker(x)).pack(side="right")

    # --- EL CEREBRO DE BUFFETT ---
    def manual_scan(self):
        if self.is_running: return
        if not self.tickers: return messagebox.showwarning("!", "Añade acciones.")
        self.is_running = True
        self.btn_analyze.configure(state="disabled", text="⏳ CONSULTANDO AL FED...")
        threading.Thread(target=self.run_full_analysis, daemon=True).start()

    def run_full_analysis(self):
        # 1. ANALIZAR EL MERCADO GLOBAL (SPY + VIX)
        self.analyze_market_health()
        
        # 2. ANALIZAR ACCIONES INDIVIDUALES
        results = []
        for i, ticker in enumerate(self.tickers):
            self.btn_analyze.configure(text=f"⏳ Analizando {ticker} ({i+1}/{len(self.tickers)})...")
            data = self.analyze_stock(ticker)
            if data: results.append(data)
            
        self.after(0, lambda: self.render_results(results))

    def analyze_market_health(self):
        try:
            # Descargamos SPY (S&P 500) y ^VIX (Volatilidad)
            spy = yf.Ticker("SPY").history(period="6mo")
            vix = yf.Ticker("^VIX").history(period="1mo")
            
            spy_price = spy['Close'].iloc[-1]
            spy_sma50 = spy['Close'].rolling(50).mean().iloc[-1]
            spy_sma200 = spy['Close'].rolling(200).mean().iloc[-1]
            vix_now = vix['Close'].iloc[-1]
            
            score = 0
            # Tendencia SPY
            if spy_price > spy_sma50: score += 5
            if spy_price > spy_sma200: score += 5
            
            # Miedo (VIX)
            if vix_now < 20: score += 5    # Mercado tranquilo
            elif vix_now > 30: score -= 10 # Pánico extremo (No comprar)
            
            self.market_score = score # Max 15, Min -10
            
            if score >= 10: 
                self.market_condition = "BULLISH (ALCISTA)"
                self.market_color = "#00ff00"
            elif score >= 0:
                self.market_condition = "NEUTRAL (PRECAUCIÓN)"
                self.market_color = "#ffff00"
            else:
                self.market_condition = "BEARISH (PELIGRO - SOLO CASH)"
                self.market_color = "#ff0000"
                
        except:
            self.market_condition = "ERROR CONEXIÓN"
            self.market_color = "gray"
            self.market_score = 0

    def analyze_stock(self, ticker):
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="1y") # Un año para ver la media de 200
            if len(df) < 200: return None
            
            price = df['Close'].iloc[-1]
            
            # Medias Móviles
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            
            # Indicadores
            rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
            atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
            macd = ta.trend.MACD(df['Close'])
            macd_diff = macd.macd_diff().iloc[-1]
            
            # Volumen
            vol_today = df['Volume'].iloc[-1]
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            rvol = vol_today / vol_avg if vol_avg > 0 else 0

            # --- LÓGICA DE SEÑAL MAESTRA ---
            signal_pct = 0
            
            # 1. Filtro "Golden Rule" (Tendencia de largo plazo)
            if price > sma200: signal_pct += 30
            else: signal_pct -= 50 # Si está bajo la media de 200, Buffett no toca esto.
            
            # 2. Tendencia Medio Plazo
            if price > sma50: signal_pct += 20
            
            # 3. Momentum (MACD & RSI)
            if macd_diff > 0: signal_pct += 15
            if rsi > 50 and rsi < 70: signal_pct += 10 # Zona sana
            if rsi < 30: signal_pct += 25 # Rebote técnico (Dip)
            if rsi > 75: signal_pct -= 40 # Sobrecompra
            
            # 4. Volumen (Confirmación)
            if rvol > 1.5 and price > df['Open'].iloc[-1]: signal_pct += 10 # Volumen subiendo
            
            # 5. AJUSTE MACRO (EL FED)
            # Si el mercado está mal, reducimos la señal de compra drásticamente
            if self.market_score < 0: # Mercado Bajista
                signal_pct -= 50 
            elif self.market_score < 10: # Mercado Neutro
                signal_pct -= 10

            signal_pct = max(-100, min(100, int(signal_pct)))

            # TEXTOS
            if signal_pct >= 80: rec = "💎 COMPRA MAESTRA"
            elif signal_pct >= 40: rec = "🟢 COMPRAR"
            elif signal_pct <= -40: rec = "🔴 VENDER"
            else: rec = "⚪ MANTENER / ESPERAR"

            rec_col = "#00ffea" if signal_pct >= 80 else ("#00ff00" if signal_pct >= 40 else ("#ff0000" if signal_pct <= -40 else "white"))

            return {
                "Ticker": ticker, "Price": price, 
                "Signal": signal_pct, "Rec": rec, "RecCol": rec_col,
                "SMA200": sma200, "RVol": rvol, "RSI": rsi,
                "Stop": price - (2*atr), "Target": price + (3*atr)
            }
        except: return None

    def render_results(self, results):
        self.is_running = False
        self.btn_analyze.configure(state="normal", text="🔍 ANÁLISIS DIARIO")
        
        # Actualizar Header Mercado
        self.lbl_market_status.configure(text=f"MERCADO: {self.market_condition} (Puntuación Fed: {self.market_score})", text_color=self.market_color)

        for w in self.results_area.winfo_children(): w.destroy()
        if not results: return
        results.sort(key=lambda x: x['Signal'], reverse=True)

        # COLUMNAS
        cols = [
            ("Ticker", 60), ("VEREDICTO BUFFETT", 150), ("Confianza", 70), 
            ("Precio", 70), ("Tendencia (200d)", 100), ("RSI", 50), ("Stop Loss", 80)
        ]
        
        h_frame = ctk.CTkFrame(self.results_area, fg_color="#333", height=40)
        h_frame.pack(fill="x", pady=(0,5))
        for txt, w in cols:
            ctk.CTkLabel(h_frame, text=txt, width=w, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)

        for res in results:
            bg = "#111"
            if res['Signal'] >= 80: bg = "#002b2b"
            
            row = ctk.CTkFrame(self.results_area, fg_color=bg)
            row.pack(fill="x", pady=2)
            
            self.mk_cell(row, res['Ticker'], 60, True)
            ctk.CTkLabel(row, text=res['Rec'], width=150, text_color=res['RecCol'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
            self.mk_cell(row, f"{res['Signal']}%", 70, color=res['RecCol'])
            self.mk_cell(row, f"${res['Price']:.2f}", 70)
            
            trend = "ALCISTA" if res['Price'] > res['SMA200'] else "BAJISTA"
            trend_col = "#00ff00" if trend == "ALCISTA" else "#ff5555"
            self.mk_cell(row, trend, 100, color=trend_col)
            
            rsi_col = "white"
            if res['RSI'] > 70: rsi_col = "#ff5555"
            if res['RSI'] < 30: rsi_col = "#00ff00"
            self.mk_cell(row, f"{int(res['RSI'])}", 50, color=rsi_col)
            
            self.mk_cell(row, f"${res['Stop']:.2f}", 80, color="#ffaaaa")

    def mk_cell(self, parent, text, w, bold=False, color="white"):
        f = ctk.CTkFont(weight="bold") if bold else ctk.CTkFont()
        ctk.CTkLabel(parent, text=text, width=w, text_color=color, font=f).pack(side="left", padx=5)

if __name__ == "__main__":
    app = OracleApp()
    app.mainloop()
