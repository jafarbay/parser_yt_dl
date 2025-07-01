import requests
import re
import json
import html
import subprocess
import os
import asyncio
import aiohttp

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

async def fetch_json_data_async(word="could", accent="us"):
    url = f"https://youglish.com/pronounce/{word}/english/{accent}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                html_text = await response.text()

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
            
    except aiohttp.ClientError as e:
        print(f"Ошибка при запросе к Youglish: {e}")
        return None
    except asyncio.TimeoutError:
        print("Таймаут запроса к Youglish.")
        return None
    except Exception as e:
        print(f"Непредвиденная ошибка при получении JSON: {e}")
        return None

async def download_single_video_async(word, result, index, folder):
    vid = result.get("vid")
    start = result.get("start")
    end = result.get("end")

    if not vid or start is None or end is None:
        print(f"Пропущен Result {index}: недостаточно данных")
        return

    try:
        start = float(start)
        end = float(end) + 3.0
    except ValueError:
        print(f"Пропущен Result {index}: start/end не являются числами")
        return

    try:
        youtube_url = f"https://www.youtube.com/watch?v={vid}"
        section = f"*{start}-{end}"
        video_path = os.path.join(folder, f"{word}_{index}.mp4")
        audio_path = os.path.join(folder, f"{word}_{index}.ogg")

        print(f"Скачивание видео {index}: {youtube_url} → {video_path}")
        proc_video = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--download-sections", section,
            "--force-keyframes-at-cuts",
            "--concurrent-fragments", "5",
            "-f", "mp4",
            youtube_url,
            "-o", video_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_video, stderr_video = await proc_video.communicate()

        if proc_video.returncode != 0:
            print(f"Ошибка yt-dlp для видео {index} (код {proc_video.returncode}):\n{stderr_video.decode()}")
            raise subprocess.CalledProcessError(proc_video.returncode, "yt-dlp", output=stdout_video, stderr=stderr_video)
        
        proc_audio = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "libvorbis",
            audio_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_audio, stderr_audio = await proc_audio.communicate()

        if proc_audio.returncode != 0:
            print(f"Ошибка ffmpeg для видео {index} (код {proc_audio.returncode}):\n{stderr_audio.decode()}")
            raise subprocess.CalledProcessError(proc_audio.returncode, "ffmpeg", output=stdout_audio, stderr=stderr_audio)

        os.remove(video_path)
        print(f"Успешно: {audio_path}")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при скачивании/конвертации видео {index}: {e}")
    except Exception as e:
        print(f"Общая ошибка для видео {index}: {e}")

async def main_async():
    word = input("Введите слово для поиска произношения: ").strip()
    if not word:
        print("Используется слово по умолчанию 'could'")
        word = "could"

    accent = choose_accent()
    print(f"Выбран акцент: {accent.upper()}")

    data = await fetch_json_data_async(word, accent)
    if data and "results" in data:
        top_results = data["results"][:5]
        folder = word.lower()
        os.makedirs(folder, exist_ok=True)

        tasks = []
        for i, result in enumerate(top_results, 1):
            tasks.append(download_single_video_async(word, result, i, folder))
        
        await asyncio.gather(*tasks)
        print(f"\nВсего скачано/обработано {len(top_results)} видео для слова '{word}'.")
    else:
        print("Не удалось получить данные с Youglish.")

if __name__ == "__main__":
    asyncio.run(main_async())
