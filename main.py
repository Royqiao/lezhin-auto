import os
import time
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

# ================= 读取环境配置 =================
LEZHIN_USER = os.environ.get("LEZHIN_USER")
LEZHIN_PASS = os.environ.get("LEZHIN_PASS")

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
SENDER_PASS = os.environ.get("SENDER_PASS", "").strip()
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "").strip()

# ================= 邮件发送工具函数 =================
def send_email(subject, body, image_path=None):
    if not all([SENDER_EMAIL, SENDER_PASS, RECEIVER_EMAIL]):
        print("⚠️ 邮件配置不完整，跳过发送。")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read(), name=os.path.basename(image_path))
                msg.attach(img)
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        print(f"✅ 邮件发送成功：{subject}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")
        return False

# ================= Lezhin 签到任务 =================
def task_lezhin(page):
    print("\n========== 🚀 [Lezhin] 开始执行 ==========")
    if not all([LEZHIN_USER, LEZHIN_PASS]):
        print("⚠️ [Lezhin] 未配置账号密码，跳过执行。")
        return

    try:
        # 1. 打开登录页
        print("[Lezhin] 正在打开登录页面...")
        page.goto("https://www.lezhin.com/ko/login?redirect=%2Fko", timeout=60000)
        page.wait_for_timeout(3000)

        # 2. 输入账号密码
        print("[Lezhin] 正在输入邮箱和密码...")
        try:
            page.fill('input#email', LEZHIN_USER, timeout=10000)
            page.wait_for_timeout(500)
            page.fill('input#password', LEZHIN_PASS, timeout=10000)
        except Exception as e:
            print(f"❌ [Lezhin] 找不到输入框: {e}")
            return

        # 3. 点击登录按钮
        print("[Lezhin] 点击登录按钮...")
        try:
            page.locator('div.login_btn__808sI button, button.login_btn__808sI').first.click(timeout=10000)
        except Exception:
            page.press('input#password', 'Enter')

        page.wait_for_timeout(8000)

        if "login" in page.url:
            print("❌ [Lezhin] 登录失败（仍停留在登录页）。")
            return

        print("✅ [Lezhin] 登录成功！")
        page.wait_for_timeout(5000) 
        
        # ==========================================
        # 4. 尝试通过点击进入签到页
        # ==========================================
        print("[Lezhin] 尝试通过点击进入签到页...")
        click_success = False
        
        try:
            menu_btn = page.locator(
                'button:has(span.a11y:text-is("메뉴")), '
                'button[aria-label="메뉴"], '
                'header button:has(svg)'
            ).first
            
            if menu_btn.is_visible(timeout=3000):
                menu_btn.click(timeout=5000, force=True)
                print("[Lezhin] 菜单已展开...")
                page.wait_for_timeout(2000)
                
                attendance_link = page.locator('a[href*="/arcade/attendance"], a:has-text("출석하기")').first
                if attendance_link.is_visible(timeout=3000):
                    attendance_link.click(timeout=5000, force=True)
                    print("[Lezhin] 成功通过点击进入签到页面！")
                    click_success = True
                    page.wait_for_timeout(5000)
        except Exception as e:
            print(f"⚠️ [Lezhin] 点击查找失败: {e}")

        if not click_success:
            print("[Lezhin] 启用兜底方案，直接访问签到页链接...")
            page.goto("https://www.lezhin.com/ko/arcade/attendance", timeout=60000)
            page.wait_for_timeout(5000)

        # ==========================================
        # 5. 精准判断签到状态并执行 (加强重试逻辑)
        # ==========================================
        print("[Lezhin] 已进入签到页面，正在检查今日签到状态...")
        
        check_btn = None
        # 最多重试 5 次，每次等 3 秒，给足页面渲染时间
        for attempt in range(5):
            try:
                # 放弃死板的 class，改为文本与 class 双重结合匹配
                btn_locator = page.locator('button:has-text("출석하기"), button:has-text("오늘 출석 완료"), button[class*="attendance_ctaButton"]').first
                
                if btn_locator.is_visible(timeout=3000):
                    check_btn = btn_locator
                    break
                else:
                    print(f"⏳ 签到按钮还没加载出来，等待 3 秒后重试 ({attempt+1}/5)...")
                    page.wait_for_timeout(3000)
            except Exception:
                page.wait_for_timeout(3000)

        if check_btn:
            btn_text = check_btn.inner_text().strip()
            print(f"[Lezhin] 识别到签到大按钮文本: '{btn_text}'")
            
            if "오늘 출석 완료" in btn_text or "완료" in btn_text:
                print("ℹ️ [Lezhin] 页面显示今日已签到，无需重复点击，直接结束任务。")
                return
            
            elif "출석하기" in btn_text:
                print("✅ [Lezhin] 检测到未签到，正在执行点击...")
                page.wait_for_timeout(1000) 
                check_btn.click(timeout=10000)
                page.wait_for_timeout(3000) 
                
                print("🎉 [Lezhin] 签到成功！")
                page.screenshot(path="lezhin_success.png", full_page=True)
                send_email("[Lezhin] 每日签到成功", "今天的 Lezhin 签到已完成，详情见附图。", "lezhin_success.png")
                return
            else:
                print(f"⚠️ [Lezhin] 遇到未知按钮文本: '{btn_text}'，尝试强制点击...")
                check_btn.click(timeout=10000, force=True)
                page.wait_for_timeout(3000)
                page.screenshot(path="lezhin_unknown.png", full_page=True)
                send_email("[Lezhin] 签到异常", f"未知按钮状态（文本：{btn_text}），已强制点击，请查看附图。", "lezhin_unknown.png")
                return
        else:
            # 如果重试了5次还找不到，截图并发邮件报警
            print("❌ [Lezhin] 重试多次依然未能找到最终的签到按钮。保存截图...")
            page.screenshot(path="lezhin_btn_not_found.png", full_page=True)
            send_email("[Lezhin] 签到失败：找不到按钮", "页面已跳转到签到页，但未能找到签到按钮，请查看附图确认页面状态。", "lezhin_btn_not_found.png")

    except Exception as e:
        print(f"❌ [Lezhin] 执行异常: {e}")
        page.screenshot(path="lezhin_error.png")

# ================= 主程序入口 =================
def main():
    # 随机延迟 1~3 分钟，避开整点检测和风控
    delay = random.randint(60, 180)
    print(f"⏳ 为了避免风控，脚本将随机延迟 {delay} 秒后启动...")
    time.sleep(delay)

    with sync_playwright() as p:
        print("🚀 启动浏览器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        
        page_lezhin = context.new_page()
        task_lezhin(page_lezhin)
        page_lezhin.close()

        browser.close()
        print("\n✅ Lezhin 任务执行完毕。")

if __name__ == "__main__":
    main()
