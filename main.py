import customtkinter as ctk
import json
import os
import sys
import threading
import time
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

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("🦈 Sniper Stocks PRO (Expert Model + Targets)")
        self.geometry("1600x850") # Aún más ancho para ver el Target

        # Variables
        self.is_running = False
        self.last_update_time = "Nunca"
        self.auto_refresh_active = True 
        
        self.tickers = self.load_data_source()

        # --- LAYOUT PRINCIPAL ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. PANEL IZQUIERDO (CONTROL)
        self.left_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.left_frame, text="🛰️ COMMAND CENTER", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.lbl_source = ctk.CTkLabel(self.left_frame, text="Fuente: Cargando...", text_color="gray")
        self.lbl_source.grid(row=1, column=0, padx=20, pady=(0, 20))

        self.input_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.entry_ticker = ctk.CTkEntry(self.input_frame, placeholder_text="Añadir: AAPL, TSLA")
        self.entry_ticker.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.btn_add = ctk.CTkButton(self.input_frame, text="+", width=40, command=self.add_manual_ticker)
        self.btn_add.pack(side="right")

        self.switch_auto = ctk.CTkSwitch(self.left_frame, text="Auto-Refresh (30m)", command=self.toggle_auto_refresh)
        self.switch_auto.select()
        self.switch_auto.grid(row=3, column=0, padx=20, pady=20)

        self.lbl_count = ctk.CTkLabel(self.left_frame, text=f"Stocks: {len(self.tickers)}", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.lbl_count.grid(row=4, column=0, padx=20, pady=5, sticky="w")

        self.scroll_tickers = ctk.CTkScrollableFrame(self.left_frame)
        self.scroll_tickers.grid(row=5, column=0, padx=20, pady=5, sticky="nsew")

        self.btn_analyze = ctk.CTkButton(self.left_frame, text="⚡ ESCANEAR AHORA", height=50, 
                                         font=ctk.CTkFont(size=16, weight="bold"), 
                                         fg_color="#006400", hover_color="#004d00",
                                         command=self.manual_scan)
        self.btn_analyze.grid(row=6, column=0, padx=20, pady=20, sticky="ew")

        # 2. PANEL DERECHO (RESULTADOS)
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self.top_bar = ctk.CTkFrame(self.right_frame, fg_color="#222", height=50)
        self.top_bar.pack(fill="x")
        self.lbl_status = ctk.CTkLabel(self.top_bar, text="Estado: Esperando...", font=ctk.CTkFont(size=14))
        self.lbl_status.pack(side="left", padx=20, pady=10)
        self.lbl_last_update = ctk.CTkLabel(self.top_bar, text="", text_color="#aaaaaa")
        self.lbl_last_update.pack(side="right", padx=20)

        self.results_area = ctk.CTkScrollableFrame(self.right_frame)
        self.results_area.pack(fill="both", expand=True, padx=20, pady=20)

        self.refresh_ticker_list_ui()
        self.update_source_label()
        self.start_auto_timer()

    # --- LÓGICA DE DATOS ---
    def load_data_source(self):
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE)
                raw_list = df.iloc[:, 0].dropna().astype(str).tolist()
                clean_list = [x.strip().upper() for x in raw_list if x.strip()]
                self.using_excel = True
                return list(set(clean_list))
            except Exception as e:
                messagebox.showerror("Error Excel", f"Error leyendo Excel:\n{e}")
        
        self.using_excel = False
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r") as f:
                return json.load(f)
        return []

    def update_source_label(self):
        if self.using_excel:
            self.lbl_source.configure(text=f"📂 Excel: {EXCEL_FILE}", text_color="#4deeea")
            self.entry_ticker.configure(state="disabled", placeholder_text="Usa el Excel")
            self.btn_add.configure(state="disabled")
        else:
            self.lbl_source.configure(text="📝 Manual (JSON)", text_color="#ffb84d")

    def save_json(self):
        if not self.using_excel:
            with open(JSON_FILE, "w") as f:
                json.dump(self.tickers, f)

    def add_manual_ticker(self):
        if self.using_excel: return
        txt = self.entry_ticker.get().upper().replace(',', ' ')
        new = [x.strip() for x in txt.split() if x.strip()]
        for n in new:
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

    def toggle_auto_refresh(self):
        self.auto_refresh_active = bool(self.switch_auto.get())

    def start_auto_timer(self):
        if self.auto_refresh_active and not self.is_running: self.manual_scan()
        self.after(1800000, self.start_auto_timer) 

    # --- MOTOR DE ANÁLISIS ---
    def manual_scan(self):
        if self.is_running: return
        if self.using_excel:
            self.tickers = self.load_data_source()
            self.refresh_ticker_list_ui()
        if not self.tickers:
            messagebox.showwarning("Vacío", "No hay acciones.")
            return

        self.is_running = True
        self.btn_analyze.configure(state="disabled", text="⏳ ESCANEANDO...", fg_color="#555")
        self.lbl_status.configure(text="Analizando mercado...", text_color="yellow")
        threading.Thread(target=self.run_analysis_thread, daemon=True).start()

    def run_analysis_thread(self):
        results = []
        total = len(self.tickers)
        for i, ticker in enumerate(self.tickers):
            self.lbl_status.configure(text=f"Analizando {i+1}/{total}: {ticker}")
            data = self.analyze_expert_mode(ticker)
            if data: results.append(data)
        self.after(0, lambda: self.render_results(results))

    def analyze_expert_mode(self, ticker):
        try:
            t = yf.Ticker(ticker)
            try: price = t.fast_info['last_price']
            except: 
                h = t.history(period='1d')
                if h.empty: return None
                price = h['Close'].iloc[-1]

            df = t.history(period="1y") 
            if len(df) < 50: return None
            
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else 0
            rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
            macd = ta.trend.MACD(df['Close'])
            macd_line = macd.macd().iloc[-1]
            macd_signal = macd.macd_signal().iloc[-1]
            atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
            vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            rvol = vol / avg_vol if avg_vol > 0 else 0

            # --- CÁLCULO DE TECHOS Y SUELOS (TARGETS) ---
            # Stop Loss (Suelo) = Precio - 2x Volatilidad
            stop_loss = price - (2.0 * atr)
            
            # Target (Techo) = Precio + 2.5x Volatilidad (Ratio Beneficio/Riesgo > 1)
            take_profit = price + (2.5 * atr)
            
            potential_gain = ((take_profit - price) / price) * 100
            
            # --- SCORE & LOGICA ---
            score = 0
            trend_state = "Neutral"
            if price > sma50:
                score += 20
                if sma50 > sma200 and sma200 > 0:
                    score += 15
                    trend_state = "ALCISTA"
                else: trend_state = "RECUPERANDO"
            elif price < sma50:
                trend_state = "BAJISTA"
                score -= 10
            
            if macd_line > macd_signal: score += 15
            else: score -= 5
            
            if 40 <= rsi <= 60: score += 10
            elif rsi < 30: score += 5
            elif rsi > 70: score -= 15
            
            if rvol > 3: score += 15

            # --- VEREDICTO FINAL ---
            verdict = "NEUTRAL"
            verdict_color = "white"

            if rsi > 75:
                verdict = "⚠️ TECHO (RSI)"
                verdict_color = "#ff5555"
            elif trend_state == "BAJISTA" and macd_line < macd_signal:
                verdict = "❌ EVITAR"
                verdict_color = "#ff0000"
            else:
                if score >= 75 and trend_state == "ALCISTA":
                    verdict = "💎 GOLD"
                    verdict_color = "#00ffea"
                elif rvol > 3 and macd_line > macd_signal:
                    verdict = "🚀 EXPLOSIVA"
                    verdict_color = "#ffff00"
                elif trend_state == "RECUPERANDO" and macd_line > macd_signal:
                    verdict = "🔄 CAMBIO CICLO"
                    verdict_color = "#ff00ff"
                elif score < 40:
                    verdict = "💩 BASURA"
                    verdict_color = "#888888"

            return {
                "Ticker": ticker, "Precio": price, "Score": int(score),
                "Trend": trend_state, "RSI": rsi, "Verdict": verdict, "VerdictColor": verdict_color,
                "Stop": stop_loss, "Target": take_profit, "Potencial": potential_gain
            }

        except Exception as e: return None

    def render_results(self, results):
        self.is_running = False
        self.btn_analyze.configure(state="normal", text="⚡ ESCANEAR AHORA", fg_color="#006400")
        self.last_update_time = datetime.now().strftime("%H:%M")
        self.lbl_last_update.configure(text=f"Última act: {self.last_update_time}")
        self.lbl_status.configure(text="Listo.", text_color="white")

        for w in self.results_area.winfo_children(): w.destroy()

        if not results: return
        results.sort(key=lambda x: x['Score'], reverse=True)

        # CABECERAS
        # Añadimos Target y Potencial
        headers = ["Ticker", "VEREDICTO", "Score", "Precio", "Target 🎯", "Potencial", "Stop Loss"]
        h_frame = ctk.CTkFrame(self.results_area, fg_color="#333", height=40)
        h_frame.pack(fill="x", pady=(0, 5))
        
        widths = [60, 140, 50, 80, 80, 70, 80]
        for i, h in enumerate(headers):
            ctk.CTkLabel(h_frame, text=h, width=widths[i], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=2)

        # FILAS
        for res in results:
            bg = "#222"
            if "GOLD" in res['Verdict']: bg = "#0f3d3d"
            
            row = ctk.CTkFrame(self.results_area, fg_color=bg)
            row.pack(fill="x", pady=2)
            
            self.mk_cell(row, res['Ticker'], 60, True)
            
            verdict_lbl = ctk.CTkLabel(row, text=res['Verdict'], width=140, text_color=res['VerdictColor'], font=ctk.CTkFont(weight="bold", size=13))
            verdict_lbl.pack(side="left", padx=2)
            
            self.mk_cell(row, str(res['Score']), 50)
            self.mk_cell(row, f"${res['Precio']:.2f}", 80)
            
            # Target (Verde Neon)
            self.mk_cell(row, f"${res['Target']:.2f}", 80, color="#7fff00", bold=True)
            
            # Potencial %
            self.mk_cell(row, f"+{res['Potencial']:.1f}%", 70, color="#7fff00")
            
            # Stop Loss (Rojo Claro)
            self.mk_cell(row, f"${res['Stop']:.2f}", 80, color="#ffaaaa")

    def mk_cell(self, parent, text, w, bold=False, color="white"):
        f = ctk.CTkFont(weight="bold") if bold else ctk.CTkFont()
        ctk.CTkLabel(parent, text=text, width=w, text_color=color, font=f).pack(side="left", padx=2)

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()
