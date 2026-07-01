import sys
import os
import asyncio
import re
import time
import random
import string
import threading
from datetime import datetime
from playwright.async_api import async_playwright
import urllib.request
import urllib.error
import json

def debug_log(msg):
    pass

_HUMAN_NAMES_CACHE = None

def load_human_names(path="human_name.json"):
    global _HUMAN_NAMES_CACHE
    if _HUMAN_NAMES_CACHE is not None:
        return _HUMAN_NAMES_CACHE

    names_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(names_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    first_names = [
        str(name).strip().lower()
        for name in data.get("first_names", [])
        if str(name).strip()
    ]
    last_names = [
        str(name).strip().lower()
        for name in data.get("last_names", [])
        if str(name).strip()
    ]

    if not first_names or not last_names:
        raise ValueError("human_name.json harus punya first_names dan last_names yang tidak kosong")

    _HUMAN_NAMES_CACHE = (first_names, last_names)
    return _HUMAN_NAMES_CACHE

def generate_human_username():
    first_names, last_names = load_human_names()
    first = random.choice(first_names)
    last = random.choice(last_names)
    digits = str(random.randint(10, 999))
    return f"{first}{last}{digits}"

TEST_MODEL = 'qwen-turbo'
TEST_TIMEOUT = 12
TEST_URL = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
TEST_CHECK_MODELS = ['qwen-turbo','qwen-plus','qwen-max','deepseek-v4-flash','deepseek-v4-pro','glm-5.2','kimi-k2.7-code']

def test_key(email, key):
    h = {"Authorization": f"Bearer {key}", "User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    r = {'email': email, 'key': key, 'status': 'UNKNOWN', 'chat_ms': None, 'model_count': None, 'models_found': [], 'error_msg': ''}
    try:
        req = urllib.request.Request(f"{TEST_URL}/models", headers=h)
        with urllib.request.urlopen(req, timeout=TEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
            models = data.get('data', [])
            r['model_count'] = len(models)
            r['models_found'] = [m['id'] for m in models if m.get('id', '') in TEST_CHECK_MODELS]
    except Exception as e:
        r['status'] = 'DEAD'; r['error_msg'] = f'models: {str(e)[:60]}'
        return r
    payload = json.dumps({"model": TEST_MODEL, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 5}).encode()
    try:
        t0 = time.time()
        req = urllib.request.Request(f"{TEST_URL}/chat/completions", data=payload, headers=h)
        with urllib.request.urlopen(req, timeout=TEST_TIMEOUT) as resp:
            r['chat_ms'] = int((time.time() - t0) * 1000)
            r['status'] = 'OK'
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try: err_msg = json.loads(body).get('error', {}).get('message', str(e))
        except: err_msg = str(e)
        if 'denied' in err_msg or e.code == 403: r['status'] = 'DENIED'
        elif 'quota' in err_msg.lower() or 'rate' in err_msg.lower(): r['status'] = 'RATE_LIMITED'
        else: r['status'] = f'ERR_{e.code}'
        r['error_msg'] = err_msg[:80]
    except Exception as e:
        r['status'] = 'TIMEOUT' if 'timed out' in str(e).lower() else 'ERROR'
        r['error_msg'] = str(e)[:60]
    return r

# GopretMailAPI removed (switching to browser-based GoMail registration and OTP checking)

def debug_log(msg):
    pass

# Rich imports
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

class DashboardState:
    def __init__(self, total_accounts, num_slots=4):
        self.lock = threading.Lock()
        self.total_accounts = total_accounts
        self.completed_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.workers = {}  # worker_id -> {status, email, start_time, percentage}
        for i in range(1, num_slots + 1):
            self.workers[i] = {"status": "Idle", "email": "", "start_time": time.time(), "percentage": 0}
        self.results = []  # list of results
        self.start_time = time.time()
        
    def update_worker(self, worker_id, status, email=""):
        with self.lock:
            if worker_id not in self.workers:
                self.workers[worker_id] = {"status": "", "email": "", "start_time": time.time(), "percentage": 0}
            self.workers[worker_id]["status"] = status
            if email:
                self.workers[worker_id]["email"] = email
                
            # Reset percentage on starting new registration
            if "memulai" in status.lower() or "buka tab 1" in status.lower():
                self.workers[worker_id]["percentage"] = 0
                
            pct = get_stage_percentage(status)
            if pct > self.workers[worker_id].get("percentage", 0):
                self.workers[worker_id]["percentage"] = pct
                
    def finish_worker(self, worker_id, success, email="", api_key="", latency=None, error_msg="", test_status=None):
        with self.lock:
            self.completed_count += 1
            if success:
                self.success_count += 1
                self.results.append({
                    "email": email,
                    "success": True,
                    "api_key": api_key,
                    "latency": latency,
                    "test_status": test_status,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
            else:
                self.failed_count += 1
                self.results.append({
                    "email": email or f"Worker-{worker_id}",
                    "success": False,
                    "error": error_msg,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
            
            if worker_id in self.workers:
                self.workers[worker_id]["status"] = "[grey50]Idle (Selesai)[/grey50]"
                self.workers[worker_id]["email"] = ""
                self.workers[worker_id]["percentage"] = 0

def get_stage_percentage(status: str) -> int:
    status_lower = status.lower()
    if "browser" in status_lower and "menutup" in status_lower: return 100
    if "browser" in status_lower: return 2
    if "tab 1" in status_lower or "navigasi ke pendaftaran" in status_lower: return 5
    if "mailbox baru" in status_lower: return 10
    if "dashboard inbox" in status_lower: return 15
    if "gomail aktif" in status_lower: return 20
    if "tab 2" in status_lower or "login alibaba" in status_lower: return 25
    if "sign up now" in status_lower: return 30
    if "tombol next" in status_lower: return 35
    if "pendaftaran..." in status_lower or "memasukkan email" in status_lower: return 40
    if "password" in status_lower: return 45
    if "step 1 of 2" in status_lower: return 50
    if "verifikasi email" in status_lower or "otp..." in status_lower: return 55
    if "memantau" in status_lower or "kotak masuk" in status_lower: return 60
    if "otp masuk" in status_lower or "disalin" in status_lower: return 65
    if "otp ke form" in status_lower or "persetujuan ketentuan" in status_lower: return 70
    if "step 2 of 2" in status_lower: return 75
    if "registrasi alibaba" in status_lower: return 80
    if "tab 3" in status_lower or "pendaftaran qwen" in status_lower: return 85
    if "api keys" in status_lower or "popup" in status_lower or "syarat" in status_lower or "persetujuan" in status_lower or "kuota gratis" in status_lower: return 90
    if "create api key" in status_lower or "menghasilkan api" in status_lower or "menyalin api" in status_lower or "tersalin" in status_lower or "tersimpan" in status_lower or "menguji" in status_lower: return 95
    if "selesai" in status_lower: return 100
    return 0

def generate_layout(state: DashboardState) -> Panel:
    # 1. Progress Bar (Overall)
    percent = (state.completed_count / state.total_accounts) * 100 if state.total_accounts > 0 else 0
    filled = int(20 * state.completed_count // state.total_accounts) if state.total_accounts > 0 else 0
    bar = "█" * filled + "░" * (20 - filled)
    
    elapsed = int(time.time() - state.start_time)
    
    lines = []
    with state.lock:
        # Show workers
        for slot_id, data in sorted(state.workers.items()):
            status_text = data['status']
            if "Idle" in status_text or not status_text:
                lines.append(
                    f"  [grey50]»[/grey50] [grey50]WORKER-{slot_id:<2}[/grey50] [grey30]Idle (Menunggu antrean...)[/grey30]"
                )
                continue
                
            pct = data.get("percentage", 0)
            filled_w = pct // 10
            bar_w = "█" * filled_w + "░" * (10 - filled_w)
            
            name = data['email'] if data['email'] else f"WORKER-{slot_id}"
            lines.append(
                f"  [bold yellow]»[/bold yellow] [yellow]WORKER-{slot_id:<2}[/yellow] {name:<30} | [[yellow]{bar_w}[/yellow]] {pct:>3}% [cyan]({status_text})[/cyan]"
            )
            
    accounts_str = "\n".join(lines) if lines else "  (Belum ada proses berjalan)"
    
    layout_content = (
        f"[bold cyan]⚡ PROSES PEMBUATAN AKUN QWEN CLOUD[/bold cyan]  [magenta]Elapsed: {elapsed}s[/magenta]\n"
        f"Progress: [[green]{bar}[/green]] {percent:.1f}% ({state.completed_count}/{state.total_accounts}) | [green]✓ {state.success_count}[/green] | [red]✗ {state.failed_count}[/red]\n"
        f"[grey30]─────────────────────────────────────────────────────────────────[/grey30]\n"
        f"{accounts_str}"
    )
    
    return Panel(layout_content, border_style="cyan", title="[bold white]DASHBOARD AUTOMATION[/bold white]")

async def find_element(page, selector, timeout_ms=20000):
    """Finds an element on the main page or within any iframe."""
    try:
        element = await page.wait_for_selector(selector, timeout=1000)
        if element:
            return page, element
    except Exception:
        pass
        
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout_ms:
        try:
            element = await page.query_selector(selector)
            if element:
                return page, element
        except Exception:
            pass
        for frame in page.frames:
            try:
                element = await frame.query_selector(selector)
                if element:
                    return frame, element
            except Exception:
                pass
        await asyncio.sleep(0.5)
    raise Exception(f"Timeout waiting for selector: {selector}")

def generate_human_bezier_curve(start_x, start_y, end_x, end_y, steps=30):
    """Generates cubic Bezier curve points with human-like acceleration and tremors."""
    import math
    points = []
    dist = math.hypot(end_x - start_x, end_y - start_y)
    
    # Hand curves more on larger distances
    offset_scale = min(60.0, dist * 0.18)
    ctrl_x1 = start_x + (end_x - start_x) * random.uniform(0.1, 0.3) + random.uniform(-offset_scale, offset_scale)
    ctrl_y1 = start_y + (end_y - start_y) * random.uniform(0.15, 0.4) + random.uniform(-offset_scale, offset_scale)
    ctrl_x2 = start_x + (end_x - start_x) * random.uniform(0.7, 0.9) + random.uniform(-offset_scale, offset_scale)
    ctrl_y2 = start_y + (end_y - start_y) * random.uniform(0.6, 0.85) + random.uniform(-offset_scale, offset_scale)
    
    for i in range(steps + 1):
        t = i / steps
        # Cubic Bezier formula
        x = (1-t)**3 * start_x + 3*(1-t)**2 * t * ctrl_x1 + 3*(1-t) * t**2 * ctrl_x2 + t**3 * end_x
        y = (1-t)**3 * start_y + 3*(1-t)**2 * t * ctrl_y1 + 3*(1-t) * t**2 * ctrl_y2 + t**3 * end_y
        
        # Add micro-tremor (hand shake) which decreases as mouse gets closer to target
        if 0 < i < steps:
            shake_factor = (1.0 - t) * 1.5
            x += random.uniform(-shake_factor, shake_factor)
            y += random.uniform(-shake_factor, shake_factor)
            
        points.append((x, y))
    return points

async def get_mouse_position(page):
    """Retrieves or initializes the current mouse coordinates on the page."""
    if not hasattr(page, 'current_mouse_x') or page.current_mouse_x is None:
        page.current_mouse_x = random.uniform(100, 500)
        page.current_mouse_y = random.uniform(100, 500)
        # Move mouse to initial position silently
        main_page = page if hasattr(page, 'mouse') else page.page
        await main_page.mouse.move(page.current_mouse_x, page.current_mouse_y)
    return page.current_mouse_x, page.current_mouse_y

async def human_move_mouse_to_element(page, element, slow_mode=False):
    """Moves the mouse smoothly to the element's center along a humanized Bezier curve."""
    import math
    box = await element.bounding_box()
    if not box:
        return None
        
    main_page = page if hasattr(page, 'mouse') else page.page
    
    # Target coordinate inside the element with slight random offset
    target_x = box['x'] + box['width'] / 2 + random.uniform(-4, 4)
    target_y = box['y'] + box['height'] / 2 + random.uniform(-4, 4)
    
    start_x, start_y = await get_mouse_position(main_page)
    
    # Human curve steps (24 to 36 steps to look natural, not teleporting)
    steps = random.randint(24, 36) if slow_mode else random.randint(18, 26)
    points = generate_human_bezier_curve(start_x, start_y, target_x, target_y, steps=steps)
    
    for i, (px, py) in enumerate(points):
        await main_page.mouse.move(px, py)
        
        # Human speed profile (Easing: slower at start/end, fast in the middle)
        t = i / steps
        delay_factor = 1.0 - math.sin(t * math.pi) # 1 at start/end, 0 in middle
        delay = 0.005 + (delay_factor * 0.015 if slow_mode else delay_factor * 0.008)
        delay += random.uniform(0.001, 0.004)
        
        await asyncio.sleep(delay)
        
    main_page.current_mouse_x = target_x
    main_page.current_mouse_y = target_y
    
    await asyncio.sleep(random.uniform(0.12, 0.28))
    return target_x, target_y

async def click_element(page, selector, timeout_ms=20000, slow_mode=False):
    await asyncio.sleep(random.uniform(0.2, 0.5) if slow_mode else random.uniform(0.05, 0.15))
    container, element = await find_element(page, selector, timeout_ms)
    await element.scroll_into_view_if_needed()
    
    coords = await human_move_mouse_to_element(container, element, slow_mode=slow_mode)
    main_page = page if hasattr(page, 'mouse') else page.page
    
    if coords:
        x, y = coords
        await main_page.mouse.click(x, y)
    else:
        await element.click()
        
    await asyncio.sleep(random.uniform(0.3, 0.6) if slow_mode else random.uniform(0.15, 0.3))

async def fill_element(page, selector, value, timeout_ms=20000, slow_mode=False):
    await asyncio.sleep(random.uniform(0.2, 0.5) if slow_mode else random.uniform(0.05, 0.15))
    container, element = await find_element(page, selector, timeout_ms)
    await element.scroll_into_view_if_needed()
    
    coords = await human_move_mouse_to_element(container, element, slow_mode=slow_mode)
    main_page = page if hasattr(page, 'mouse') else page.page
    
    if coords:
        x, y = coords
        await main_page.mouse.click(x, y)
    else:
        await element.click()
        
    await element.press("Control+A")
    await element.press("Backspace")
    await asyncio.sleep(random.uniform(0.1, 0.2) if slow_mode else random.uniform(0.05, 0.1))
    
    for char in value:
        await element.type(char)
        if slow_mode:
            # Slower, natural typing delay
            await asyncio.sleep(random.uniform(0.04, 0.09))
        else:
            # Fast typing delay
            await asyncio.sleep(random.uniform(0.005, 0.012))
        
    await asyncio.sleep(random.uniform(0.3, 0.6) if slow_mode else random.uniform(0.1, 0.2))

async def check_element(page, selector, timeout_ms=20000, slow_mode=False):
    await asyncio.sleep(random.uniform(0.2, 0.5) if slow_mode else random.uniform(0.05, 0.15))
    container, element = await find_element(page, selector, timeout_ms)
    await element.scroll_into_view_if_needed()
    
    is_checked = await element.is_checked()
    if not is_checked:
        coords = await human_move_mouse_to_element(container, element, slow_mode=slow_mode)
        main_page = page if hasattr(page, 'mouse') else page.page
        
        clicked = False
        if coords:
            try:
                x, y = coords
                await main_page.mouse.click(x, y)
                clicked = True
            except Exception:
                pass
                
        if not clicked:
            try:
                parent_label = await element.evaluate_handle("el => el.closest('label') || el.closest('span.next-checkbox') || el")
                parent_el = parent_label.as_element()
                if parent_el:
                    await parent_el.click()
                else:
                    await element.check(force=True)
            except Exception:
                try:
                    await element.check(force=True)
                except Exception:
                    pass
                    
        await asyncio.sleep(0.2 if slow_mode else 0.1)
        try:
            if not await element.is_checked():
                await element.check(force=True)
        except Exception:
            pass
            
    await asyncio.sleep(random.uniform(0.3, 0.6) if slow_mode else random.uniform(0.15, 0.3))

async def check_slider_exists(page):
    slider_selector = '#nc_1_n1z, .btn_slide, span.nc_iconfont.btn_slide, span[id*="_n1z"]'
    try:
        # Cek cepat di halaman utama
        el = await page.query_selector(slider_selector)
        if el and await el.is_visible():
            return page, el
    except Exception:
        pass
    
    # Cek cepat di setiap frame
    for frame in page.frames:
        try:
            el = await frame.query_selector(slider_selector)
            if el and await el.is_visible():
                return frame, el
        except Exception:
            pass
    return None, None

async def solve_slider_captcha(page, status_callback=None, email="", timeout_ms=5000):
    import math
    
    # Cek cepat awal apakah ada slider. Jika tidak ada, langsung keluar diam-diam.
    container, element = await check_slider_exists(page)
    if not element:
        return False
        
    # Mencoba mendeteksi dan menyelesaikan slider captcha hingga 3 kali percobaan
    for attempt in range(1, 4):
        try:
            if attempt > 1:
                container, element = await check_slider_exists(page)
                if not element or not await element.is_visible():
                    return True
                
            # Tunggu acak 0.5-1.2 detik setelah muncul captcha sebelum mulai menggeser
            delay_wait = random.uniform(0.5, 1.2)
            if status_callback:
                await status_callback(f"Mendeteksi captcha geser (percobaan {attempt}/3). Menunggu {delay_wait:.2f}s...", email)
            await asyncio.sleep(delay_wait)
            
            box = await element.bounding_box()
            if not box:
                return False
                
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.15, 0.3))
            
            # Ambil kembali bounding box terbaru setelah scroll
            box = await element.bounding_box()
            if not box:
                return False
                
            main_page = page if hasattr(page, 'mouse') else page.page
            
            # Tentukan posisi mouse awal di bagian bawah halaman (seakan kursor sedang diam/istirahat di bawah)
            resting_x = box['x'] + random.uniform(-100, 100)
            resting_y = box['y'] + box['height'] + random.uniform(150, 300)
            
            # Pastikan posisi awal kursor berada dalam batasan layar yang aman
            resting_x = max(80, min(1200, resting_x))
            resting_y = max(350, min(680, resting_y))
            
            # Tempatkan kursor mouse di bagian bawah terlebih dahulu
            main_page.current_mouse_x = resting_x
            main_page.current_mouse_y = resting_y
            await main_page.mouse.move(resting_x, resting_y)
            await asyncio.sleep(random.uniform(0.15, 0.3))
            
            # Pindahkan kursor mouse dari posisi bawah ke tombol slider secara halus menggunakan kurva Bezier
            coords = await human_move_mouse_to_element(container, element, slow_mode=True)
            if not coords:
                return False
            start_x, start_y = coords
            
            # Klik dan tahan tombol
            await main_page.mouse.down()
            await asyncio.sleep(random.uniform(0.1, 0.2))
            
            # Cari lebar track secara dinamis dari parent/container slider terdekat (seperti .nc_scale atau #nc_1__scale_text)
            try:
                track_width = await element.evaluate("el => { const p = el.closest('.nc_scale') || el.closest('#nc_1__scale_text') || el.parentElement; return p ? p.clientWidth : 300; }")
                if not track_width or track_width < 100:
                    track_width = 300
            except Exception:
                track_width = 300
                
            # Tarik melampaui lebar tombol agar benar-benar mentok ke kanan
            drag_distance = int(track_width - (box['width'] / 2) + random.randint(15, 30))
            if drag_distance < 260:
                drag_distance = random.randint(290, 320)
                
            # Drag steps (28-40 steps is optimal for human-like speed control)
            steps = random.randint(28, 40)
            max_y_drift = random.uniform(-8.0, 8.0)
            
            x_tremor, x_velocity = 0.0, 0.0
            y_tremor, y_velocity = 0.0, 0.0
            
            points = []
            for i in range(steps):
                percent = (i + 1) / steps
                
                # Easing curve non-linear (Cubic ease-in-out)
                if percent < 0.5:
                    step_factor = 4 * percent * percent * percent
                else:
                    f = ((2 * percent) - 2)
                    step_factor = 0.5 * f * f * f + 1
                
                base_x = start_x + (drag_distance * step_factor)
                
                # Tremor mikro pada sumbu X
                x_accel = random.uniform(-0.15, 0.15) - 0.08 * x_velocity
                x_velocity += x_accel
                x_tremor += x_velocity
                x_tremor = max(-1.2, min(1.2, x_tremor))
                target_x = base_x + x_tremor
                
                # Drift makro melengkung pada sumbu Y
                macro_y = max_y_drift * math.sin(percent * math.pi)
                y_accel = random.uniform(-0.2, 0.2) - 0.12 * y_velocity
                y_velocity += y_accel
                y_tremor += y_velocity
                y_tremor = max(-1.8, min(1.8, y_tremor))
                target_y = start_y + macro_y + y_tremor
                
                points.append((target_x, target_y))
            
            # Move mouse step-by-step with natural easing speed profile
            for i, (px, py) in enumerate(points):
                await main_page.mouse.move(px, py)
                
                t = (i + 1) / steps
                # Drag easing: slower at start and end (muscle inertia), fast in the middle
                delay_factor = 1.0 - math.sin(t * math.pi)
                delay = 0.004 + (delay_factor * 0.012)
                delay += random.uniform(0.001, 0.003)
                
                await asyncio.sleep(delay)
                
            # Efek Overshoot (tarikan sedikit melampaui batas akhir sebelum dilepas)
            overshoot_distance = random.randint(8, 16)
            overshoot_x = start_x + drag_distance + overshoot_distance
            overshoot_y = start_y + random.uniform(-1, 1)
            overshoot_steps = random.randint(3, 5)
            for j in range(overshoot_steps):
                p = (j + 1) / overshoot_steps
                curr_x = (start_x + drag_distance) + (overshoot_distance * p)
                await main_page.mouse.move(curr_x, overshoot_y)
                await asyncio.sleep(random.uniform(0.012, 0.022))
                
            await asyncio.sleep(random.uniform(0.06, 0.12))
            
            # Efek Recoil (kembali sedikit ke kiri sebelum melepas klik)
            recoil_x = start_x + drag_distance + random.randint(1, 4)
            recoil_y = start_y + random.uniform(-1, 1)
            recoil_steps = random.randint(2, 4)
            for j in range(recoil_steps):
                p = (j + 1) / recoil_steps
                curr_x = overshoot_x - ((overshoot_x - recoil_x) * p)
                await main_page.mouse.move(curr_x, recoil_y)
                await asyncio.sleep(random.uniform(0.015, 0.025))
                
            await asyncio.sleep(random.uniform(0.08, 0.15))
            
            # Lepas mouse
            await main_page.mouse.up()
            
            # Tunggu respon halaman
            await asyncio.sleep(2.0)
            
            # Cek status kelolosan
            page_content = await page.content()
            if "periksa koneksi jaringan Anda" in page_content or "coba lagi" in page_content or "refresh" in page_content.lower():
                if status_callback:
                    await status_callback("Penyelesaian slider diblokir/gagal. Mencoba menyegarkan captcha...", email)
                # Klik tombol refresh jika ada
                refresh_selectors = ['a:has-text("coba lagi")', 'a:has-text("refresh")', '.nc-lang-cnt a', '#rectMask']
                for r_sel in refresh_selectors:
                    try:
                        r_el = await container.query_selector(r_sel)
                        if r_el and await r_el.is_visible():
                            await r_el.click()
                            await asyncio.sleep(2.0)
                            break
                    except Exception:
                        pass
                continue # Coba lagi di iterasi berikutnya
            else:
                if status_callback:
                    await status_callback("Captcha geser berhasil dilewati.", email)
                return True
                
        except Exception as e:
            debug_log(f"Slider captcha attempt {attempt} error: {e}")
            await asyncio.sleep(2.0)
            
    return False

async def click_element_helper(frame_or_page, element, slow_mode=False):
    main_page = frame_or_page if hasattr(frame_or_page, 'mouse') else frame_or_page.page
    coords = await human_move_mouse_to_element(frame_or_page, element, slow_mode=slow_mode)
    if coords:
        x, y = coords
        await main_page.mouse.click(x, y)
    else:
        await element.click()
    await asyncio.sleep(random.uniform(0.2, 0.5) if slow_mode else random.uniform(0.1, 0.3))

async def find_ok_button_in_container(frame_or_page, container, status_callback, email):
    btn_selectors = [
        'button:has-text("OK")',
        'button:has-text("Ok")',
        'button:text-is("OK")',
        '.next-btn-primary',
        '.next-dialog-btn',
        '.ant-btn-primary',
        '[role="button"]:has-text("OK")',
        '[role="button"]:has-text("Ok")',
        'span:text-is("OK")',
        'span:text-is("Ok")',
        'button:has-text("Create API key")'
    ]
    for sel in btn_selectors:
        try:
            el = await container.query_selector(sel)
            if el and await el.is_visible():
                await status_callback(f"Menutup popup Region di dialog ({sel})...", email)
                await click_element_helper(frame_or_page, el)
                return el
        except Exception:
            pass
    return None

async def find_ok_button_globally(page, status_callback, email):
    ok_selectors = [
        'button:has-text("OK")',
        'button:has-text("Ok")',
        'button:text-is("OK")',
        '.next-btn-primary',
        '.next-dialog-btn',
        '.ant-btn-primary',
        '[role="button"]:has-text("OK")',
        '[role="button"]:has-text("Ok")',
        'span:text-is("OK")',
        'span:text-is("Ok")'
    ]
    for selector in ok_selectors:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await status_callback(f"Menutup popup Region global ({selector})...", email)
                await click_element_helper(page, el)
                return True
        except Exception:
            pass
        for frame in page.frames:
            try:
                el = await frame.query_selector(selector)
                if el and await el.is_visible():
                    await status_callback(f"Menutup popup Region global di frame ({selector})...", email)
                    await click_element_helper(frame, el)
                    return True
            except Exception:
                pass
    return False

async def handle_first_use_popups(page, status_callback, email):
    await status_callback("Menangani popup pengguna pertama kali...", email)
    await page.wait_for_timeout(500)
    
    original_url = page.url
    
    # 1. Tutup popup region initialization
    try:
        dialog_selectors = [
            '[role="dialog"]',
            '.next-dialog',
            '.ant-modal',
            '.next-overlay-wrapper',
            '.next-dialog-container'
        ]
        
        dialog_found = False
        for ds in dialog_selectors:
            try:
                dialogs = await page.query_selector_all(ds)
                for dialog in dialogs:
                    if await dialog.is_visible():
                        ok_btn = await find_ok_button_in_container(page, dialog, status_callback, email)
                        if ok_btn:
                            dialog_found = True
                            break
            except Exception:
                pass
            if dialog_found:
                break
                
            for frame in page.frames:
                try:
                    dialogs = await frame.query_selector_all(ds)
                    for dialog in dialogs:
                        if await dialog.is_visible():
                            ok_btn = await find_ok_button_in_container(frame, dialog, status_callback, email)
                            if ok_btn:
                                dialog_found = True
                                break
                except Exception:
                    pass
                if dialog_found:
                    break
            if dialog_found:
                break
                
        if not dialog_found:
            await find_ok_button_globally(page, status_callback, email)
    except Exception as e:
        debug_log(f"Error closing region popup: {e}")
        
    # 2. Cek dan setujui checkbox persetujuan syarat di konsol jika ada
    try:
        cb_selectors = 'input[type="checkbox"], span.next-checkbox-input input, input.maas-terms-text__checkbox'
        all_checkboxes = []
        
        try:
            cbs = await page.query_selector_all(cb_selectors)
            for cb in cbs:
                all_checkboxes.append((page, cb))
        except Exception:
            pass
            
        for frame in page.frames:
            try:
                cbs = await frame.query_selector_all(cb_selectors)
                for cb in cbs:
                    all_checkboxes.append((frame, cb))
            except Exception:
                pass
                
        for frame_or_page, cb in all_checkboxes:
            if await cb.is_visible() and not await cb.is_checked():
                await status_callback("Mencentang persetujuan syarat & ketentuan...", email)
                await cb.check(force=True)
                await page.wait_for_timeout(200)
    except Exception as e:
        debug_log(f"Error checking terms checkboxes: {e}")
        
    # 3. Cek dan klik tombol persetujuan/aktivasi
    try:
        agree_selectors = [
            'button:has-text("Agree")',
            'button:has-text("Activate")',
            'button:has-text("Confirm")',
            'button:has-text("Agree and Activate")',
            'button:has-text("Accept")',
            'button:has-text("Setuju")',
            'button:has-text("Aktifkan")'
        ]
        
        all_buttons = []
        for sel in agree_selectors:
            try:
                btns = await page.query_selector_all(sel)
                for btn in btns:
                    all_buttons.append((page, btn))
            except Exception:
                pass
            for frame in page.frames:
                try:
                    btns = await frame.query_selector_all(sel)
                    for btn in btns:
                        all_buttons.append((frame, btn))
                except Exception:
                    pass
                    
        for frame_or_page, btn in all_buttons:
            text = await btn.inner_text()
            if await btn.is_visible() and not any(x in text.lower() for x in ["create", "cancel", "batal"]):
                await status_callback(f"Mengeklik tombol persetujuan: {text}...", email)
                await btn.click()
                await page.wait_for_timeout(400)
                break
    except Exception as e:
        debug_log(f"Error clicking agree/activate buttons: {e}")
 
    # 4. Navigasi ke halaman Kuota Gratis dan aktifkan (Best Effort)
    try:
        await status_callback("Membuka halaman Kuota Gratis...", email)
        console_base = original_url.split('#')[0]
        free_quota_url = f"{console_base}#/billing/free-quota"
        await page.goto(free_quota_url, timeout=15000)
        await page.wait_for_load_state()
        await page.wait_for_timeout(500)
        
        # Cari tombol aktivasi/klaim di halaman kuota gratis
        quota_selectors = 'button:has-text("Activate"), button:has-text("Claim"), button:has-text("Subscribe"), button:has-text("Open")'
        all_quota_buttons = []
        
        try:
            q_btns = await page.query_selector_all(quota_selectors)
            for q_btn in q_btns:
                all_quota_buttons.append(q_btn)
        except Exception:
            pass
            
        for frame in page.frames:
            try:
                q_btns = await frame.query_selector_all(quota_selectors)
                for q_btn in q_btns:
                    all_quota_buttons.append(q_btn)
            except Exception:
                pass
                
        activated_any = False
        for q_btn in all_quota_buttons:
            if await q_btn.is_visible():
                q_text = await q_btn.inner_text()
                await status_callback(f"Mengaktifkan kuota gratis: {q_text}...", email)
                await q_btn.click()
                await page.wait_for_timeout(400)
                activated_any = True
        
        if activated_any:
            await status_callback("Kuota gratis berhasil diaktifkan.", email)
            
        # Kembali ke halaman API Key semula
        await status_callback("Kembali ke halaman API Key...", email)
        await page.goto(original_url, timeout=15000)
        await page.wait_for_load_state()
        await page.wait_for_timeout(400)
    except Exception as e:
        debug_log(f"Error activating free quota: {e}")
        try:
            await page.goto(original_url, timeout=15000)
        except Exception:
            pass

async def click_and_get_page(context, page, selector, timeout_ms=20000, slow_mode=False):
    """
    Clicks an element and safely retrieves the resulting page,
    regardless of whether it opens in a new tab or loading in the same page.
    """
    is_blank = False
    try:
        container, element = await find_element(page, selector, 3000)
        target = await element.get_attribute("target")
        if target == "_blank":
            is_blank = True
    except Exception:
        pass

    if is_blank:
        try:
            async with context.expect_page() as new_page_info:
                await click_element(page, selector, timeout_ms, slow_mode=slow_mode)
            new_page = await new_page_info.value
            await new_page.wait_for_load_state()
            return new_page
        except Exception:
            pass

    try:
        async with context.expect_page(timeout=6000) as new_page_info:
            await click_element(page, selector, timeout_ms, slow_mode=slow_mode)
        new_page = await new_page_info.value
        await new_page.wait_for_load_state()
        return new_page
    except Exception:
        await page.wait_for_load_state()
        return page

async def run_automation(mailbox_password, status_callback, headless=True):
    # 1. Mulai otomatisasi browser menggunakan Playwright
    async with async_playwright() as p:
        await status_callback("Membuka browser Chromium...")
        
        browser = await p.chromium.launch(
            headless=headless,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--no-zygote",
                "--disable-features=Translate",
                "--disable-translate"
            ]
        )
        
        # Buat context baru dengan User Agent standard, locale en-US agar tidak diterjemahkan otomatis
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            timezone_id="Asia/Jakarta"
        )
        
        # Script Anti-Fingerprinting (Stealth) untuk menyamarkan status otomatisasi
        stealth_script = """
        // Helpers to mock native methods
        const mockToString = (fn, name) => {
            const bound = Function.prototype.toString.bind(fn);
            Object.defineProperty(fn, 'toString', {
                value: function() {
                    if (this === fn) return `function ${name || fn.name}() { [native code] }`;
                    return bound();
                },
                writable: true,
                configurable: true
            });
        };

        // 1. Hapus penanda Webdriver di prototype
        try {
            if (Navigator.prototype.hasOwnProperty('webdriver')) {
                delete Navigator.prototype.webdriver;
            }
        } catch (e) {}
        try {
            if (navigator.hasOwnProperty('webdriver')) {
                delete navigator.webdriver;
            }
        } catch (e) {}
        
        // 2. Simulasikan plugin standard di prototype menggunakan real PluginArray & Plugin
        try {
            const makePlugin = (name, filename, description) => {
                const p = Object.create(Plugin.prototype);
                Object.defineProperties(p, {
                    name: { value: name, enumerable: true },
                    filename: { value: filename, enumerable: true },
                    description: { value: description, enumerable: true },
                    length: { value: 0 }
                });
                return p;
            };
            const mockPlugins = [
                makePlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
                makePlugin('Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
                makePlugin('Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
                makePlugin('Microsoft Edge PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
                makePlugin('WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format')
            ];
            const pluginArray = Object.create(PluginArray.prototype);
            mockPlugins.forEach((p, i) => {
                Object.defineProperty(pluginArray, i, { value: p, enumerable: true });
                Object.defineProperty(pluginArray, p.name, { value: p });
            });
            Object.defineProperties(pluginArray, {
                length: { value: mockPlugins.length, enumerable: true },
                item: {
                    value: function(index) { return mockPlugins[index]; },
                    writable: true,
                    configurable: true
                },
                namedItem: {
                    value: function(name) { return mockPlugins.find(p => p.name === name); },
                    writable: true,
                    configurable: true
                }
            });
            mockToString(pluginArray.item, 'item');
            mockToString(pluginArray.namedItem, 'namedItem');
            
            Object.defineProperty(Navigator.prototype, 'plugins', {
                get: () => pluginArray,
                configurable: true,
                enumerable: true
            });
        } catch (e) {}
        
        // 3. Simulasikan bahasa Indonesia di prototype
        try {
            Object.defineProperty(Navigator.prototype, 'languages', {
                get: () => ['id-ID', 'id', 'en-US', 'en'],
                configurable: true,
                enumerable: true
            });
            Object.defineProperty(Navigator.prototype, 'language', {
                get: () => 'id-ID',
                configurable: true,
                enumerable: true
            });
        } catch (e) {}
        
        // 4. Simulasikan objek chrome runtime
        try {
            if (!window.chrome) {
                window.chrome = {};
            }
            const app = {
                isInstalled: false,
                InstallState: {
                    DISABLED: 'disabled',
                    INSTALLED: 'installed',
                    NOT_INSTALLED: 'not_installed'
                },
                RunningState: {
                    CANNOT_RUN: 'cannot_run',
                    READY_TO_RUN: 'ready_to_run',
                    RUNNING: 'running'
                },
                getDetails: function() {},
                getIsInstalled: function() {},
                install: function() {}
            };
            mockToString(app.getDetails, 'getDetails');
            mockToString(app.getIsInstalled, 'getIsInstalled');
            mockToString(app.install, 'install');
            window.chrome.app = app;

            const runtime = {
                OnInstalledReason: {
                    CHROME_UPDATE: 'chrome_update',
                    INSTALL: 'install',
                    SHARED_MODULE_UPDATE: 'shared_module_update',
                    UPDATE: 'update'
                },
                OnRestartRequiredReason: {
                    APP_UPDATE: 'app_update',
                    OS_UPDATE: 'os_update',
                    PERIODIC: 'periodic'
                },
                PlatformArch: {
                    ARM: 'arm',
                    ARM64: 'arm64',
                    MIPS: 'mips',
                    MIPS64: 'mips64',
                    X86_32: 'x86-32',
                    X86_64: 'x86-64'
                },
                PlatformNaclArch: {
                    ARM: 'arm',
                    MIPS: 'mips',
                    MIPS64: 'mips64',
                    X86_32: 'x86-32',
                    X86_64: 'x86-64'
                },
                PlatformOs: {
                    ANDROID: 'android',
                    CROS: 'cros',
                    LINUX: 'linux',
                    MAC: 'mac',
                    OPENBSD: 'openbsd',
                    WIN: 'win'
                },
                RequestUpdateCheckStatus: {
                    NO_UPDATE: 'no_update',
                    THROTTLED: 'throttled',
                    UPDATE_AVAILABLE: 'update_available'
                },
                connect: function() {},
                sendMessage: function() {}
            };
            mockToString(runtime.connect, 'connect');
            mockToString(runtime.sendMessage, 'sendMessage');
            window.chrome.runtime = runtime;
        } catch (e) {}
        
        // 5. Simulasikan permissions query
        try {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            mockToString(window.navigator.permissions.query, 'query');
        } catch (e) {}

        // 6. Simulasikan WebGL getParameter vendor & renderer hardware nyata (GeForce RTX 3060)
        try {
            const getParameterProxy = {
                apply: function(target, thisArg, args) {
                    const param = args[0];
                    // UNMASKED_VENDOR_WEBGL (37445)
                    if (param === 37445) {
                        return 'Google Inc. (NVIDIA)';
                    }
                    // UNMASKED_RENDERER_WEBGL (37446)
                    if (param === 37446) {
                        return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                    }
                    return Reflect.apply(target, thisArg, args);
                }
            };
            
            const addWebGLProxy = (proto) => {
                if (proto && proto.getParameter) {
                    proto.getParameter = new Proxy(proto.getParameter, getParameterProxy);
                    mockToString(proto.getParameter, 'getParameter');
                }
            };
            
            addWebGLProxy(WebGLRenderingContext.prototype);
            addWebGLProxy(WebGL2RenderingContext.prototype);
        } catch (e) {}
        """
        await context.add_init_script(stealth_script)
        
        # Target URL registrasi Qwen Cloud
        target_url = os.environ.get(
            "TARGET_URL",
            "https://home.qwencloud.com"
        )
        
        # Generate username acak dengan nama manusia random untuk email baru
        username = generate_human_username()
        
        try:
            # --- 1. MEMBUAT AKUN GOMAIL BARU DI MAIL.GOPRETSTUDIO.COM ---
            await status_callback("Membuka Tab 1 untuk GoMail...")
            mail_page = await context.new_page()
            
            await status_callback("Navigasi ke pendaftaran GoMail...")
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    await mail_page.goto("https://mail.gopretstudio.com/signup", timeout=45000)
                    break
                except Exception as e:
                    if attempt == max_retries:
                        raise e
                    await status_callback(f"Gagal memuat GoMail (percobaan {attempt}/{max_retries}), mencoba lagi dalam 5 detik...")
                    await asyncio.sleep(5)
            
            # Mengisi formulir pendaftaran GoMail
            await status_callback("Mengisi form pendaftaran GoMail...")
            await fill_element(mail_page, "input#signup-username", username, slow_mode=False)
            await fill_element(mail_page, "input#signup-password", mailbox_password, slow_mode=False)
            await fill_element(mail_page, "input#signup-confirm", mailbox_password, slow_mode=False)
            
            # Memilih domain GoMail secara acak dari combobox
            try:
                await status_callback("Membuka dropdown domain GoMail...")
                await click_element(mail_page, 'button[role="combobox"]', slow_mode=False)
                await mail_page.wait_for_selector('[role="option"]', timeout=10000)
                options = await mail_page.query_selector_all('[role="option"]')
                if options:
                    selected_option = random.choice(options)
                    domain_text = await selected_option.inner_text()
                    await status_callback(f"Memilih domain GoMail secara acak: {domain_text.strip()}...")
                    await selected_option.click()
                    await mail_page.wait_for_timeout(200)
                else:
                    await status_callback("Gagal menemukan opsi domain, menggunakan domain default...")
            except Exception as e:
                await status_callback(f"Gagal memilih domain acak ({str(e)}), menggunakan default...")
            
            # Dapatkan domain yang sedang aktif terpilih di select combobox secara dinamis
            domain_element = await mail_page.query_selector('button[role="combobox"] span[data-slot="select-value"]')
            domain_suffix = await domain_element.inner_text() if domain_element else "@awdigi.dev"
            domain_suffix = domain_suffix.strip()
            if not domain_suffix.startswith("@"):
                domain_suffix = f"@{domain_suffix}"
            target_signup_email = f"{username}{domain_suffix}"
            
            await status_callback("Mengirim form pendaftaran mailbox baru...", target_signup_email)
            
            # Beri jeda agar tombol Create Account beralih dari disabled ke enabled
            create_btn_selector = 'button[type="submit"]:has-text("Create Account")'
            await mail_page.wait_for_selector(create_btn_selector, timeout=5000)
            await mail_page.wait_for_timeout(100)
            await click_element(mail_page, create_btn_selector, slow_mode=False)
            
            # Tunggu elemen dashboard utama ter-render (menandakan pendaftaran berhasil)
            await status_callback("Menunggu dashboard inbox GoMail dimuat...", target_signup_email)
            await mail_page.wait_for_selector('h1:has-text("Inbox")', timeout=10000)
            await status_callback("Inbox GoMail aktif di Tab 1.", target_signup_email)
            
            # --- 2. BUKA BROWSER UNTUK ALIBABA CLOUD / QWEN ---
            alibabacloud_login_url = "https://account.alibabacloud.com/login/login.htm?oauth_callback=https%3A%2F%2Fmodelstudio.console.alibabacloud.com%2Fap-southeast-1%3Ftab%3Ddoc%23%2Fdoc%2F%3Ftype%3Dmodel%26url%3D2840914&clearRedirectCookie=1"
            await status_callback("Membuka halaman login Alibaba Cloud...", target_signup_email)
            qwen_page = await context.new_page()
            await qwen_page.goto(alibabacloud_login_url, timeout=30000, wait_until="domcontentloaded")
            await qwen_page.wait_for_timeout(800) # Istirahat 800ms
            await solve_slider_captcha(qwen_page, status_callback, target_signup_email)
            
            # 1. Klik link signup
            await status_callback("Mengeklik link Sign Up Now...", target_signup_email)
            await click_element(qwen_page, 'a:has-text("Sign Up Now"), a:has-text("Sign Up"), a:has-text("Daftar Sekarang"), a[href*="intl_register"]', slow_mode=False)
            await qwen_page.wait_for_load_state()
            await qwen_page.wait_for_timeout(800) # Istirahat 800ms
            await solve_slider_captcha(qwen_page, status_callback, target_signup_email)
            await qwen_page.wait_for_timeout(200) # Jeda agar elemen form ter-render stabil
            
            # 2. Klik Next
            await status_callback("Mengeklik tombol Next...", target_signup_email)
            await click_element(qwen_page, 'a.entity__btn-next, a:has-text("Next"), a:has-text("Berikutnya")', slow_mode=False)
            await qwen_page.wait_for_load_state()
            await qwen_page.wait_for_timeout(800) # Istirahat 800ms
            
            # 3. Masukkan email
            await status_callback("Memasukkan email pendaftaran...", target_signup_email)
            await fill_element(qwen_page, 'input#email', target_signup_email, slow_mode=False)
            
            # 4. Masukkan password
            await status_callback("Memasukkan password...", target_signup_email)
            await fill_element(qwen_page, 'input#password', mailbox_password, slow_mode=False)
            
            # 5. Konfirmasi password
            await status_callback("Memasukkan konfirmasi password...", target_signup_email)
            await fill_element(qwen_page, 'input#confirmPwd', mailbox_password, slow_mode=False)
            
            # 6. Klik Sign Up (Step 1 of 2)
            await status_callback("Mengeklik tombol Sign Up (Step 1 of 2)...", target_signup_email)
            await click_element(qwen_page, 'button:has-text("Sign Up"), span:has-text("Sign Up (Step 1 of 2)"), span:has-text("Daftar (Langkah 1 dari 2)")', slow_mode=False)
            await qwen_page.wait_for_timeout(800) # Istirahat 800ms
            await solve_slider_captcha(qwen_page, status_callback, target_signup_email)
            
            # 7. Klik tab Email di Step 2 of 2
            await status_callback("Beralih ke verifikasi Email...", target_signup_email)
            await qwen_page.bring_to_front()
            
            # Robust selector to find the email tab (often represented by the envelope SVG or specific class)
            email_tab_selector = 'div.next-tabs-tab-inner:has(svg.Icons__Mobile), div.next-tabs-tab-inner:has(path[d^="M15.3,0"]), div.next-tabs-tab-inner:has(svg)'
            await click_element(qwen_page, email_tab_selector, slow_mode=False)
            await qwen_page.wait_for_timeout(800) # Istirahat 800ms
            
            # 8. Klik Send
            await status_callback("Mengirim kode OTP...", target_signup_email)
            await qwen_page.bring_to_front()
            await click_element(qwen_page, 'span:text-is("Send")', slow_mode=False)
            await qwen_page.wait_for_timeout(800) # Istirahat 800ms
            await solve_slider_captcha(qwen_page, status_callback, target_signup_email)
            
            # --- MEMANTAU OTP DI TAB 1 (GOMAIL) ---
            await status_callback("Memantau kotak masuk untuk email OTP...", target_signup_email)
            await mail_page.bring_to_front()
            otp_code = None
            start_time = time.time()
            timeout_limit = 90
            
            while time.time() - start_time < timeout_limit:
                # 1. Cek semua frame saat ini (jika email sudah terbuka)
                for frame in mail_page.frames:
                    try:
                        # Coba temukan OTP dari div bergaya khusus di frame ini
                        otp_div = await frame.query_selector('div[style*="Courier New"], div[style*="letter-spacing"]')
                        if otp_div:
                            otp_text = await otp_div.inner_text()
                            otp_clean = "".join(otp_text.split())  # Hapus spasi antar digit jika ada
                            if re.match(r"^\d{6}$", otp_clean):
                                otp_code = otp_clean
                                await status_callback(f"Kode OTP {otp_code} terdeteksi di iframe!", target_signup_email)
                                break
                        
                        # Fallback jika ada OTP 6 digit langsung di teks halaman (misal ada di snippet pratinjau list)
                        frame_text = await frame.inner_text("body")
                        if "Alibaba" in frame_text or "Verification" in frame_text or "Code" in frame_text:
                            otp_match = re.search(r"\b\d{6}\b", frame_text)
                            if otp_match:
                                otp_code = otp_match.group(0)
                                await status_callback(f"Kode OTP {otp_code} terdeteksi di teks body!", target_signup_email)
                                break
                    except Exception:
                        pass
                
                if otp_code:
                    break
                
                # 2. Cari tombol email list item dan klik jika unread email muncul
                email_button = await mail_page.query_selector('button:has-text("Qwen Cloud"), button:has-text("Verification"), button:has-text("Alibaba")')
                if email_button:
                    await status_callback("Email OTP masuk! Membuka email...", target_signup_email)
                    await click_element(mail_page, 'button:has-text("Qwen Cloud"), button:has-text("Verification"), button:has-text("Alibaba")', slow_mode=False)
                    # Beri waktu jeda agar iframe konten email dimuat sepenuhnya
                    await mail_page.wait_for_timeout(100)
                    
                    # Cek semua frame lagi setelah klik
                    for frame in mail_page.frames:
                        try:
                            # Coba temukan dari div bergaya khusus di halaman email terbuka
                            otp_div_opened = await frame.query_selector('div[style*="Courier New"], div[style*="letter-spacing"]')
                            if otp_div_opened:
                                otp_text = await otp_div_opened.inner_text()
                                otp_clean = "".join(otp_text.split())
                                if re.match(r"^\d{6}$", otp_clean):
                                    otp_code = otp_clean
                                    await status_callback(f"Kode OTP {otp_code} disalin dari email!", target_signup_email)
                                    break
                            
                            frame_text = await frame.inner_text("body")
                            if "Alibaba" in frame_text or "Verification" in frame_text or "Code" in frame_text:
                                otp_match = re.search(r"\b\d{6}\b", frame_text)
                                if otp_match:
                                    otp_code = otp_match.group(0)
                                    await status_callback(f"Kode OTP {otp_code} disalin (fallback)!", target_signup_email)
                                    break
                        except Exception:
                            pass
                    
                    if otp_code:
                        break
                
                await asyncio.sleep(0.5)
            
            # Tutup Tab GoMail setelah OTP ditemukan
            try:
                await mail_page.close()
            except Exception:
                pass
                
            # 9. Masukkan OTP
            await qwen_page.bring_to_front()
            await status_callback("Memasukkan OTP ke form Alibaba Cloud...", target_signup_email)
            await fill_element(qwen_page, 'input#emailCaptcha', otp_code, slow_mode=False)
            
            # 10. Centang checkbox
            await status_callback("Centang persetujuan ketentuan...", target_signup_email)
            await check_element(qwen_page, 'input#policy0', slow_mode=False)
            
            # 11. Klik Sign Up (Step 2 of 2)
            await status_callback("Mengeklik tombol Sign Up (Step 2 of 2)...", target_signup_email)
            await click_element(qwen_page, 'button.verify__submit, button:has-text("Sign Up (Step 2 of 2)"), button.next-btn-primary:has-text("Sign Up")', slow_mode=False)
            
            # 12. Tunggu proses registrasi selesai
            await status_callback("Menunggu proses registrasi Alibaba Cloud selesai...", target_signup_email)
            await qwen_page.wait_for_timeout(2000) # Istirahat 2 detik agar pembuatan akun selesai penuh di server
            
            # ========================================================
            # --- TAHAP 3: DAFTAR DI QWEN CLOUD ---
            # ========================================================
            await status_callback("Membuka Tab 3 (Qwen Cloud)...", target_signup_email)
            qwen_cloud_page = await context.new_page()
            
            await status_callback("Membuka halaman pendaftaran Qwen Cloud...", target_signup_email)
            await qwen_cloud_page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            await qwen_cloud_page.wait_for_timeout(800) # Istirahat 800ms
            await solve_slider_captcha(qwen_cloud_page, status_callback, target_signup_email)
            
            # Cek jika muncul popup tombol "Refresh"
            refresh_btn_selector = 'button:has-text("Refresh")'
            try:
                await qwen_cloud_page.wait_for_selector(refresh_btn_selector, timeout=5000)
                await qwen_cloud_page.click(refresh_btn_selector)
                await status_callback("Popup terdeteksi, mengeklik Refresh...", target_signup_email)
                await qwen_cloud_page.wait_for_timeout(500)
                await solve_slider_captcha(qwen_cloud_page, status_callback, target_signup_email)
            except Exception:
                pass
            
            # Klik tombol "Continue" setelah refresh / saat halaman pertama muncul
            continue_btn_selector = 'button:has-text("Continue")'
            try:
                # Selesaikan captcha jika muncul saat halaman pertama qwen loading
                await solve_slider_captcha(qwen_cloud_page, status_callback, target_signup_email)
                
                # Klik Continue Pertama secara aman
                await status_callback("Mengeklik tombol Continue pertama...", target_signup_email)
                await click_element(qwen_cloud_page, continue_btn_selector, timeout_ms=15000, slow_mode=False)
                await qwen_cloud_page.wait_for_timeout(800) # Istirahat 800ms
                
                # Selesaikan captcha jika dipicu setelah klik Continue pertama
                await solve_slider_captcha(qwen_cloud_page, status_callback, target_signup_email)
                
                # Centang checkbox persetujuan
                terms_checkbox_selector = 'input.maas-terms-text__checkbox, input[type="checkbox"]'
                await status_callback("Mencentang checkbox persetujuan...", target_signup_email)
                await check_element(qwen_cloud_page, terms_checkbox_selector, timeout_ms=10000, slow_mode=False)
                await qwen_cloud_page.wait_for_timeout(800) # Istirahat 800ms
                
                # Klik button Continue Kedua secara aman
                await status_callback("Mengeklik tombol Continue kedua...", target_signup_email)
                await click_element(qwen_cloud_page, continue_btn_selector, timeout_ms=10000, slow_mode=False)
                await qwen_cloud_page.wait_for_timeout(1000) # Istirahat 1 detik
            except Exception as e:
                debug_log(f"Alur Continue / Persetujuan Qwen Cloud error: {e}")
                # Fallback langsung klik secara mentah tanpa human mouse jika fungsi pembantu gagal
                try:
                    await qwen_cloud_page.click(continue_btn_selector, timeout=5000)
                    await qwen_cloud_page.click('input.maas-terms-text__checkbox', timeout=5000)
                    await qwen_cloud_page.click(continue_btn_selector, timeout=5000)
                except Exception:
                    pass
            

            # --- KLIK API KEYS ---
            await status_callback("Mengeklik menu API Keys...", target_signup_email)
            api_keys_selector = 'span:has-text("API Keys"), span.min-w-0:has-text("API Keys"), span[data-spm-anchor-id="qwencloud.45753575.0.i15.1ee15b90j2Rcn2"]'
            new_page = await click_and_get_page(context, qwen_cloud_page, api_keys_selector, timeout_ms=25000)
            await new_page.wait_for_timeout(800)
            
            # --- TANGANI POPUP & AKTIVASI LAYANAN / KUOTA ---
            await handle_first_use_popups(new_page, status_callback, target_signup_email)
            
            # --- KLIK 'CREATE API KEY' DI TAB BARU ---
            create_api_key_btn = 'button:has-text("Create API key")'
            await new_page.wait_for_selector(create_api_key_btn, timeout=2000)
            await new_page.click(create_api_key_btn)
            
            # --- TAHAP PENGISIAN NAMA API KEY DI POPUP ---
            api_key_name_input = 'input[placeholder="e.g., Production API key for main application"]'
            await new_page.wait_for_selector(api_key_name_input, timeout=2000)
            
            key_number = random.randint(1000, 9999)
            target_key_name = f"test{key_number}"
            
            await new_page.fill(api_key_name_input, target_key_name)
            
            # --- KLIK 'GENERATE KEY' UNTUK MENYELESAIKAN ---
            generate_key_btn = 'button:has-text("Generate Key")'
            await new_page.wait_for_selector(generate_key_btn, timeout=2000)
            await new_page.click(generate_key_btn)
            await status_callback("Menghasilkan API Key baru di popup...", target_signup_email)
            
            # --- TAHAP MENYALIN API KEY ---
            api_key_input_selector = 'input[data-slot="input-group-control"]'
            await new_page.wait_for_selector(api_key_input_selector, timeout=2000)
            
            await status_callback("Menunggu API Key selesai dibuat...", target_signup_email)
            api_key = ""
            for _ in range(30):
                api_key_inputs = await new_page.query_selector_all(api_key_input_selector)
                for inp in api_key_inputs:
                    val = await inp.input_value()
                    if val and val.startswith("sk-"):
                        api_key = val
                        break
                    
                    val_attr = await inp.get_attribute("value")
                    if val_attr and val_attr.startswith("sk-"):
                        api_key = val_attr
                        break
                
                if api_key:
                    break
                await asyncio.sleep(0.5)
            
            await status_callback(f"Kunci API tersalin: {api_key[:10]}...", target_signup_email)
            
            # --- UJI KUNCI API SECARA INSTAN ---
            await status_callback("Menguji validitas API Key...", target_signup_email)
            test_res = await asyncio.get_event_loop().run_in_executor(None, test_key, target_signup_email, api_key)
            
            # Jika DENIED, cek apakah akun belum eligible di halaman benefits
            if test_res.get("status") == "DENIED":
                try:
                    await status_callback("API Key DENIED. Memeriksa status eligibilitas...", target_signup_email)
                    await new_page.goto("https://home.qwencloud.com/benefits", timeout=20000)
                    await new_page.wait_for_timeout(1000)
                    
                    page_content = await new_page.content()
                    is_eligible = False
                    try:
                        el = await new_page.query_selector('text="Eligible models"')
                        if el and await el.is_visible():
                            is_eligible = True
                    except Exception:
                        pass
                    
                    if not is_eligible and "eligible models" in page_content.lower():
                        is_eligible = True
                        
                    if not is_eligible:
                        await status_callback("Akun tidak eligible untuk free tier.", target_signup_email)
                        test_res["status"] = "UNELIGIBLE"
                        test_res["error_msg"] = "Not eligible for free tier benefits yet"
                    else:
                        await status_callback("Akun eligible, namun API Key tetap DENIED.", target_signup_email)
                except Exception as e:
                    debug_log(f"Gagal memeriksa halaman benefits: {e}")
            
            # --- SIMPAN HASIL KE FILE TEXT SESUAI STATUS ---
            status_str = test_res.get("status", "UNKNOWN")
            if status_str == "OK":
                save_file_path = "Valid.txt"
            elif status_str == "UNELIGIBLE":
                save_file_path = "Uneligible.txt"
            else:
                save_file_path = "Dead.txt"
                
            try:
                with open(save_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{target_signup_email}|{api_key}\n")
                await status_callback(f"Data akun tersimpan ke {save_file_path}.", target_signup_email)
            except Exception as e:
                debug_log(f"Gagal menyimpan ke {save_file_path}: {e}")
                await status_callback(f"Gagal menyimpan ke {save_file_path}.", target_signup_email)
            
            # --- KLIK 'CLOSE' DI POPUP API KEY ---
            try:
                close_btn = 'button:has-text("Close")'
                await new_page.wait_for_selector(close_btn, timeout=5000)
                await new_page.click(close_btn)
            except Exception:
                pass
            
            # --- TAHAP LOGOUT / SIGN OUT ---
            sign_out_selector = 'a:has-text("Sign out")'
            try:
                await new_page.wait_for_selector(sign_out_selector, timeout=10000)
                await new_page.click(sign_out_selector, force=True)
            except Exception:
                sign_out_url = "https://account.qwencloud.com/sso/signout?returnUrl=https://www.qwencloud.com/"
                await new_page.goto(sign_out_url, timeout=30000)
            
            await status_callback("Selesai keluar dari sesi.", target_signup_email)
            await new_page.wait_for_timeout(500)
            return {"email": target_signup_email, "api_key": api_key, "test_res": test_res}
        except Exception as e:
            raise Exception(f"Gagal saat navigasi otomatisasi: {e}")
        finally:
            await status_callback("Menutup browser...")
            await browser.close()
 
async def worker(account_index, password, semaphore, slot_queue, state: DashboardState, headless=True):
    async with semaphore:
        slot_id = await slot_queue.get()
        
        async def status_callback(status, email=""):
            state.update_worker(slot_id, status, email)
            
        # Beri jeda acak 1-3 detik untuk mencegah peluncuran browser bersamaan (meringankan CPU/RAM)
        delay = random.uniform(1, 3)
        state.update_worker(slot_id, f"Menunggu jeda antrean ({delay:.1f}s)...", "")
        await asyncio.sleep(delay)
        
        state.update_worker(slot_id, f"Memulai pendaftaran akun #{account_index}...", "")
        
        try:
            # Otomatisasi Playwright berjalan di background/foreground sesuai parameter
            res = await run_automation(password, status_callback, headless=headless)
            email = res["email"]
            api_key = res["api_key"]
            test_res = res.get("test_res") or {}
            status_str = test_res.get("status", "UNKNOWN")
            latency = test_res.get("chat_ms", 0) or 0
            
            # Update state selesai sukses
            state.finish_worker(slot_id, success=True, email=email, api_key=api_key, latency=latency, test_status=status_str)
        except Exception as e:
            # Update state selesai gagal
            state.finish_worker(slot_id, success=False, email=f"Akun #{account_index}", error_msg=str(e))
        finally:
            await slot_queue.put(slot_id)

def print_final_summary(results):
    total = len(results)
    if total == 0:
        return
    
    valid_tests = [r for r in results if r.get("success") and "test_status" in r]
    ok = sum(1 for r in valid_tests if r.get('test_status') == 'OK')
    denied = sum(1 for r in valid_tests if r.get('test_status') == 'DENIED')
    uneligible = sum(1 for r in valid_tests if r.get('test_status') == 'UNELIGIBLE')
    dead = sum(1 for r in valid_tests if r.get('test_status') == 'DEAD')
    failed_runs = sum(1 for r in results if not r.get("success"))
    
    print("\n\033[96m" + "=" * 65 + "\033[0m")
    print("\033[92m\033[1m📊 SUMMARY HASIL PENGUJIAN API KEY:\033[0m")
    print("\033[96m" + "=" * 65 + "\033[0m")
    print(f"Total Registrasi Diproses : {total}")
    print(f"✔ API Key OK / Aktif      : \033[92m{ok}\033[0m")
    print(f"✖ API Key DENIED          : \033[91m{denied}\033[0m")
    print(f"⚠ API Key UNELIGIBLE      : \033[93m{uneligible}\033[0m")
    print(f"💀 API Key DEAD/EXPIRED    : \033[90m{dead}\033[0m")
    print(f"✗ Gagal Registrasi Bot    : \033[91m{failed_runs}\033[0m")
    
    try:
        # Logging hasil ke qwen-test-results.txt dinonaktifkan atas permintaan user
        pass
    except Exception as e:
        pass

def load_env(path=".env"):
    """Membaca file .env dan mengembalikan dict konfigurasi."""
    config = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return config

async def run_once(cfg):
    """Menjalankan satu siklus pendaftaran berdasarkan konfigurasi."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8')
            except Exception:
                pass

    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[96m" + "=" * 65 + "\033[0m")
    print("\033[92m\033[1m     QWEN CLOUD CONCURRENT BATCH ACCOUNT GENERATOR & TESTER      \033[0m")
    print("\033[96m" + "=" * 65 + "\033[0m\n")

    # Baca konfigurasi dari .env
    user_password   = cfg.get("PASSWORD", "")
    num_accounts    = int(cfg.get("ACCOUNTS_PER_RUN", "2"))
    headless        = cfg.get("HEADLESS", "true").lower() not in ("false", "no", "0")
    max_concurrency = max(1, int(cfg.get("CONCURRENCY", "2")))
    cooldown_batch  = int(cfg.get("COOLDOWN_BETWEEN_BATCHES", "60"))

    # Validasi password
    if not user_password or len(user_password) < 8 or len(user_password) > 20:
        print("\033[91m[ERROR] PASSWORD di .env tidak valid (harus 8-20 karakter)!\033[0m")
        return

    print(f"\033[96m📋 Konfigurasi dari .env:\033[0m")
    print(f"   Password       : {'*' * len(user_password)}")
    print(f"   Akun per run   : {num_accounts}")
    print(f"   Headless       : {'Ya' if headless else 'Tidak'}")
    print(f"   Concurrency    : {max_concurrency}")
    print(f"   Cooldown batch : {cooldown_batch}s")
    print()

    num_slots = max(max_concurrency, 4)
    state     = DashboardState(num_accounts, num_slots=num_slots)
    semaphore = asyncio.Semaphore(max_concurrency)

    slot_queue = asyncio.Queue()
    for s in range(1, num_slots + 1):
        await slot_queue.put(s)

    # Proses akun dalam kelompok 2, dengan jeda antar batch
    BATCH_SIZE = 2
    account_indices = list(range(1, num_accounts + 1))
    batches = [account_indices[i:i+BATCH_SIZE] for i in range(0, len(account_indices), BATCH_SIZE)]

    with Live(generate_layout(state), refresh_per_second=2, auto_refresh=False) as live:
        async def update_dashboard():
            while state.completed_count < num_accounts:
                live.update(generate_layout(state), refresh=True)
                await asyncio.sleep(0.5)
            live.update(generate_layout(state), refresh=True)

        dashboard_task = asyncio.ensure_future(update_dashboard())

        for batch_num, batch in enumerate(batches):
            batch_tasks = [worker(i, user_password, semaphore, slot_queue, state, headless) for i in batch]
            await asyncio.gather(*batch_tasks)

            if batch_num < len(batches) - 1:
                for remaining in range(cooldown_batch, 0, -1):
                    live.update(generate_layout(state), refresh=True)
                    print(f"\r\033[93m⏳ Cooldown sebelum batch berikutnya: {remaining}s ...\033[0m", end="", flush=True)
                    await asyncio.sleep(1)
                print(f"\r\033[92m✔ Cooldown selesai! Melanjutkan batch berikutnya...          \033[0m")

        await dashboard_task

    print("\n\033[92m[✓] Semua pendaftaran dan pengujian selesai diproses!\033[0m")
    print_final_summary(state.results)


async def main():
    try:
        # Hapus file error.log dan qwen-test-results.txt pada startup jika ada
        for filepath in ["error.log", "qwen-test-results.txt"]:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

        cfg          = load_env()
        restart_delay = int(cfg.get("RESTART_DELAY", "60"))
        max_restarts  = int(cfg.get("MAX_RESTARTS", "0"))  # 0 = tidak terbatas

        run_count = 0
        while True:
            await run_once(cfg)
            run_count += 1

            # Cek apakah sudah mencapai batas restart
            if max_restarts > 0 and run_count >= max_restarts:
                print(f"\n\033[92m[✓] Batas {max_restarts} run tercapai. Bot berhenti.\033[0m")
                break

            if restart_delay <= 0:
                print(f"\n\033[92m[✓] Auto-restart dinonaktifkan (RESTART_DELAY=0). Bot berhenti.\033[0m")
                break

            # Countdown sebelum restart
            print(f"\n\033[96m🔄 Run ke-{run_count} selesai. Restart otomatis dalam {restart_delay} detik...\033[0m")
            for remaining in range(restart_delay, 0, -1):
                print(f"\r\033[93m⏳ Restart dalam: {remaining}s ...\033[0m", end="", flush=True)
                await asyncio.sleep(1)
            print(f"\r\033[92m🚀 Memulai run ke-{run_count + 1}...                              \033[0m\n")

    except KeyboardInterrupt:
        print("\n\033[91m[-] Proses dibatalkan oleh pengguna (KeyboardInterrupt).\033[0m")

if __name__ == "__main__":
    asyncio.run(main())
