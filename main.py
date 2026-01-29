import customtkinter as ctk
import json
import os
import threading
import yfinance as yf
import pandas as pd
import ta
from tkinter import messagebox

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

FILE_NAME = "mis_acciones.json"

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("🦈 Sniper Stocks Pro - Desktop")
        self.geometry("1300x800") # Un poco más grande para que quepan las columnas

        # Variables de datos
        self.tickers = self.load_tickers()
        
        # --- LAYOUT PRINCIPAL ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================================
        # 1. PANEL IZQUIERDO (LISTA DE VIGILANCIA)
        # ==========================================
        self.left_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(4, weight=1)

        # Título
        self.logo_label = ctk.CTkLabel(self.left_frame, text="📡 CENTER CONTROL", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Input añadir (Soporta listas)
        self.lbl_add = ctk.CTkLabel(self.left_frame, text="Añadir Tickers (separados por coma):", anchor="w")
        self.lbl_add.grid(row=1, column=0, padx=20, pady=(10,0), sticky="w")
        
        self.entry_ticker = ctk.CTkEntry(self.left_frame, placeholder_text="Ej: TSLA, AAPL, AMC")
        self.entry_ticker.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        # Botones de Gestión
        self.btn_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        
        self.btn_add = ctk.CTkButton(self.btn_frame, text="➕ Añadir", width=100, command=self.add_tickers)
        self.btn_add.pack(side="left", padx=(0, 5))
        
        self.btn_clear = ctk.CTkButton(self.btn_frame, text="🗑️ Todo", width=80, fg_color="#cf3434", hover_color="#8a2323", command=self.clear_all_tickers)
        self.btn_clear.pack(side="right")

        # Lista Scrollable
        self.lbl_lista = ctk.CTkLabel(self.left_frame, text=f"📋 Mis Stocks ({len(self.tickers)})", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.lbl_lista.grid(row=4, column=0, padx=20, pady=(20,5), sticky="w")

        self.scroll_tickers = ctk.CTkScrollableFrame(self.left_frame, label_text="Lista de Vigilancia")
        self.scroll_tickers.grid(row=5, column=0, padx=20, pady=5, sticky="nsew")
        
        # Botón Analizar
        self.btn_analyze = ctk.CTkButton(self.left_frame, text="⚡ EJECUTAR ANÁLISIS", height=50, 
                                         font=ctk.CTkFont(size=16, weight="bold"), 
                                         fg_color="#006400", hover_color="#004d00", # Verde oscuro
                                         command=self.start_analysis)
        self.btn_analyze.grid(row=6, column=0, padx=20, pady=20, sticky="ew")

        # ==========================================
        # 2. PANEL DERECHO (RESULTADOS)
        # ==========================================
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        # Cabecera Derecha
        self.top_bar = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=20)
        
        self.lbl_res = ctk.CTkLabel(self.top_bar, text="Resultados del Análisis", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_res.pack(side="left")

        # Área de Resultados (Scrollable)
        self.results_area = ctk.CTkScrollableFrame(self.right_frame)
        self.results_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Cargar lista inicial
        self.refresh_ticker_list()

    # --- GESTIÓN DE DATOS ---
    def load_tickers(self):
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, "r") as f:
                return json.load(f)
        return []

    def save_tickers(self):
        with open(FILE_NAME, "w") as f:
            json.dump(self.tickers, f)
        self.lbl_lista.configure(text=f"📋 Mis Stocks ({len(self.tickers)})")

    def add_tickers(self):
        raw_text = self.entry_ticker.get()
        if not raw_text: return
        
        # Separar por comas o espacios
        new_items = [t.strip().upper() for t in raw_text.replace(',', ' ').split() if t.strip()]
        
        added_count = 0
        for item in new_items:
            if item not in self.tickers:
                self.tickers.append(item)
                added_count += 1
        
        if added_count > 0:
            self.save_tickers()
            self.refresh_ticker_list()
            self.entry_ticker.delete(0, "end")

    def delete_single_ticker(self, ticker_to_del):
        if ticker_to_del in self.tickers:
            self.tickers.remove(ticker_to_del)
            self.save_tickers()
            self.refresh_ticker_list()

    def clear_all_tickers(self):
        if not self.tickers: return
        self.tickers = []
        self.save_tickers()
        self.refresh_ticker_list()

    # --- INTERFAZ DINÁMICA (LISTA IZQUIERDA) ---
    def refresh_ticker_list(self):
        for widget in self.scroll_tickers.winfo_children():
            widget.destroy()

        for ticker in self.tickers:
            row = ctk.CTkFrame(self.scroll_tickers, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            # Etiqueta Ticker
            lbl = ctk.CTkLabel(row, text=f"🔹 {ticker}", font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=5)
            
            # Botón Borrar Individual (X roja)
            btn = ctk.CTkButton(row, text="❌", width=30, height=20, 
                                fg_color="transparent", text_color="#ff5555", hover_color="#330000",
                                font=ctk.CTkFont(weight="bold"),
                                command=lambda t=ticker: self.delete_single_ticker(t))
            btn.pack(side="right")

    # --- LÓGICA DE ANÁLISIS ---
    def start_analysis(self):
        if not self.tickers:
            messagebox.showwarning("Vacío", "Añade acciones a la lista primero.")
            return
        
        self.btn_analyze.configure(state="disabled", text="⏳ Analizando...", fg_color="#555")
        
        # Limpiar tabla previa
        for widget in self.results_area.winfo_children():
            widget.destroy()
            
        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        results = []
        total = len(self.tickers)
        for i, ticker in enumerate(self.tickers):
            # Actualizar botón con progreso
            self.btn_analyze.configure(text=f"⏳ Analizando ({i+1}/{total})...")
            data = self.get_guru_data(ticker)
            if data:
                results.append(data)
        
        self.after(0, lambda: self.show_results(results))

    def show_results(self, results):
        self.btn_analyze.configure(state="normal", text="⚡ EJECUTAR ANÁLISIS", fg_color="#006400")
        
        if not results:
            ctk.CTkLabel(self.results_area, text="❌ No se obtuvieron datos. Revisa tu conexión.").pack(pady=20)
            return

        results.sort(key=lambda x: x['Score'], reverse=True)

        # --- CABECERA DE LA TABLA ---
        headers_frame = ctk.CTkFrame(self.results_area, height=40, fg_color="#333")
        headers_frame.pack(fill="x", pady=(0, 5))
        
        cols = [("Ticker", 60), ("Score", 50), ("Precio", 70), ("Stop Loss", 70), 
                ("Riesgo", 60), ("Float", 70), ("RVOL", 50), ("RSI", 50), ("Cierre %", 60)]
        
        for col_name, width in cols:
            ctk.CTkLabel(headers_frame, text=col_name, width=width, font=ctk.CTkFont(weight="bold")).pack(side="left", expand=True, padx=2)

        # --- FILAS DE DATOS ---
        for res in results:
            # 1. Color de FONDO según Score
            bg_color = "#2b2b2b" # Gris base
            if res['Score'] >= 80: bg_color = "#1e4d2b" # Verde Fuerte (Top)
            elif res['Score'] >= 60: bg_color = "#5c5c00" # Amarillo oscuro (Medio)
            
            row = ctk.CTkFrame(self.results_area, fg_color=bg_color)
            row.pack(fill="x", pady=2)
            
            # 2. Colores de TEXTO específicos (Indicadores)
            color_float = "#ff00ff" if res['is_low_float'] else "white" # Magenta si es Low Float
            color_rvol = "#00ffff" if res['is_high_rvol'] else "white" # Cian si hay volumen
            
            # Crear celdas
            self.create_cell(row, res['Ticker'], width=60, bold=True)
            self.create_cell(row, str(res['Score']), width=50, bold=True)
            self.create_cell(row, f"${res['Precio']:.2f}", width=70)
            self.create_cell(row, f"${res['Stop Loss']:.2f}", width=70, color="#ff9999") # Rojo claro
            self.create_cell(row, f"{res['Riesgo %']:.1f}%", width=60)
            self.create_cell(row, f"{res['Float']:.1f}M", width=70, color=color_float, bold=True)
            self.create_cell(row, f"{res['RVOL']:.1f}x", width=50, color=color_rvol, bold=True)
            self.create_cell(row, f"{res['RSI']:.0f}", width=50)
            self.create_cell(row, f"{res['Cierre %']:.0f}%", width=60)

    def create_cell(self, parent, text, width, color="white", bold=False):
        font = ctk.CTkFont(weight="bold") if bold else ctk.CTkFont()
        lbl = ctk.CTkLabel(parent, text=text, width=width, text_color=color, font=font)
        lbl.pack(side="left", expand=True, padx=2)

    def get_guru_data(self, ticker):
        try:
            t = yf.Ticker(ticker)
            # Intentar obtener precio rápido
            try: price = t.fast_info['last_price']
            except: 
                h = t.history(period='1d')
                if h.empty: return None
                price = h['Close'].iloc[-1]
            
            info = t.info
            df = t.history(period="6mo")
            if len(df) < 50: return None
            
            # Datos fundamentales y técnicos
            f_shares = info.get('floatShares', None)
            m_cap = info.get('marketCap', 0)
            if f_shares is None and price > 0: f_shares = m_cap / price 
            
            vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            
            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) > 200 else 0
            atr = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14).iloc[-1]
            rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
            
            # Cierre relativo
            day_range = df['High'].iloc[-1] - df['Low'].iloc[-1]
            close_pos = (df['Close'].iloc[-1] - df['Low'].iloc[-1]) / day_range if day_range > 0 else 0
            
            # --- SCORING ---
            score = 0
            is_low_float = False
            is_high_rvol = False
            
            # Float
            if f_shares and f_shares < 10e6: 
                score += 25
                is_low_float = True
            elif f_shares and f_shares < 20e6: score += 15
            
            # Volume
            if f_shares and vol > f_shares: score += 25
            rvol = vol/avg_vol if avg_vol else 0
            if rvol > 5: 
                score += 20
                is_high_rvol = True
            elif rvol > 3: score += 10
            
            # Tendencia
            if price > sma20 and price > sma50: score += 10
            if price > sma200: score += 5
            if close_pos > 0.75: score += 15
            
            stop_loss = max(price - (2.5 * atr), 0.01)
            risk = ((price - stop_loss) / price) * 100
            
            return {
                "Ticker": ticker, "Precio": price, "Score": score,
                "Float": (f_shares/1e6) if f_shares else 0, 
                "RVOL": rvol, "RSI": rsi, "Cierre %": close_pos*100,
                "Stop Loss": stop_loss, "Riesgo %": risk,
                "is_low_float": is_low_float, "is_high_rvol": is_high_rvol
            }
        except: return None

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()
