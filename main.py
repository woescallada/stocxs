import customtkinter as ctk
import json
import os
import threading
import yfinance as yf
import pandas as pd
import ta
from tkinter import messagebox

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")  # Modo oscuro
ctk.set_default_color_theme("blue")  # Tema azul

FILE_NAME = "mis_acciones.json"

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("🦈 Sniper Stocks - Desktop Edition")
        self.geometry("1100x700")

        # Variables de datos
        self.tickers = self.load_tickers()
        
        # --- LAYOUT PRINCIPAL (2 COLUMNAS) ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. PANEL IZQUIERDO (CONTROLES Y LISTA)
        self.left_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(4, weight=1) # La lista se estira

        # Título
        self.logo_label = ctk.CTkLabel(self.left_frame, text="CONTROL DE MANDO", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Input añadir
        self.entry_ticker = ctk.CTkEntry(self.left_frame, placeholder_text="Ej: TSLA")
        self.entry_ticker.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.btn_add = ctk.CTkButton(self.left_frame, text="+ Añadir Ticker", command=self.add_ticker)
        self.btn_add.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_clear = ctk.CTkButton(self.left_frame, text="🗑️ Borrar Todo", fg_color="#cf3434", hover_color="#8a2323", command=self.clear_all_tickers)
        self.btn_clear.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        # Lista Scrollable de Tickers
        self.lbl_lista = ctk.CTkLabel(self.left_frame, text=f"Mis Stocks ({len(self.tickers)})", anchor="w")
        self.lbl_lista.grid(row=4, column=0, padx=20, pady=(20,0), sticky="w")

        self.scroll_tickers = ctk.CTkScrollableFrame(self.left_frame, label_text="Lista Vigilancia")
        self.scroll_tickers.grid(row=5, column=0, padx=20, pady=10, sticky="nsew")
        
        # Botón Analizar (Abajo del panel izquierdo)
        self.btn_analyze = ctk.CTkButton(self.left_frame, text="⚡ EJECUTAR ANÁLISIS", height=50, font=ctk.CTkFont(size=15, weight="bold"), command=self.start_analysis)
        self.btn_analyze.grid(row=6, column=0, padx=20, pady=20, sticky="ew")

        # 2. PANEL DERECHO (RESULTADOS)
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self.lbl_res = ctk.CTkLabel(self.right_frame, text="Resultados del Análisis", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_res.pack(pady=20, padx=20, anchor="w")

        self.results_area = ctk.CTkScrollableFrame(self.right_frame)
        self.results_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Cargar lista visual inicial
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
        self.lbl_lista.configure(text=f"Mis Stocks ({len(self.tickers)})")

    def add_ticker(self):
        txt = self.entry_ticker.get().upper().strip()
        if txt and txt not in self.tickers:
            self.tickers.append(txt)
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

    # --- INTERFAZ DINÁMICA ---
    def refresh_ticker_list(self):
        # Limpiar lista visual
        for widget in self.scroll_tickers.winfo_children():
            widget.destroy()

        # Crear filas
        for ticker in self.tickers:
            row = ctk.CTkFrame(self.scroll_tickers, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            lbl = ctk.CTkLabel(row, text=ticker, font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=5)
            
            # Botón papelera pequeña
            btn = ctk.CTkButton(row, text="🗑️", width=30, height=20, fg_color="#444", hover_color="#666", 
                                command=lambda t=ticker: self.delete_single_ticker(t))
            btn.pack(side="right")

    # --- LÓGICA DE ANÁLISIS ---
    def start_analysis(self):
        if not self.tickers:
            messagebox.showwarning("Vacío", "No hay acciones para analizar.")
            return
        
        self.btn_analyze.configure(state="disabled", text="Analizando...")
        
        # Limpiar resultados previos
        for widget in self.results_area.winfo_children():
            widget.destroy()
            
        # Ejecutar en hilo secundario para no congelar la ventana
        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        results = []
        for ticker in self.tickers:
            data = self.get_guru_data(ticker)
            if data:
                results.append(data)
        
        # Volver al hilo principal para actualizar GUI
        self.after(0, lambda: self.show_results(results))

    def show_results(self, results):
        self.btn_analyze.configure(state="normal", text="⚡ EJECUTAR ANÁLISIS")
        
        if not results:
            lbl = ctk.CTkLabel(self.results_area, text="No se pudieron obtener datos.")
            lbl.pack(pady=20)
            return

        # Ordenar por Score
        results.sort(key=lambda x: x['Score'], reverse=True)

        # Crear tarjetas de resultados
        headers = ctk.CTkFrame(self.results_area, height=40)
        headers.pack(fill="x", pady=5)
        cols = ["Ticker", "Precio", "Score", "Float", "RVOL", "Cierre %"]
        for col in cols:
            ctk.CTkLabel(headers, text=col, width=100, font=ctk.CTkFont(weight="bold")).pack(side="left", expand=True)

        for res in results:
            # Color basado en score
            color = "#2b2b2b" # Gris oscuro base
            text_col = "white"
            if res['Score'] >= 70: 
                color = "#1e4d2b" # Verde oscuro
                text_col = "#7fff00" # Verde neon
            elif res['Score'] >= 50:
                color = "#4d4d1e" # Amarillo oscuro
                text_col = "#ffff00"

            card = ctk.CTkFrame(self.results_area, fg_color=color)
            card.pack(fill="x", pady=3)
            
            vals = [
                res['Ticker'], 
                f"${res['Precio']:.2f}", 
                str(res['Score']), 
                f"{res['Float']:.1f}M", 
                f"{res['RVOL']:.1f}x", 
                f"{res['Cierre %']:.0f}%"
            ]
            
            for val in vals:
                ctk.CTkLabel(card, text=val, width=100, text_color=text_col).pack(side="left", expand=True)

    def get_guru_data(self, ticker):
        # Lógica resumida de tu script anterior
        try:
            t = yf.Ticker(ticker)
            try: price = t.fast_info['last_price']
            except: 
                h = t.history(period='1d')
                if h.empty: return None
                price = h['Close'].iloc[-1]
            
            info = t.info
            df = t.history(period="6mo")
            if len(df) < 50: return None
            
            f_shares = info.get('floatShares', info.get('marketCap', 0)/price)
            vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            
            # Score simplificado
            score = 0
            if f_shares < 10e6: score += 25
            elif f_shares < 20e6: score += 15
            if vol > f_shares: score += 25
            rvol = vol/avg_vol if avg_vol else 0
            if rvol > 5: score += 20
            elif rvol > 3: score += 10
            
            # Cierre
            high = df['High'].iloc[-1]
            low = df['Low'].iloc[-1]
            close_pos = (df['Close'].iloc[-1] - low) / (high - low) if (high-low) > 0 else 0
            if close_pos > 0.75: score += 15
            
            return {
                "Ticker": ticker, "Precio": price, "Score": score,
                "Float": f_shares/1e6, "RVOL": rvol, "Cierre %": close_pos*100
            }
        except: return None

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()
