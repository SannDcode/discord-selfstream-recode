import os
import time
import subprocess
import requests
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Konfigurasi Target & Lokasi File
TARGET_WEBSITE = "https://z2.idlixku.com"
OUTPUT_DIR = "assets"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current_movie.mp4")

def fetch_latest_movies(url):
    print(f"[*] Mencari film terbaru di {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    playlist = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/movie/" in href and href not in playlist:
                    if href.startswith("http"):
                        playlist.append(href)
                    else:
                        playlist.append(url.rstrip('/') + href)
                        
            playlist = playlist[:5] 
            print(f"[+] Berhasil menemukan {len(playlist)} halaman film terbaru.")
            return playlist
        else:
            print(f"[!] Gagal mengakses website. Status code: {response.status_code}")
    except Exception as e:
        print(f"[!] Terjadi kesalahan saat scraping halaman utama: {e}")
        
    return []

def extract_video_with_browser(movie_url):
    """
    Membuka browser tersembunyi untuk mengeksekusi JavaScript halaman film,
    menghasut klik otomatis pada opsi pemutar, dan menangkap link streaming aslinya.
    """
    print(f"[*] Meluncurkan browser internal untuk membedah proteksi halaman...")
    video_link = None
    
    with sync_playwright() as p:
        # Menjalankan chromium tanpa menampilkan jendela aplikasi (headless=True)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Interseptor jaringan untuk menangkap link video m3u8 atau mp4 dari provider player
        def intercept_response(response):
            nonlocal video_link
            url = response.url
            # Mendeteksi segmen link video dari server streaming populer
            if any(provider in url for provider in ["dood", "filemoon", "upstream", "vidsrc", "streamhide", ".mp4", ".m3u8"]):
                if not video_link:
                    video_link = url
                    print(f"[+] Trafik video terdeteksi: {video_link}")

        page.on("response", intercept_response)
        
        try:
            # Buka halaman film
            page.goto(movie_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5) # Tunggu skrip enkripsi memuat elemen
            
            # Cari tombol play/opsi server pemutar di layar dan klik secara otomatis
            player_selectors = ["#play-video", ".play-video", ".dooplay_player_option", "iframe"]
            for selector in player_selectors:
                if page.locator(selector).count() > 0:
                    try:
                        page.locator(selector).first.click(timeout=3000)
                        time.sleep(3)
                    except:
                        pass
                        
            # Jika belum tertangkap dari trafik, baca elemen iframe hasil render akhir browser
            if not video_link:
                iframes = page.locator("iframe").all()
                for iframe in iframes:
                    src = iframe.get_attribute("src")
                    if src and "http" in src and not any(x in src for x in ["ads", "google", "facebook"]):
                        video_link = src
                        print(f"[+] Link iframe hasil render ditemukan: {video_link}")
                        break
                        
        except Exception as e:
            print(f"[!] Browser gagal memproses halaman: {e}")
        finally:
            browser.close()
            
    return video_link

def download_video(video_url):
    print(f"[*] Mengirimkan link akhir yang tervalidasi ke yt-dlp...")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    command = [
        "yt-dlp",
        "--no-check-certificate",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-o", OUTPUT_FILE,
        video_url
    ]
    
    try:
        result = subprocess.run(command, check=True)
        if result.returncode == 0 and os.path.exists(OUTPUT_FILE):
            print("[+] Unduhan film berhasil diselesaikan!")
            return True
    except subprocess.CalledProcessError:
        print("[!] yt-dlp gagal mengunduh link streaming tersebut.")
    return False

def start_discord_stream():
    print("[*] Mengaktifkan bot discord-selfstream...")
    process = subprocess.Popen(["npm", "run", "start"], shell=True)
    return process

def cleanup_video():
    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
            print("[+] File video lama berhasil dibersihkan dari disk.")
        except Exception as e:
            print(f"[!] Gagal menghapus file lama: {e}")

def main_loop():
    while True:
        film_playlist = fetch_latest_movies(TARGET_WEBSITE)
        
        if not film_playlist:
            print("[!] Antrean film kosong. Mencoba memuat kembali dalam 60 detik...")
            time.sleep(60)
            continue
            
        for film_url in film_playlist:
            cleanup_video()
            
            print(f"\n[>] Memproses antrean film: {film_url}")
            
            # MENGGUNAKAN METODE BROWSER RENDERING
            real_stream_url = extract_video_with_browser(film_url)
            
            if real_stream_url:
                if download_video(real_stream_url):
                    bot_process = start_discord_stream()
                    
                    # Jeda waktu putar film (contoh: 2 jam)
                    durasi_menonton_detik = 7200 
                    print(f"[*] Film berhasil diputar. Menunggu selesai ({durasi_menonton_detik // 60} menit)...")
                    time.sleep(durasi_menonton_detik)
                    
                    print("[*] Menghentikan siaran player bot...")
                    bot_process.terminate()
                    time.sleep(5)
                else:
                    print("[!] Gagal mengunduh materi film dari link streaming.")
            else:
                print("[!] Gagal menemukan link video asli di halaman ini. Dilewati.")
                
        print("\n[+] Seluruh antrean halaman habis. Mencari film baru dalam 5 menit...\n")
        time.sleep(300)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n[!] Program automasi dihentikan oleh pengguna secara manual.")
        cleanup_video()
