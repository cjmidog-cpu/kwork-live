import streamlit as st
import asyncio, re, json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from playwright.async_api import async_playwright

import subprocess, sys, os


# Устанавливаем браузер один раз при старте
try:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
        capture_output=True
    )
except Exception:
    pass


import subprocess, sys
import os
import subprocess

# Устанавливаем Chromium для Playwright (только если ещё не установлен)
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    print("Installing Playwright browsers...")
    subprocess.run(["playwright", "install", "chromium"], check=False)





st.set_page_config(page_title="Kwork Live", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp { background: #06090d; }
.block-container { padding-top: 1.4rem !important; padding-bottom: 1.5rem !important; max-width: 980px; }
div[data-testid="stMetricValue"] { font-size: 1.2rem !important; font-weight: 600; }
div[data-testid="stMetricLabel"] { font-size: 0.72rem !important; opacity: 0.6; }
.stDivider { margin: 0.5rem 0 !important; }

.k-card {
    background: #0f141b;
    border: 1px solid #1a222d;
    border-radius: 9px;
    padding: 0.65rem 0.9rem;
    margin-bottom: 0.4rem;
}
.k-card:hover { border-color: #2a3544; }
.k-title { font-size: 0.93rem; font-weight: 600; color: #f1f5f9; line-height: 1.3; margin: 0 0 0.2rem 0; }
.k-desc { font-size: 0.78rem; color: #94a3b8; line-height: 1.35; margin: 0.15rem 0 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.k-price { font-size: 0.95rem; font-weight: 700; color: #e2e8f0; }
.k-meta { font-size: 0.7rem; color: #64748b; margin-top: 0.1rem; }
.k-tag { display: inline-block; background: #0d2818; color: #4ade80; font-size: 0.62rem; font-weight: 500; padding: 0.1rem 0.4rem; border-radius: 8px; margin: 0 0.2rem 0.15rem 0; }
.k-row { display: flex; justify-content: space-between; gap: 0.7rem; }
.k-left { flex: 1; min-width: 0; }
.k-right { text-align: right; min-width: 85px; }
.k-btn { display: inline-block; margin-top: 0.3rem; background: #1e293b; color: #e2e8f0 !important; font-size: 0.72rem; padding: 0.2rem 0.55rem; border-radius: 6px; text-decoration: none !important; border: 1px solid #334155; }
.k-btn:hover { background: #334155; color: #fff !important; }
</style>
""", unsafe_allow_html=True)

SEEN = Path("seen_projects.json")

KEYWORDS = {
    "Сайты": ["сайт", "лендинг", "landing", "tilda", "wordpress", "веб", "новый сайт", "копия сайта", "создание сайта"],
    "ИИ-фото/видео": ["фото", "реставрация", "апскейл", "8k", "видео", "shorts", "монтаж", "нейросеть", "midjourney", "flux", "портрет", "аватар", "ии-генерация", "иллюстраци"],
    "Дизайн/Figma": ["figma", "макет", "ui", "ux", "дизайн", "инфографика"],
    "Тексты/SEO": ["seo", "статья", "тексты", "рерайт", "редактура", "копирайт", "контент"],
    "Боты": ["бот", "telegram", "телеграм", "чат-бот", "mini app"],
    "Excel/PDF": ["excel", "таблица", "pdf", "парсинг", "данные", "автоматизация"],
    "Маркетплейсы": ["карточка", "wildberries", "wb", "ozon", "товар"],
}

@dataclass
class Project:
    id: str
    title: str
    price: str
    price_num: int
    offers: str
    description: str
    url: str
    score: int = 0
    groups: list = field(default_factory=list)

def load_seen():
    if SEEN.exists():
        try: return set(json.loads(SEEN.read_text(encoding="utf-8")))
        except: return set()
    return set()

def save_seen(s):
    SEEN.write_text(json.dumps(list(s), ensure_ascii=False), encoding="utf-8")

def score(title, desc):
    text = (title + " " + desc).lower()
    matched, groups = [], []
    for g, kws in KEYWORDS.items():
        found = [k for k in kws if k in text]
        if found:
            matched += found
            groups.append(g)
    return len(set(matched)), groups

@st.cache_data(ttl=60, show_spinner=False)
def parse_cached(pages=3):
    return asyncio.run(parse(pages))

async def parse(pages=3):
    projects = []
    seen_ids = set()
    async with async_playwright() as p:
       browser = await p.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--single-process",
        "--no-zygote",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-default-apps",
        "--mute-audio",
    ]
)
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            java_script_enabled=True,
        )
        # Блокируем картинки, шрифты, медиа
        await context.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "media", "font"] 
            else route.continue_()
        )
        page = await context.new_page()

        for page_num in range(1, pages + 1):
            url = "https://kwork.ru/projects" if page_num == 1 else f"https://kwork.ru/projects?page={page_num}"
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(400)

            data = await page.evaluate("""
                () => {
                    const r = [], s = new Set();
                    for (const a of document.querySelectorAll('a[href*="/projects/"]')) {
                        const h = a.getAttribute('href') || '';
                        const m = h.match(/\\/projects\\/(\\d+)/);
                        if (!m || s.has(m[1])) continue;
                        s.add(m[1]);
                        const t = a.innerText.trim();
                        if (!t || t.length < 5) continue;
                        let c = a;
                        for (let i = 0; i < 12; i++) {
                            if (!c.parentElement) break;
                            c = c.parentElement;
                            if ((c.innerText || '').includes('₽')) break;
                        }
                        r.push({id: m[1], title: t, text: c.innerText || '', href: h});
                    }
                    return r;
                }
            """)

            for c in data:
                if c["id"] in seen_ids: continue
                seen_ids.add(c["id"])
                title, text, href = c["title"], c["text"], c["href"]

                price, pnum = "—", 0
                m = re.search(r"(?:Желаемый бюджет|Цена до|до)[:\s]*([\d\s\u00a0]+)\s*₽", text, re.I)
                if m:
                    clean = re.sub(r"[\s\u00a0]+", "", m.group(1))
                    price = clean + " ₽"
                    try: pnum = int(clean)
                    except: pass

                offers = "0"
                m2 = re.search(r"Предложений?\s*[:\s]*(\d+)", text, re.I)
                if m2: offers = m2.group(1)

                desc = re.sub(r"\s+", " ", text).strip()
                if title in desc: desc = desc.replace(title, "", 1).strip()
                desc = re.sub(r"(Покупатель|Размещено|Показать полностью|Желаемый бюджет|Цена до).*", "", desc, flags=re.I).strip()
                desc = desc[:150] + "…" if len(desc) > 150 else desc

                full_url = href if href.startswith("http") else "https://kwork.ru" + href
                sc, gr = score(title, desc)
                projects.append(Project(c["id"], title, price, pnum, offers, desc, full_url, sc, gr))

        await browser.close()
    return projects

# ========== UI ==========
st.markdown("## ⚡ Kwork Live")
st.caption("Монитор заказов под твои услуги")

# Основные фильтры
c1, c2, c3, c4 = st.columns([1.2, 1.1, 1.1, 0.9])
with c1:
    only_rel = st.toggle("Только подходящие", value=True)
with c2:
    only_str = st.toggle("Сильные (2+)", value=False)
with c3:
    min_p = st.number_input("Мин. ₽", min_value=0, value=0, step=500, label_visibility="collapsed")
with c4:
    if st.button("Обновить", use_container_width=True, type="primary"):
        st.rerun()

# Быстрые фильтры по направлениям
st.write("")
f1, f2, f3, f4 = st.columns(4)
with f1:
    f_sites = st.checkbox("Сайты / Лендинги", value=False)
with f2:
    f_ai = st.checkbox("ИИ фото/видео", value=False)
with f3:
    f_bots = st.checkbox("Боты / Telegram", value=False)
with f4:
    f_design = st.checkbox("Дизайн / Figma", value=False)

with st.spinner("Сканирую 3 страницы биржи..."):
    projects = parse_cached(pages=3)

projects.sort(key=lambda x: (x.score, x.price_num), reverse=True)

seen = load_seen()
for p in projects:
    seen.add(p.id)
save_seen(seen)

# Фильтрация
filtered = []
for p in projects:
    if only_rel and p.score == 0:
        continue
    if only_str and p.score < 2:
        continue
    if min_p > 0 and p.price_num < min_p:
        continue

    # Быстрые фильтры
    if f_sites or f_ai or f_bots or f_design:
        ok = False
        if f_sites and "Сайты" in p.groups: ok = True
        if f_ai and "ИИ-фото/видео" in p.groups: ok = True
        if f_bots and "Боты" in p.groups: ok = True
        if f_design and "Дизайн/Figma" in p.groups: ok = True
        if not ok:
            continue

    filtered.append(p)

# Метрики
now = datetime.now().strftime("%H:%M:%S")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Собрано", len(projects))
m2.metric("Подходят", len([p for p in projects if p.score > 0]))
m3.metric("Показано", len(filtered))
m4.metric("Обновлено", now)

st.divider()

if not filtered:
    st.info("Нет заказов по текущим фильтрам")
else:
    for p in filtered:
        tags = "".join(f'<span class="k-tag">{g}</span>' for g in p.groups)
        st.markdown(f"""
        <div class="k-card">
            <div class="k-row">
                <div class="k-left">
                    <div class="k-title">{p.title}</div>
                    <div>{tags}</div>
                    <div class="k-desc">{p.description}</div>
                    <a class="k-btn" href="{p.url}" target="_blank">Открыть →</a>
                </div>
                <div class="k-right">
                    <div class="k-price">{p.price}</div>
                    <div class="k-meta">Откликов: {p.offers}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.caption("AI-Profi · kwork.ru")
