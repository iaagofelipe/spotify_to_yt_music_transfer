import os
import csv
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Configuração inicial
# -------------------------------------------------------------------

load_dotenv()  # carrega .env com SPOTIPY_*

CSV_DIR = "csv"
os.makedirs(CSV_DIR, exist_ok=True)

HEADERS_FILE_DEFAULT = "browser.json"


# -------------------------------------------------------------------
# Helpers de backend (Spotify / YouTube)
# -------------------------------------------------------------------

def extract_playlist_id(playlist_id_or_url: str) -> str:
    """
    Aceita tanto o ID puro quanto a URL da playlist do Spotify.
    Ex:
      - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
        -> 37i9dQZF1DXcBWIGoYBM5M
    """
    if "open.spotify.com" in playlist_id_or_url:
        parts = playlist_id_or_url.split("playlist/")
        if len(parts) > 1:
            return parts[1].split("?")[0]
    return playlist_id_or_url.strip()


def get_spotify_client() -> Spotify:
    """
    Cria o cliente Spotify com os escopos necessários.
    """
    return Spotify(
        auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            scope="playlist-read-private user-library-read",
        )
    )


def get_liked_tracks(sp: Spotify):
    """
    Retorna a lista de 'músicas curtidas' (saved tracks) do usuário.
    """
    results = sp.current_user_saved_tracks(limit=50)
    tracks = results["items"]

    while results["next"]:
        results = sp.next(results)
        tracks.extend(results["items"])

    return tracks


def export_spotify_playlist_to_csv(playlist_id_or_url: str, csv_path: str, log):
    """
    Exporta uma playlist NORMAL do Spotify para CSV (colunas: Artist, Track).
    """
    sp = get_spotify_client()
    playlist_id = extract_playlist_id(playlist_id_or_url)

    def get_playlist_tracks(pid):
        results = sp.playlist_tracks(pid)
        tracks_local = results["items"]
        while results["next"]:
            results = sp.next(results)
            tracks_local.extend(results["items"])
        return tracks_local

    log(f"\nLendo playlist do Spotify ({playlist_id})...")
    tracks = get_playlist_tracks(playlist_id)
    log(f"Encontradas {len(tracks)} faixas. Salvando em CSV...")

    with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Artist", "Track"])  # cabeçalho

        for item in tracks:
            track = item.get("track")
            if not track:
                continue
            artist_name = track["artists"][0]["name"]
            track_name = track["name"]
            writer.writerow([artist_name, track_name])

    log(f"✅ Exportação concluída! {len(tracks)} músicas salvas em '{csv_path}'.")


def export_liked_songs_to_csv(csv_path: str, log):
    """
    Exporta as MÚSICAS CURTIDAS do usuário para CSV.
    """
    sp = get_spotify_client()

    log("\nLendo MINHAS MÚSICAS CURTIDAS do Spotify...")
    tracks = get_liked_tracks(sp)
    log(f"Encontradas {len(tracks)} faixas curtidas. Salvando em CSV...")

    with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Artist", "Track"])  # cabeçalho

        for item in tracks:
            track = item.get("track")
            if not track:
                continue
            artist_name = track["artists"][0]["name"]
            track_name = track["name"]
            writer.writerow([artist_name, track_name])

    log(f"✅ Exportação concluída! {len(tracks)} músicas curtidas salvas em '{csv_path}'.")


def import_csv_to_ytmusic(
    csv_path: str,
    new_playlist_name: str,
    headers_file: str,
    sleep_seconds: float,
    log,
):
    """
    Cria uma nova playlist no YouTube Music e importa as músicas do CSV.
    Usa autenticação baseada em headers.
    Retorna (playlist_id, lista_not_found).
    """
    if not os.path.exists(headers_file):
        raise FileNotFoundError(
            f"Arquivo de headers '{headers_file}' não encontrado. "
            f"Garanta que gerou o browser.json com 'ytmusicapi browser'."
        )

    yt = YTMusic(headers_file)

    log(f"\nCriando playlist '{new_playlist_name}' no YouTube Music...")
    playlist_id = yt.create_playlist(
        title=new_playlist_name,
        description="Importada automaticamente a partir de uma playlist do Spotify.",
    )
    log(f"✅ Playlist criada! ID: {playlist_id}")

    added = 0
    not_found = []

    with open(csv_path, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            artist = row["Artist"]
            track = row["Track"]
            query = f"{artist} {track}"

            log(f"🔎 Buscando: {query}...")
            try:
                results = yt.search(query, filter="songs")
                if results:
                    video_id = results[0]["videoId"]
                    yt.add_playlist_items(playlist_id, [video_id])
                    added += 1
                    log(f"  ✅ Adicionado: {track} - {artist}")
                else:
                    not_found.append(query)
                    log(f"  ❌ Não encontrado: {query}")

                time.sleep(sleep_seconds)  # evita rate limit
            except Exception as e:
                log(f"  ⚠️ Erro ao adicionar '{query}': {e}")

    log("\n🎉 Importação concluída!")
    log(f"Total adicionadas: {added}")
    if not_found:
        log(f"Não encontradas: {len(not_found)}")

    return playlist_id, not_found


def salvar_fallback_not_found(not_found_list, base_name: str, log):
    """
    Salva as queries não encontradas em um .txt simples para você revisar depois.
    """
    if not not_found_list:
        return None

    filename = f"{base_name}_not_found.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for q in not_found_list:
            f.write(q + "\n")

    log(f"📝 Arquivo de fallback salvo em '{filename}'.")
    return filename


# -------------------------------------------------------------------
# GUI
# -------------------------------------------------------------------

class SpotifyYtMusicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Spotify → YouTube Music")
        self.root.geometry("750x600")

        # estado
        self.headers_file = tk.StringVar(value=HEADERS_FILE_DEFAULT)
        self.sleep_seconds = tk.DoubleVar(value=0.6)

        self.last_playlist_id = None
        self.last_playlist_name = None
        self.last_fallback_file = None

        # para garantir updates thread-safe no log
        self.log_queue = []

        self._build_ui()
        self._schedule_log_update()

    # ------------------- construção da UI -------------------

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Topo: seleção do headers_file e sleep
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(top_frame, text="Headers YT (browser.json):").pack(side="left")
        entry_headers = ttk.Entry(top_frame, textvariable=self.headers_file, width=40)
        entry_headers.pack(side="left", padx=5)

        btn_browse = ttk.Button(top_frame, text="Procurar...", command=self._browse_headers_file)
        btn_browse.pack(side="left", padx=5)

        ttk.Label(top_frame, text="Delay (s):").pack(side="left", padx=(20, 2))
        ttk.Entry(top_frame, textvariable=self.sleep_seconds, width=5).pack(side="left")

        # Notebook com abas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        self._build_tab_playlist(notebook)
        self._build_tab_liked(notebook)
        self._build_tab_manual(notebook)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.log_text = tk.Text(log_frame, height=12, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        # Rodapé
        footer = ttk.Frame(main_frame)
        footer.pack(fill="x", pady=(8, 0))

        ttk.Button(footer, text="Abrir pasta CSV", command=self._open_csv_dir).pack(side="left")
        ttk.Button(footer, text="Sair", command=self.root.destroy).pack(side="right")

    def _build_tab_playlist(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Migrar Playlist")

        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill="both", expand=True)

        # URL / ID
        ttk.Label(frm, text="URL ou ID da playlist no Spotify:").grid(row=0, column=0, sticky="w")
        self.playlist_url_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.playlist_url_var, width=60).grid(row=1, column=0, columnspan=3, sticky="we", pady=2)

        # Nome base / CSV / playlist YT
        self.use_same_name_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            frm,
            text="Usar mesmo nome para CSV e playlist no YouTube Music",
            variable=self.use_same_name_var,
            command=self._toggle_name_fields,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 2))

        ttk.Label(frm, text="Nome base / CSV:").grid(row=3, column=0, sticky="w")
        self.playlist_base_name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.playlist_base_name_var, width=30).grid(row=3, column=1, sticky="w")

        ttk.Label(frm, text="Nome playlist YT:").grid(row=4, column=0, sticky="w", pady=(5, 0))
        self.playlist_yt_name_var = tk.StringVar()
        self.entry_playlist_yt_name = ttk.Entry(frm, textvariable=self.playlist_yt_name_var, width=30, state="disabled")
        self.entry_playlist_yt_name.grid(row=4, column=1, sticky="w", pady=(5, 0))

        # Botão
        ttk.Button(frm, text="Migrar playlist", command=self.on_migrate_playlist).grid(
            row=5, column=0, columnspan=3, pady=15
        )

        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=0)

    def _build_tab_liked(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Curtidas")

        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Nome base para CSV e playlist no YT:").grid(row=0, column=0, sticky="w")
        self.liked_base_name_var = tk.StringVar(value="liked_songs")
        ttk.Entry(frm, textvariable=self.liked_base_name_var, width=30).grid(row=0, column=1, sticky="w")

        ttk.Button(frm, text="Migrar minhas músicas curtidas", command=self.on_migrate_liked).grid(
            row=1, column=0, columnspan=2, pady=15
        )

        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)

    def _build_tab_manual(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Adição Manual")

        frm = ttk.Frame(tab, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Última playlist criada nesta sessão:").grid(row=0, column=0, columnspan=3, sticky="w")

        self.last_playlist_label = ttk.Label(frm, text="(nenhuma ainda)")
        self.last_playlist_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # Campo de busca
        ttk.Label(frm, text="Buscar (artista + música):").grid(row=2, column=0, sticky="w")
        self.manual_query_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.manual_query_var, width=40).grid(row=2, column=1, sticky="w")

        ttk.Button(frm, text="Buscar", command=self.on_manual_search).grid(row=2, column=2, padx=5)

        # Lista de resultados
        self.results_list = tk.Listbox(frm, height=8)
        self.results_list.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(5, 5))

        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.results_list.yview)
        scroll.grid(row=3, column=3, sticky="ns")
        self.results_list.configure(yscrollcommand=scroll.set)

        ttk.Button(frm, text="Adicionar faixa selecionada", command=self.on_manual_add_selected).grid(
            row=4, column=0, columnspan=3, pady=(5, 0)
        )

        ttk.Button(frm, text="Abrir último arquivo _not_found (se existir)", command=self.on_open_last_fallback).grid(
            row=5, column=0, columnspan=3, pady=(10, 0)
        )

        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=0)
        frm.columnconfigure(3, weight=0)
        frm.rowconfigure(3, weight=1)

    # ------------------- utilitários GUI -------------------

    def append_log(self, text: str):
        """Enfileira mensagem para ser exibida no Text em segurança."""
        self.log_queue.append(text)

    def _schedule_log_update(self):
        """Atualiza o Text com as mensagens enfileiradas."""
        if self.log_queue:
            self.log_text.configure(state="normal")
            while self.log_queue:
                msg = self.log_queue.pop(0)
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(100, self._schedule_log_update)

    def _browse_headers_file(self):
        filename = filedialog.askopenfilename(
            title="Selecionar arquivo de headers (browser.json)",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if filename:
            self.headers_file.set(filename)

    def _open_csv_dir(self):
        if os.path.exists(CSV_DIR):
            try:
                # Windows
                os.startfile(CSV_DIR)
            except Exception:
                # Outras plataformas
                messagebox.showinfo("Info", f"Pasta CSV: {os.path.abspath(CSV_DIR)}")
        else:
            messagebox.showerror("Erro", "Pasta csv não encontrada.")

    def _toggle_name_fields(self):
        if self.use_same_name_var.get():
            # desabilita o campo de playlist YT
            self.entry_playlist_yt_name.configure(state="disabled")
        else:
            self.entry_playlist_yt_name.configure(state="normal")

    def _run_in_thread(self, target, *args, **kwargs):
        def wrapper():
            try:
                target(*args, **kwargs)
            except Exception as e:
                self.append_log(f"\n❌ Erro: {e}")
                self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))
        t = threading.Thread(target=wrapper, daemon=True)
        t.start()

    # ------------------- ações das abas -------------------

    def on_migrate_playlist(self):
        playlist_url = self.playlist_url_var.get().strip()
        if not playlist_url:
            messagebox.showwarning("Atenção", "Informe a URL ou ID da playlist do Spotify.")
            return

        base_name = self.playlist_base_name_var.get().strip()
        if not base_name:
            base_name = extract_playlist_id(playlist_url)

        use_same = self.use_same_name_var.get()
        if use_same:
            csv_name = base_name
            yt_name = base_name
        else:
            csv_name = base_name
            yt_name = self.playlist_yt_name_var.get().strip() or base_name

        csv_path = os.path.join(CSV_DIR, f"{csv_name}.csv")
        headers = self.headers_file.get()
        sleep = float(self.sleep_seconds.get())

        def job():
            self.append_log("\n=== MIGRAR PLAYLIST (GUI) ===")
            self.append_log(f"Playlist: {playlist_url}")
            self.append_log(f"CSV: {csv_path}")
            self.append_log(f"Playlist YT: {yt_name}")

            export_spotify_playlist_to_csv(playlist_url, csv_path, self.append_log)
            playlist_id_yt, not_found = import_csv_to_ytmusic(
                csv_path=csv_path,
                new_playlist_name=yt_name,
                headers_file=headers,
                sleep_seconds=sleep,
                log=self.append_log,
            )
            fallback_file = salvar_fallback_not_found(not_found, csv_name, self.append_log)

            # Atualiza estado
            self.last_playlist_id = playlist_id_yt
            self.last_playlist_name = yt_name
            self.last_fallback_file = fallback_file

            self._update_last_playlist_label()

        self._run_in_thread(job)

    def on_migrate_liked(self):
        base_name = self.liked_base_name_var.get().strip()
        if not base_name:
            base_name = "liked_songs"

        csv_path = os.path.join(CSV_DIR, f"{base_name}.csv")
        yt_name = base_name
        headers = self.headers_file.get()
        sleep = float(self.sleep_seconds.get())

        def job():
            self.append_log("\n=== MIGRAR MÚSICAS CURTIDAS (GUI) ===")
            self.append_log(f"Base: {base_name}")
            self.append_log(f"CSV: {csv_path}")
            self.append_log(f"Playlist YT: {yt_name}")

            export_liked_songs_to_csv(csv_path, self.append_log)
            playlist_id_yt, not_found = import_csv_to_ytmusic(
                csv_path=csv_path,
                new_playlist_name=yt_name,
                headers_file=headers,
                sleep_seconds=sleep,
                log=self.append_log,
            )
            fallback_file = salvar_fallback_not_found(not_found, base_name, self.append_log)

            self.last_playlist_id = playlist_id_yt
            self.last_playlist_name = yt_name
            self.last_fallback_file = fallback_file

            self._update_last_playlist_label()

        self._run_in_thread(job)

    def _update_last_playlist_label(self):
        if self.last_playlist_id:
            txt = f"{self.last_playlist_name} (ID: {self.last_playlist_id})"
        else:
            txt = "(nenhuma ainda)"
        self.last_playlist_label.configure(text=txt)

    def on_manual_search(self):
        query = self.manual_query_var.get().strip()
        if not query:
            messagebox.showwarning("Atenção", "Digite um termo de busca (artista + música).")
            return

        if not self.last_playlist_id:
            messagebox.showwarning("Atenção", "Nenhuma playlist criada ainda nesta sessão.")
            return

        headers = self.headers_file.get()
        if not os.path.exists(headers):
            messagebox.showerror("Erro", f"Arquivo de headers '{headers}' não encontrado.")
            return

        def job():
            self.append_log(f"\n🔎 Busca manual: {query}")
            yt = YTMusic(headers)
            results = yt.search(query, filter="songs")

            def update_list():
                self.results_list.delete(0, "end")
                for item in results[:20]:
                    title = item.get("title", "Sem título")
                    artists = ", ".join([a["name"] for a in item.get("artists", [])]) or "Artista desconhecido"
                    album = item.get("album", {}).get("name", "")
                    display = f"{title} - {artists} ({album})"
                    self.results_list.insert("end", display)
                self.append_log(f"Encontrados {len(results)} resultados para busca manual.")

            self.root.after(0, update_list)

        self._run_in_thread(job)

    def on_manual_add_selected(self):
        sel = self.results_list.curselection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione uma faixa na lista de resultados.")
            return

        idx = sel[0]
        query = self.manual_query_var.get().strip()

        headers = self.headers_file.get()
        if not os.path.exists(headers):
            messagebox.showerror("Erro", f"Arquivo de headers '{headers}' não encontrado.")
            return

        if not self.last_playlist_id:
            messagebox.showwarning("Atenção", "Nenhuma playlist criada ainda nesta sessão.")
            return

        def job():
            yt = YTMusic(headers)
            results = yt.search(query, filter="songs")
            if not results or idx >= len(results):
                self.append_log("Nenhum resultado disponível para adicionar.")
                return

            item = results[idx]
            video_id = item["videoId"]
            yt.add_playlist_items(self.last_playlist_id, [video_id])

            title = item.get("title", "Sem título")
            artists = ", ".join([a["name"] for a in item.get("artists", [])]) or "Artista desconhecido"
            self.append_log(f"✅ Adicionado manualmente: {title} - {artists}")

        self._run_in_thread(job)

    def on_open_last_fallback(self):
        if self.last_fallback_file and os.path.exists(self.last_fallback_file):
            try:
                os.startfile(self.last_fallback_file)
            except Exception:
                messagebox.showinfo("Info", f"Arquivo: {os.path.abspath(self.last_fallback_file)}")
        else:
            messagebox.showinfo("Info", "Nenhum arquivo _not_found disponível nesta sessão.")


def main():
    root = tk.Tk()
    app = SpotifyYtMusicApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
