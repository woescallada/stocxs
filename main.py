import customtkinter as ctk
import json
import os
import threading
import yfinance as yf
import pandas as pd
import ta
import requests
import io
from tkinter import messagebox
from datetime import datetime

# --- CONFIGURACIÓN ESTILO ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

JSON_FILE = "mis_acciones.json"
EXCEL_FILE = "stocks.xlsx"

# --- LISTA UNIVERSO (Blue Chips) ---
MARKET_UNIVERSE = [
    "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL", "META", "NFLX",
    "JPM", "BAC", "LLY", "NVO", "XOM", "CVX", "DIS", "KO", "MCD", "UBER"
]

# --- LISTA BACKUP PENNIES (Por si falla el scraper) ---
PENNY_BACKUP = [
    "MARA", "RIOT", "CLSK", "HUT", "BITF", "IREN", # Crypto Miners
    "SOFI", "PLTR", "LCID", "RIVN", "OPEN", "DNA", # Tech/Growth
    "AMC", "GME", "BB", "TLRY", "SNDL", "CGC", # Meme/Weed
    "MULN", "NKLA", "FSR", "NIO", "XPEV" # EV Risky
]

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
        self.title("🏛️ THE ORACLE: Gem Hunter Edition v4")
        self.geometry("1750x950")

        self.running_tasks = {"portfolio": False, "scanner": False, "pennies": False}
        self.market_score = 0
        self.market_condition = "NEUTRAL"
        
        self.portfolio_tickers = []
        self.load_data()

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_portfolio = self.tabview.add("💼 MI CARTERA")
        self.tab_scanner = self.tabview.add("🌎 MERCADO (Blue Chips)")
        self.tab_pennies = self.tabview.add("💎 MINA DE GEMAS (Penny Stocks)")

        self.setup_portfolio_tab()
        self.setup_scanner_tab()
        self.setup_pennies_tab()
        
        threading.Thread(target=self.analyze_market_health, daemon=True).start()

    # ==========================================
    # DATA HANDLING
    # ==========================================
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
        self.portfolio_tickers = list(loaded)

    def save_json(self):
        try:
            with open(JSON_FILE, "w") as f: json.dump(self.portfolio_tickers, f)
        except: pass

    # ==========================================
    # 1. MI CARTERA
    # ==========================================
    def setup_portfolio_tab(self):
        self.tab_portfolio.grid_columnconfigure(1, weight=1)
        self.tab_portfolio.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self.tab_portfolio, width=280)
        left.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(left, text="GESTIÓN", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        
        inp = ctk.CTkFrame(left, fg_color="transparent")
        inp.pack(pady=10, padx=20, fill="x")
        self.entry_ticker = ctk.CTkEntry(inp, placeholder_text="Añadir...")
        self.entry_ticker.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(inp, text="+", width=30, command=self.add_manual_ticker).pack(side="right", padx=(5,0))

        self.scroll_portfolio = ctk.CTkScrollableFrame(left)
        self.scroll_portfolio.pack(fill="both", expand=True, padx=20, pady=10)
        self.refresh_portfolio_ui()

        self.btn_run_portfolio = ctk.CTkButton(left, text="🔍 ANALIZAR LISTA", height=50, fg_color="#006400", command=self.run_portfolio)
        self.btn_run_portfolio.pack(padx=20, pady=20, fill="x")

        right = ctk.CTkFrame(self.tab_portfolio, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.lbl_mkt_p = ctk.CTkLabel(right, text="Mercado: ...", font=ctk.CTkFont(weight="bold"))
        self.lbl_mkt_p.pack(pady=10)
        self.res_portfolio = ctk.CTkScrollableFrame(right)
        self.res_portfolio.pack(fill="both", expand=True, padx=20, pady=10)

    def add_manual_ticker(self):
        t = self.entry_ticker.get().upper().replace(',', ' ')
        for n in t.split():
            if n not in self.portfolio_tickers: self.portfolio_tickers.append(n)
        self.save_json()
        self.refresh_portfolio_ui()
        self.entry_ticker.delete(0, 'end')

    def remove_ticker(self, t):
        if t in self.portfolio_tickers:
            self.portfolio_tickers.remove(t)
            self.save_json()
            self.refresh_portfolio_ui()

    def refresh_portfolio_ui(self):
        for w in self.scroll_portfolio.winfo_children(): w.destroy()
        for t in self.portfolio_tickers:
            r = ctk.CTkFrame(self.scroll_portfolio, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=t, width=60, anchor="w").pack(side="left")
            ctk.CTkButton(r, text="x", width=25, fg_color="#442222", hover_color="red", command=lambda x=t: self.remove_ticker(x)).pack(side="right")

    # ==========================================
    # 2. MERCADO (SCANNER)
    # ==========================================
    def setup_scanner_tab(self):
        self.tab_scanner.grid_columnconfigure(0, weight=1)
        self.tab_scanner.grid_rowconfigure(1, weight=1)
        
        head = ctk.CTkFrame(self.tab_scanner, height=60, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        self.btn_run_scanner = ctk.CTkButton(head, text="🚀 ESCANEAR TOP 50 (BLUE CHIPS)", height=40, 
                                             fg_color="#005577", command=self.run_scanner)
        self.btn_run_scanner.pack(side="left", fill="x", expand=True)
        self.lbl_status_scanner = ctk.CTkLabel(head, text="")
        self.lbl_status_scanner.pack(side="right", padx=20)

        self.res_scanner = ctk.CTkScrollableFrame(self.tab_scanner)
        self.res_scanner.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

    # ==========================================
    # 3. GEMAS (PENNY STOCKS)
    # ==========================================
    def setup_pennies_tab(self):
        self.tab_pennies.grid_columnconfigure(0, weight=1)
        self.tab_pennies.grid_rowconfigure(1, weight=1)
        
        head = ctk.CTkFrame(self.tab_pennies, height=60, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        # Botón especial
        self.btn_run_pennies = ctk.CTkButton(head, text="⛏️ MINAR GEMAS (BUSCAR EN INTERNET)", height=40, 
                                             fg_color="#800080", hover_color="#5a005a", # Morado
                                             font=ctk.CTkFont(weight="bold"),
                                             command=self.run_pennies)
        self.btn_run_pennies.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(head, text="⚠️ ALTO RIESGO", text_color="orange").pack(side="left", padx=10)
        self.lbl_status_pennies = ctk.CTkLabel(head, text="Listo para minar.")
        self.lbl_status_pennies.pack(side="right", padx=20)

        self.res_pennies = ctk.CTkScrollableFrame(self.tab_pennies)
        self.res_pennies.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

    # ==========================================
    # WEBSCRAPER DE PENNIES
    # ==========================================
    def fetch_live_pennies(self):
        """Intenta descargar las acciones más calientes del momento."""
        found_tickers = []
        try:
            # Opción A: StockAnalysis (Suele ser amigable)
            url = "https://stockanalysis.com/markets/gainers/penny-stocks/"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                dfs = pd.read_html(io.StringIO(r.text))
                if dfs:
                    df = dfs[0]
                    # Asumimos que la columna símbolo es la primera o se llama 'Symbol'
                    if 'Symbol' in df.columns: found_tickers = df['Symbol'].tolist()
                    elif 'Ticker' in df.columns: found_tickers = df['Ticker'].tolist()
                    else: found_tickers = df.iloc[:, 0].tolist()
        except Exception as e:
            print(f"Scraper error: {e}")
        
        # Limpiar y filtrar
        clean = [str(x).strip().upper() for x in found_tickers if str(x).isalpha()]
        return list(set(clean))

    # ==========================================
    # ANALYSIS CORE
    # ==========================================
    def analyze_market_health(self):
        try:
            spy = yf.Ticker("SPY").history(period="6mo")
            vix = yf.Ticker("^VIX").history(period="1mo")
            score = 0
            if spy['Close'].iloc[-1] > spy['Close'].rolling(200).mean().iloc[-1]: score += 10
            if vix['Close'].iloc[-1] < 20: score += 5
            elif vix['Close'].iloc[-1] > 30: score -= 10
            
            self.market_score = score
            if score >= 10: self.market_condition, self.market_color = "ALCISTA 🟢", "#00ff00"
            elif score >= 0: self.market_condition, self.market_color = "NEUTRAL 🟡", "#ffff00"
            else: self.market_condition, self.market_color = "BAJISTA 🔴", "#ff0000"
            
            self.lbl_mkt_p.configure(text=f"MERCADO: {self.market_condition}", text_color=self.market_color)
        except: pass

    def analyze_stock(self, ticker):
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="1y")
            if len(df) < 50: return None # Pennies pueden tener menos historia
            
            price = df['Close'].iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) > 200 else sma50
            rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
            atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
            macd = ta.trend.MACD(df['Close'])
            macd_diff = macd.macd_diff().iloc[-1]
            
            # Vol
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            rvol = df['Volume'].iloc[-1] / vol_avg if vol_avg > 0 else 0

            # Signal Logic
            signal = 0
            if price > sma200: signal += 20
            else: signal -= 20 # En pennies no penalizamos tanto estar bajo la 200, son volátiles
            
            if price > sma50: signal += 20
            if macd_diff > 0: signal += 15
            if rvol > 2: signal += 25 # VOLUMEN ES REY EN PENNIES
            
            if rsi < 30: signal += 30
            if rsi > 80: signal -= 40
            
            # Ajuste Mercado
            if self.market_score < 0: signal -= 30

            signal = max(-100, min(100, int(signal)))

            rec, col = "MANTENER", "white"
            if signal >= 80: rec, col = "💎 GEMA", "#00ffea"
            elif signal >= 40: rec, col = "🟢 COMPRA", "#00ff00"
            elif signal <= -40: rec, col = "🔴 VENTA", "#ff0000"

            stop = price - (2.5 * atr) # Stop más amplio para pennies
            target = price + (4.0 * atr) # Target más ambicioso
            
            risk = ((price - stop)/price)*100
            reward = ((target - price)/price)*100

            return {
                "Ticker": ticker, "Price": price, "Signal": signal, 
                "Rec": rec, "RecCol": col, "Stop": stop, "Target": target,
                "Risk": risk, "Reward": reward, "RVol": rvol
            }
        except: return None

    # ==========================================
    # THREADS DE EJECUCIÓN
    # ==========================================
    def run_portfolio(self):
        if self.running_tasks["portfolio"]: return
        self.running_tasks["portfolio"] = True
        self.btn_run_portfolio.configure(state="disabled", text="⏳...")
        threading.Thread(target=self.thread_generic, args=(self.portfolio_tickers, self.res_portfolio, "portfolio", self.btn_run_portfolio, "🔍 ANALIZAR LISTA"), daemon=True).start()

    def run_scanner(self):
        if self.running_tasks["scanner"]: return
        self.running_tasks["scanner"] = True
        self.btn_run_scanner.configure(state="disabled", text="⏳ ESCANEANDO...")
        threading.Thread(target=self.thread_generic, args=(MARKET_UNIVERSE, self.res_scanner, "scanner", self.btn_run_scanner, "🚀 ESCANEAR TOP 50"), daemon=True).start()

    def run_pennies(self):
        if self.running_tasks["pennies"]: return
        self.running_tasks["pennies"] = True
        self.btn_run_pennies.configure(state="disabled", text="⛏️ MINANDO INTERNET...")
        self.lbl_status_pennies.configure(text="Conectando con el mercado...")
        threading.Thread(target=self.thread_pennies, daemon=True).start()

    def thread_pennies(self):
        # 1. Scrape
        live_tickers = self.fetch_live_pennies()
        
        # 2. Combine with backup if empty or few
        if len(live_tickers) < 5:
            live_tickers.extend(PENNY_BACKUP)
        
        # Eliminar duplicados
        target_list = list(set(live_tickers))
        self.lbl_status_pennies.configure(text=f"Analizando {len(target_list)} gemas potenciales...")
        
        # 3. Analyze
        results = []
        for t in target_list:
            res = self.analyze_stock(t)
            # Solo mostrar si tienen volumen interesante o señal positiva
            if res and (res['RVol'] > 1.5 or res['Signal'] > 20): 
                results.append(res)
        
        results.sort(key=lambda x: x['Signal'], reverse=True)
        top_20 = results[:30]

        self.after(0, lambda: self.render_table(top_20, self.res_pennies, is_penny=True))
        self.running_tasks["pennies"] = False
        self.after(0, lambda: self.btn_run_pennies.configure(state="normal", text="⛏️ MINAR GEMAS"))
        self.after(0, lambda: self.lbl_status_pennies.configure(text=f"Encontradas: {len(top_20)}"))

    def thread_generic(self, ticker_list, frame, task_name, btn, btn_text):
        results = []
        for t in ticker_list:
            res = self.analyze_stock(t)
            if res: results.append(res)
        
        results.sort(key=lambda x: x['Signal'], reverse=True)
        if task_name == "scanner": results = results[:20]

        self.after(0, lambda: self.render_table(results, frame))
        self.running_tasks[task_name] = False
        self.after(0, lambda: btn.configure(state="normal", text=btn_text))

    # ==========================================
    # RENDER
    # ==========================================
    def render_table(self, results, frame, is_penny=False):
        for w in frame.winfo_children(): w.destroy()
        
        cols = [("Ticker", 60, "Símbolo"), ("ASESOR", 120, "Opinión"), ("Precio", 70, "Actual"),
                ("R.Vol", 50, "Volumen Relativo"), ("STOP", 70, "Salida"), ("TARGET", 70, "Meta"),
                ("Riesgo", 60, "% Perdida"), ("Beneficio", 60, "% Ganancia")]
        
        h = ctk.CTkFrame(frame, fg_color="#333", height=40)
        h.pack(fill="x", pady=(0,5))
        for txt, w, tip in cols:
            lbl = ctk.CTkLabel(h, text=txt, width=w, font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=5)
            ToolTip(lbl, tip)

        for res in results:
            bg = "#111"
            if res['Signal'] >= 80: bg = "#002b2b"
            if is_penny and res['RVol'] > 3: bg = "#2b002b" # Fondo morado para vol explosivo

            row = ctk.CTkFrame(frame, fg_color=bg)
            row.pack(fill="x", pady=2)

            self.mk_cell(row, res['Ticker'], 60, True)
            ctk.CTkLabel(row, text=f"{res['Rec']} ({res['Signal']}%)", width=120, text_color=res['RecCol'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
            self.mk_cell(row, f"${res['Price']:.2f}", 70)
            
            rv_col = "#d000ff" if res['RVol'] > 3 else "white"
            self.mk_cell(row, f"{res['RVol']:.1f}x", 50, color=rv_col, bold=True)
            
            self.mk_cell(row, f"${res['Stop']:.2f}", 70, color="#ff7777")
            self.mk_cell(row, f"${res['Target']:.2f}", 70, color="#00ff00", bold=True)
            self.mk_cell(row, f"-{res['Risk']:.1f}%", 60, color="#ffaaaa")
            self.mk_cell(row, f"+{res['Reward']:.1f}%", 60, color="#ccffcc")

    def mk_cell(self, parent, text, w, bold=False, color="white"):
        f = ctk.CTkFont(weight="bold") if bold else ctk.CTkFont()
        ctk.CTkLabel(parent, text=text, width=w, text_color=color, font=f).pack(side="left", padx=5)

if __name__ == "__main__":
    app = OracleApp()
    app.mainloop()
