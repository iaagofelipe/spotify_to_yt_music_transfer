import os
import csv
import time
import argparse

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from dotenv import load_dotenv

load_dotenv()  # carrega .env com SPOTIPY_*


# --------- SPOTIFY → CSV ---------
def export_spotify_playlist_to_csv(playlist_id_or_url: str, csv_path: str):
    """
    Exporta uma playlist do Spotify para CSV (colunas: Artist, Track).
    Aceita tanto o ID puro quanto a URL completa da playlist.
    """
    playlist_id = extract_playlist_id(playlist_id_or_url)

    sp = Spotify(
        auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            scope="playlist-read-private"
        )
    )

    def get_playlist_tracks(pid):
        results = sp.playlist_tracks(pid)
        tracks = results["items"]
        while results["next"]:
            results = sp.next(results)
            tracks.extend(results["items"])
        return tracks

    print(f"Lendo playlist do Spotify ({playlist_id})...")
    tracks = get_playlist_tracks(playlist_id)

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

    print(f"✅ Exportação concluída! {len(tracks)} músicas salvas em {csv_path}")


def extract_playlist_id(playlist_id_or_url: str) -> str:
    """
    Se o usuário passar a URL completa do Spotify, extrai só o ID.
    Exemplo:
      - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
      -> 37i9dQZF1DXcBWIGoYBM5M
    """
    if "open.spotify.com" in playlist_id_or_url:
        # divide na parte depois de 'playlist/'
        parts = playlist_id_or_url.split("playlist/")
        if len(parts) > 1:
            return parts[1].split("?")[0]
    return playlist_id_or_url.strip()


# --------- CSV → YOUTUBE MUSIC ---------
def import_csv_to_ytmusic(
    csv_path: str,
    new_playlist_name: str,
    headers_file: str = "browser.json",
    sleep_seconds: float = 0.6,
):
    """
    Cria uma nova playlist no YouTube Music e importa as músicas do CSV.
    Usa autenticação baseada em headers (browser.json).
    """
    if not os.path.exists(headers_file):
        raise FileNotFoundError(
            f"Arquivo de headers '{headers_file}' não encontrado. "
            f"Garanta que gerou o browser.json com 'ytmusicapi browser'."
        )

    yt = YTMusic(headers_file)

    print(f"Criando playlist '{new_playlist_name}' no YouTube Music...")
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
        print("Não encontradas:")
        for q in not_found:
            print(f"  - {q}")


# --------- CLI ---------
def main():
    parser = argparse.ArgumentParser(
        description="Exportar playlists do Spotify para CSV e importar para YouTube Music."
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando (export ou import)")

    # spotify → csv
    export_parser = subparsers.add_parser(
        "export", help="Exportar playlist do Spotify para CSV"
    )
    export_parser.add_argument(
        "--playlist",
        required=True,
        help="ID ou URL da playlist do Spotify",
    )
    export_parser.add_argument(
        "--csv",
        default="playlist_spotify.csv",
        help="Caminho do arquivo CSV de saída",
    )

    # csv → ytmusic
    import_parser = subparsers.add_parser(
        "import", help="Importar CSV para YouTube Music"
    )
    import_parser.add_argument(
        "--csv",
        required=True,
        help="Caminho do arquivo CSV de entrada",
    )
    import_parser.add_argument(
        "--name",
        required=True,
        help="Nome da nova playlist no YouTube Music",
    )
    import_parser.add_argument(
        "--headers",
        default="browser.json",
        help="Arquivo de headers do ytmusicapi (ex: browser.json)",
    )
    import_parser.add_argument(
        "--sleep",
        type=float,
        default=0.6,
        help="Tempo (segundos) de espera entre cada adição para evitar bloqueio",
    )

    args = parser.parse_args()

    if args.command == "export":
        export_spotify_playlist_to_csv(args.playlist, args.csv)
    elif args.command == "import":
        import_csv_to_ytmusic(args.csv, args.name, args.headers, args.sleep)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
