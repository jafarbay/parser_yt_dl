import requests
import re
import json
import html
import subprocess
import os

ACCENTS = {
    "1": "us",
    "2": "uk",
    "3": "aus",
    "4": "can",
    "5": "ei",
    "6": "sco",
    "7": "nz"
}

def choose_accent():
    print("Выберите акцент:")
    for key, val in ACCENTS.items():
        print(f"{key}: {val.upper()}")

    choice = input("Введите номер акцента (по умолчанию 1 - US): ").strip()
    return ACCENTS.get(choice, "us")

def fetch_json_data(word="could", accent="us"):
    url = f"https://youglish.com/pronounce/{word}/english/{accent}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_text = response.text

        match = re.search(r'params\.jsonData\s*=\s*\'({.*?})\';', html_text, re.DOTALL)
        if not match:
            match = re.search(r'params\.jsonData\s*=\s*\'({.*)', html_text, re.DOTALL)
            if match:
                partial_json = match.group(1)
                brace_count = 1
                end_pos = 0
                for i, char in enumerate(partial_json[1:], 1):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i
                            break
                if end_pos > 0:
                    raw_json = partial_json[:end_pos+1]
                else:
                    print("Не удалось найти корректное закрытие JSON")
                    return None
            else:
                print("params.jsonData не найден в HTML.")
                return None
        else:
            raw_json = match.group(1)

        raw_json = html.unescape(raw_json)
        raw_json = raw_json.replace('\\"', '"')
        raw_json = raw_json.replace('\\/', '/')
        
        clean_json = []
        in_escape = False
        for char in raw_json:
            if char == '\\' and not in_escape:
                in_escape = True
            else:
                clean_json.append(char)
                in_escape = False
        clean_json = ''.join(clean_json)

        try:
            data = json.loads(clean_json)
            return data
        except json.JSONDecodeError as e:
            print(f"Ошибка при декодировании JSON (позиция {e.pos}): {e.msg}")
            print(f"Контекст ошибки: {clean_json[e.pos-30:e.pos+30]}")
            return None
            
    except requests.RequestException as e:
        print(f"Ошибка при запросе к Youglish: {e}")
        return None

def download_videos(word, results):
    folder = word.lower()
    os.makedirs(folder, exist_ok=True)

    for i, result in enumerate(results, 1):
        vid = result.get("vid")
        start = result.get("start")
        end = result.get("end")
        
        if not vid or not start or not end:
            print(f"Пропущен Result {i}: недостаточно данных")
            continue

        try:
            youtube_url = f"https://www.youtube.com/watch?v={vid}"
            section = f"*{start}-{end}"
            video_path = os.path.join(folder, f"{word}_{i}.mp4")
            audio_path = os.path.join(folder, f"{word}_{i}.ogg")

            command_video = [
                "yt-dlp",
                "--download-sections", section,
                "--force-keyframes-at-cuts",
                "--concurrent-fragments", "5",
                "-f", "mp4",
                youtube_url,
                "-o", video_path
            ]
            print(f"Скачивание видео {i}: {youtube_url} → {video_path}")
            subprocess.run(command_video, check=True)

            command_audio = [
                "ffmpeg",
                "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "libvorbis",
                audio_path
            ]
            subprocess.run(command_audio, check=True)
            print(f"Успешно: {audio_path}")

            os.remove(video_path)

        except subprocess.CalledProcessError as e:
            print(f"Ошибка при скачивании/конвертации: {e}")
        except Exception as e:
            print(f"Ошибка: {e}")

if __name__ == "__main__":
    word = input("Введите слово для поиска произношения: ").strip()
    if not word:
        print("Используется слово по умолчанию 'could'")
        word = "could"

    accent = choose_accent()
    print(f"Выбран акцент: {accent.upper()}")

    data = fetch_json_data(word, accent)
    if data and "results" in data:
        top_results = data["results"][:5]
        download_videos(word, top_results)
    else:
        print("Не удалось получить данные с Youglish.")
