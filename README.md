🟩 Spotify → YouTube Music GUI
==============================

App em Python (com interface gráfica em Tkinter) para:

*   Exportar playlists do **Spotify** para CSV
    
*   Exportar suas **músicas curtidas**
    
*   Importar playlists para o **YouTube Music**
    
*   Ajustar faixas manualmente
    
*   Tudo com GUI, tema escuro, animações e barra de progresso
    

🎧 Funcionalidades
------------------

*   **Migrar playlists do Spotify → YT Music**
    
*   **Migrar músicas curtidas**
    
*   **Deduplicação de faixas**
    
*   **Fallback automático** (\*\_not\_found.txt)
    
*   **Adição manual** de faixas via busca no YT Music
    
*   **Pasta csv/ automática**
    
*   **Tema dark**
    
*   **Barra de progresso + spinner animado**
    
*   **Tela de configurações**
    
*   Totalmente integrado via GUI
    

📥 Instalação
-------------

### 1\. Baixe o projeto

Crie a pasta do projeto:

``` spotify_to_ytmusic/ ```

Coloque dentro dela o arquivo:

*   spotify\_ytmusic\_gui.py
    

Crie também (se ainda não existir):

*   `.env` (vamos configurar abaixo)
    
*   arquivo de headers `browser.json` (YT Music)
    

🧰 Instalar dependências
------------------------

### Windows

```
py -m venv venv 
venv\Scripts\activate
pip install spotipy ytmusicapi python-dotenv
```

### Linux/macOS

```
python3 -m venv venv 
source venv/bin/activate
pip install spotipy ytmusicapi python-dotenv 
```

🎵 Configurando o Spotify (Spotipy)
===================================

Vamos criar um app no Spotify Developer para permitir exportar playlists.

🔑 1. Criar app no Spotify Developer
------------------------------------

Acesse:

👉 [https://developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)

1.  Clique em **Create App**
    
2.  Nome do app → SpotifyToYTMusic
    
3.  Descrição → qualquer texto
    
4.  Na seção **Redirect URIs**, adicione:

```    
http://127.0.0.1:8888/callback  
```
⚠️ _Importante:_ localhost **não funciona mais**, só 127.0.0.1.

🔑 2. Copie o Client ID e Client Secret
---------------------------------------

Depois de criar o app, vá em **Settings** e copie:

*   Client ID
    
*   Client Secret
    

🔧 3. Criar arquivo .env
------------------------

Na raiz do projeto, crie o arquivo:

 ```.env```   
 
E coloque:
```
SPOTIPY_CLIENT_ID=SEU_CLIENT_ID
SPOTIPY_CLIENT_SECRET=SEU_CLIENT_SECRET
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

🧪 4. Login automático
----------------------

Na primeira vez que executar uma migração, o Spotify abrirá o navegador pedindo autorização.

Depois disso, o token automático ficará salvo no arquivo .cache.

🎵 Configurando o YouTube Music (ytmusicapi via browser.json)
=============================================================

O YouTube Music **não usa OAuth facilmente**, então usamos login via **headers do navegador**, que é 100% compatível com ytmusicapi.

🔎 1. Acesse o YouTube Music
----------------------------

Entre em:

👉 [https://music.youtube.com](https://music.youtube.com)

Certifique-se de estar **logado** na conta correta.

🧪 2. Abra o DevTools → aba Network
-----------------------------------

1.  Pressione **F12**
    
2.  Vá em **Network**
    
3.  No filtro, digite:
    
```   /browse   ```

1.  Clique em uma requisição POST browse?...
    
2.  Copie **todos** os _Request Headers_:
    

No Chrome/Edge:

*   Clique com botão direito → **Copy → Copy request headers**
    

No Firefox:

*   Clique com botão direito → **Copy → Copy request headers**
    

🔧 3. Gerar o arquivo browser.json
----------------------------------

Com o ambiente virtual ativado:

```   ytmusicapi browser   ```

O terminal exibirá:

`  Paste your request headers and press Ctrl-D (Linux/mac) or Ctrl-Z (Windows)   `

Cole os headers copiados → pressione Ctrl + Z → Enter.

Isso criará:

`   browser.json   `

Esse arquivo é o seu "login" no YouTube Music.

▶️ Como rodar o app
===================

Ative o ambiente virtual e execute:

`   python spotify_ytmusic_gui.py   `

A GUI abrirá com:

*   Migrar Playlist
    
*   Migrar Curtidas
    
*   Adição Manual
    
*   Configurações
    

🟩 Como usar
============

1\. Migrar playlist do Spotify
------------------------------

1.  Vá na aba **Migrar Playlist**
    
2.  Cole a URL ou ID da playlist
    
3.  Escolha o nome base do CSV
    
4.  (Opcional) Nome diferente para a playlist no YT Music
    
5.  Clique **Migrar Playlist**
    

Ele vai:

*   Exportar playlist → CSV
    
*   Criar playlist no YT Music
    
*   Adicionar cada música
    
*   Mostrar progresso + log
    

2\. Migrar músicas curtidas
---------------------------

1.  Vá na aba **Curtidas**
    
2.  Escolha o nome base
    
3.  Clique **Migrar minhas músicas curtidas**
    

3\. Adicionar manualmente músicas que falharam
----------------------------------------------

1.  Abra a aba **Adição Manual**
    
2.  Digite artista + música
    
3.  Clique **Buscar**
    
4.  Selecione o resultado
    
5.  Clique **Adicionar faixa selecionada**
    

Você também pode abrir o \_not\_found.txt.

4\. Configuração
----------------

Na aba **Config**:

*   Selecionar browser.json
    
*   Ajustar delay (0.6s recomendado)
    
*   Ativar/desativar deduplicação
    

🩻 Troubleshooting
==================

❌ Spotify: "invalid redirect uri"
---------------------------------

Você colocou no .env:

`   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback   `

Mas no Spotify Developer o valor está diferente.

⚠️ Eles precisam ser **idênticos**.

❌ YouTube Music: "Bad headers" ou "could not authenticate"
----------------------------------------------------------

Geralmente significa:

*   Headers incompletos
    
*   Você extraiu headers antes do login
    
*   Extração feita com extensão de bloqueio ativa
    
*   Requisição errada (não era /browse)
    

Refaça os passos.

📦 Criar um executável (.exe)
=============================

Você pode transformar o app inteiro em um .exe usando PyInstaller:

``` 
pip install pyinstaller
pyinstaller --noconsole --onefile spotify_ytmusic_gui.py
```

O executável aparecerá em:

`   dist/spotify_ytmusic_gui.exe   `

📚 Estrutura final recomendada
==============================

```  
   spotify_to_ytmusic/  
    │
    ├── spotify_ytmusic_gui.py
    ├── browser.json
    ├── .env
    ├── csv/  
    │   ├── playlist1.csv  
    │   ├── playlist2.csv  
    │   └── ...  
    └── README.md  ← (este arquivo)   
```

👑 Créditos
===========

Desenvolvido com carinho por **Iago 😎**
