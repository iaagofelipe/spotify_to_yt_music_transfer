import os
import csv
import time

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from dotenv import load_dotenv

load_dotenv()  # carrega .env com SPOTIPY_*

CSV_DIR = "csv"
os.makedirs(CSV_DIR, exist_ok=True)


# -------------------------------------------------------------------
# Helpers básicos
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


# -------------------------------------------------------------------
# SPOTIFY → CSV
# -------------------------------------------------------------------

def export_spotify_playlist_to_csv(playlist_id_or_url: str, csv_path: str):
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

    print(f"\nLendo playlist do Spotify ({playlist_id})...")
    tracks = get_playlist_tracks(playlist_id)
    print(f"Encontradas {len(tracks)} faixas. Salvando em CSV...")

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

    print(f"✅ Exportação concluída! {len(tracks)} músicas salvas em '{csv_path}'.")


def export_liked_songs_to_csv(csv_path: str):
    """
    Exporta as MÚSICAS CURTIDAS do usuário para CSV.
    """
    sp = get_spotify_client()

    print("\nLendo MINHAS MÚSICAS CURTIDAS do Spotify...")
    tracks = get_liked_tracks(sp)
    print(f"Encontradas {len(tracks)} faixas curtidas. Salvando em CSV...")

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

    print(f"✅ Exportação concluída! {len(tracks)} músicas curtidas salvas em '{csv_path}'.")


# -------------------------------------------------------------------
# CSV → YOUTUBE MUSIC
# -------------------------------------------------------------------

def import_csv_to_ytmusic(
    csv_path: str,
    new_playlist_name: str,
    headers_file: str = "browser.json",
    sleep_seconds: float = 0.6,
):
    """
    Cria uma nova playlist no YouTube Music e importa as músicas do CSV.
    Usa autenticação baseada em headers (browser.json).
    Retorna (playlist_id, lista_not_found).
    """
    if not os.path.exists(headers_file):
        raise FileNotFoundError(
            f"Arquivo de headers '{headers_file}' não encontrado. "
            f"Garanta que gerou o browser.json com 'ytmusicapi browser'."
        )

    yt = YTMusic(headers_file)

    print(f"\nCriando playlist '{new_playlist_name}' no YouTube Music...")
    playlist_id = yt.create_playlist(
        title=new_playlist_name,
        description="Importada automaticamente a partir de uma playlist do Spotify.",
    )
    print(f"✅ Playlist criada! ID: {playlist_id}")

    added = 0
    not_found = []

    with open(csv_path, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            artist = row["Artist"]
            track = row["Track"]
            query = f"{artist} {track}"

            print(f"🔎 Buscando: {query}...")
            try:
                results = yt.search(query, filter="songs")
                if results:
                    video_id = results[0]["videoId"]
                    yt.add_playlist_items(playlist_id, [video_id])
                    added += 1
                    print(f"  ✅ Adicionado: {track} - {artist}")
                else:
                    not_found.append(query)
                    print(f"  ❌ Não encontrado: {query}")

                time.sleep(sleep_seconds)  # evita rate limit
            except Exception as e:
                print(f"  ⚠️ Erro ao adicionar '{query}': {e}")

    print("\n🎉 Importação concluída!")
    print(f"Total adicionadas: {added}")
    if not_found:
        print(f"Não encontradas: {len(not_found)}")

    return playlist_id, not_found


# -------------------------------------------------------------------
# Fallback: salvar não encontradas e adicionar manualmente
# -------------------------------------------------------------------

def salvar_fallback_not_found(not_found_list, base_name: str):
    """
    Salva as queries não encontradas em um .txt simples para você revisar depois.
    """
    if not not_found_list:
        return None

    filename = f"{base_name}_not_found.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for q in not_found_list:
            f.write(q + "\n")

    print(f"📝 Arquivo de fallback salvo em '{filename}'.")
    return filename


def interactive_add_tracks_to_playlist(playlist_id: str, playlist_name: str, headers_file: str = "browser.json"):
    """
    Permite adicionar faixas unitárias, via busca manual, na playlist informada.
    Ideal para lidar com fallbacks (músicas não encontradas automaticamente).
    """
    if not os.path.exists(headers_file):
        print(f"Arquivo '{headers_file}' não encontrado. Não foi possível autenticar no YouTube Music.")
        return

    yt = YTMusic(headers_file)

    print(f"\n=== MODO DE ADIÇÃO MANUAL ===")
    print(f"Playlist de destino: {playlist_name} (ID: {playlist_id})")
    print("Digite um termo de busca (ex: artista + música). ENTER vazio para sair.\n")

    while True:
        query = input("🔎 Buscar (ENTER para sair): ").strip()
        if not query:
            print("Saindo do modo de adição manual.\n")
            break

        results = yt.search(query, filter="songs")
        if not results:
            print("Nenhum resultado encontrado. Tente outra busca.\n")
            continue

        # mostra os 5 primeiros resultados
        print("\nResultados:")
        for i, item in enumerate(results[:5], start=1):
            title = item.get("title", "Sem título")
            artists = ", ".join([a["name"] for a in item.get("artists", [])]) or "Artista desconhecido"
            album = item.get("album", {}).get("name", "")
            print(f"[{i}] {title} - {artists} ({album})")

        choice = input("Escolha o número para adicionar (ou ENTER para pular): ").strip()
        if not choice:
            print("Pulando.\n")
            continue

        if not choice.isdigit() or not (1 <= int(choice) <= min(5, len(results))):
            print("Opção inválida. Tente novamente.\n")
            continue

        index = int(choice) - 1
        video_id = results[index]["videoId"]
        yt.add_playlist_items(playlist_id, [video_id])
        print("✅ Faixa adicionada com sucesso!\n")


# -------------------------------------------------------------------
# Fluxo 1: UMA TACADA SÓ (nome base = CSV + playlist YT)
# -------------------------------------------------------------------

def fluxo_migrar_spotify_para_yt_base(headers_file: str = "browser.json"):
    """
    Pergunta:
    - URL/ID da playlist do Spotify
    - Nome base (usado tanto para o CSV quanto para a playlist no YT Music)
    """
    print("\n=== MIGRAR PLAYLIST (NOME BASE ÚNICO) ===")

    playlist_input = input("Cole a URL ou ID da playlist do Spotify: ").strip()
    if not playlist_input:
        print("Nenhuma playlist informada. Abortando.\n")
        return None, None, None

    base_name = input(
        "Nome base para o arquivo CSV e a playlist no YT Music (ex: minha_playlist): "
    ).strip()
    if not base_name:
        base_name = extract_playlist_id(playlist_input)

    csv_path = os.path.join(CSV_DIR, f"{base_name}.csv")
    yt_playlist_name = base_name  # usa o mesmo nome pro YT

    # 1) Exportar Spotify → CSV
    export_spotify_playlist_to_csv(playlist_input, csv_path)

    # 2) Importar CSV → YT Music
    playlist_id_yt, not_found = import_csv_to_ytmusic(
        csv_path=csv_path,
        new_playlist_name=yt_playlist_name,
        headers_file=headers_file,
        sleep_seconds=0.6,
    )

    # 3) Salvar fallbacks (não encontradas)
    fallback_file = salvar_fallback_not_found(not_found, base_name)

    return playlist_id_yt, yt_playlist_name, fallback_file


# -------------------------------------------------------------------
# Fluxo 2: COMPLETO (URL + nome CSV + nome playlist YT separados)
# -------------------------------------------------------------------

def fluxo_migrar_spotify_para_yt_custom(headers_file: str = "browser.json"):
    """
    Pergunta:
    - URL/ID da playlist do Spotify
    - Nome do arquivo CSV (sem .csv)
    - Nome da playlist no YT Music (livre)
    """
    print("\n=== MIGRAR PLAYLIST (NOMES PERSONALIZADOS) ===")

    playlist_input = input("Cole a URL ou ID da playlist do Spotify: ").strip()
    if not playlist_input:
        print("Nenhuma playlist informada. Abortando.\n")
        return None, None, None

    csv_name = input("Nome do arquivo CSV (sem .csv): ").strip()
    if not csv_name:
        csv_name = "playlist_export"

    yt_playlist_name = input("Nome da nova playlist no YouTube Music: ").strip()
    if not yt_playlist_name:
        yt_playlist_name = csv_name

    csv_path = os.path.join(CSV_DIR, f"{csv_name}.csv")

    # 1) Exportar Spotify → CSV
    export_spotify_playlist_to_csv(playlist_input, csv_path)

    # 2) Importar CSV → YT Music
    playlist_id_yt, not_found = import_csv_to_ytmusic(
        csv_path=csv_path,
        new_playlist_name=yt_playlist_name,
        headers_file=headers_file,
        sleep_seconds=0.6,
    )

    # 3) Salvar fallbacks (não encontradas) — usa nome do CSV como base
    fallback_file = salvar_fallback_not_found(not_found, csv_name)

    return playlist_id_yt, yt_playlist_name, fallback_file


# -------------------------------------------------------------------
# Fluxo 3: MIGRAR MÚSICAS CURTIDAS
# -------------------------------------------------------------------

def fluxo_migrar_curtidas_para_yt(headers_file: str = "browser.json"):
    """
    Exporta MINHAS MÚSICAS CURTIDAS para CSV e cria uma playlist no YT Music.
    """
    print("\n=== MIGRAR MINHAS MÚSICAS CURTIDAS ===")

    base_name = input(
        "Nome base para o arquivo CSV e playlist no YT Music (ex: curtidas_spotify): "
    ).strip()
    if not base_name:
        base_name = "liked_songs"

    csv_path = os.path.join(CSV_DIR, f"{base_name}.csv")
    yt_playlist_name = base_name

    # 1) Exportar curtidas → CSV
    export_liked_songs_to_csv(csv_path)

    # 2) Importar CSV → YT Music
    playlist_id_yt, not_found = import_csv_to_ytmusic(
        csv_path=csv_path,
        new_playlist_name=yt_playlist_name,
        headers_file=headers_file,
        sleep_seconds=0.6,
    )

    # 3) Salvar fallbacks (não encontradas)
    fallback_file = salvar_fallback_not_found(not_found, base_name)

    return playlist_id_yt, yt_playlist_name, fallback_file


# -------------------------------------------------------------------
# Menu principal
# -------------------------------------------------------------------

def main():
    headers_file = "browser.json"

    last_playlist_id = None
    last_playlist_name = None
    last_fallback_file = None

    while True:
        print("\n==============================")
        print("  SPOTIFY → YOUTUBE MUSIC APP ")
        print("==============================")
        print("1) Migrar playlist (nome base único: CSV = playlist YT)")
        print("2) Migrar playlist (nomes personalizados: CSV e YT separados)")
        print("3) Adicionar faixas manualmente na ÚLTIMA playlist criada")
        print("4) Migrar MINHAS MÚSICAS CURTIDAS para o YouTube Music")
        print("0) Sair")
        choice = input("Escolha uma opção: ").strip()

        if choice == "1":
            last_playlist_id, last_playlist_name, last_fallback_file = fluxo_migrar_spotify_para_yt_base(headers_file)

        elif choice == "2":
            last_playlist_id, last_playlist_name, last_fallback_file = fluxo_migrar_spotify_para_yt_custom(headers_file)

        elif choice == "3":
            if not last_playlist_id:
                print("Nenhuma playlist criada ainda nesta sessão. Use a opção 1, 2 ou 4 primeiro.\n")
            else:
                print(f"\nÚltima playlist criada: {last_playlist_name} (ID: {last_playlist_id})")
                if last_fallback_file and os.path.exists(last_fallback_file):
                    print(f"Você também tem um arquivo de fallback: {last_fallback_file}")
                    print("Abra esse arquivo e copie/cole as buscas aqui, se quiser.\n")
                interactive_add_tracks_to_playlist(last_playlist_id, last_playlist_name, headers_file)

        elif choice == "4":
            last_playlist_id, last_playlist_name, last_fallback_file = fluxo_migrar_curtidas_para_yt(headers_file)

        elif choice == "0":
            print("Saindo. Até a próxima! 👋")
            break

        else:
            print("Opção inválida. Tente novamente.\n")


if __name__ == "__main__":
    main()
