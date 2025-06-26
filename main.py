import asyncio
from playwright.async_api import async_playwright
import random
import json
import os
import subprocess
from urllib.parse import urlparse, parse_qs

COOKIES_FILE = "cookies.json"
YOUTUBE_LINKS_FILE = "youtube_links.txt"
ACCENT_CODES = {
    "US": "us",
    "UK": "uk",
    "AUS": "au",
    "CAN": "ca",
    "IE": "ie",
    "SCO": "gb-sco",
    "NZ": "nz"
}

def extract_info_and_download(url, duration, output_file):
    parsed_url = urlparse(url)
    query = parse_qs(parsed_url.query)

    video_id = query.get('v', [None])[0]
    if not video_id:
        raise ValueError(f"❌ Не удалось найти параметр 'v' в ссылке: {url}")

    start_time = int(query.get('time_continue', [0])[0])
    end_time = start_time + duration

    normal_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"⬇️ Скачиваем {output_file} с {start_time} до {end_time} сек")

    command = [
        "yt-dlp",
        "--quiet", "--no-warnings",
        "--download-sections", f"*{start_time}-{end_time}",
        normal_url,
        "-o", output_file
    ]

    subprocess.run(command, check=True)

def random_user_agent():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)

async def main():
    word = input("🔤 Введите слово для произношения (например, hello): ").strip()
    print("🎙️ Доступные акценты: US, UK, AUS, CAN, IE, SCO, NZ")
    accent_input = input("🌍 Введите акцент (например, US): ").strip().upper()

    if accent_input not in ACCENT_CODES:
        print(f"❌ Неизвестный акцент: {accent_input}")
        return

    accent = ACCENT_CODES[accent_input]
    url = f"https://youglish.com/pronounce/{word}/english/{accent}"

    folder_name = word.lower()
    os.makedirs(folder_name, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=random_user_agent())

        if os.path.exists(COOKIES_FILE):
            print("💾 Загружаем сохранённые cookies...")
            cookies = json.load(open(COOKIES_FILE, "r"))
            await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto(url)

        try:
            print("🔘 Ищем кнопку согласия на cookies...")
            await page.wait_for_selector(
                "body > div.fc-consent-root button.fc-cta-consent", timeout=5000
            )
            await page.click("body > div.fc-consent-root button.fc-cta-consent")
            print("✅ Cookies приняты.")
        except:
            print("⚠️ Кнопка согласия не найдена или уже принята.")

        cookies = await context.cookies()
        json.dump(cookies, open(COOKIES_FILE, "w"), indent=2)
        print("💾 Куки сохранены.")

        youtube_links = []

        for i in range(5):
            print(f"\n🔎 Обрабатываем пример №{i+1}...")

            selector = '#all_actions > div:nth-child(1) > div:nth-child(2) > div:nth-child(1)'
            await page.wait_for_selector(selector, timeout=10000)

            container = await page.query_selector(selector)
            if not container:
                print("❌ Не найден элемент с YouTube ссылкой.")
                break

            link = await container.query_selector('a')
            if not link:
                print("❌ В элементе нет ссылки <a>.")
                break

            async with context.expect_page() as new_page_info:
                await link.click()

            new_page = await new_page_info.value
            await new_page.wait_for_load_state()
            youtube_url = new_page.url
            print(f"✅ Получена ссылка на YouTube: {youtube_url}")
            youtube_links.append(youtube_url)
            await new_page.close()

            if i < 4:
                print("➡️ Нажимаем кнопку 'Next' для следующего примера...")
                try:
                    await page.wait_for_selector('#b_next', timeout=5000)
                    await page.click('#b_next')
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"❌ Не удалось нажать кнопку 'Next': {e}")
                    break

        # Сохраняем ссылки
        with open(YOUTUBE_LINKS_FILE, "a") as f:
            for link in youtube_links:
                f.write(link + "\n")

        print(f"\n💾 Все ссылки сохранены в {YOUTUBE_LINKS_FILE}")

        # Скачиваем фрагменты видео
        print("\n📥 Начинаем скачивание фрагментов YouTube...")
        for idx, link in enumerate(youtube_links, start=1):
            output_path = os.path.join(folder_name, f"{word.lower()}{idx}.mp4")
            try:
                extract_info_and_download(link, duration=8, output_file=output_path)
            except Exception as e:
                print(f"❌ Ошибка при скачивании {link}: {e}")

        input("\n⏸️ Нажми Enter для завершения...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
