"""Chat actions for Xianyu (Goofish) IM page."""

import time
import re


GOOFISH_IM_URL = "https://www.goofish.com/im"


def _dismiss_security_popup(page, timeout=3000):
    """Dismiss Xianyu security warning popups that block chat interaction.

    These popups appear when Xianyu flags a message as potential fraud.
    Returns True if a popup was dismissed, False otherwise.
    """
    dismissed = False
    # Common popup selectors: modal confirm/close buttons, "我知道了", "继续聊天", "知道了"
    popup_selectors = [
        # Ant Design modal buttons
        '.ant-modal .ant-btn-primary',
        '.ant-modal .ant-btn',
        '[class*="modal"] [class*="confirm"]',
        '[class*="modal"] [class*="close"]',
        '[class*="modal"] [class*="btn"]',
        # Dialog buttons
        '[class*="dialog"] button',
        '[class*="Dialog"] button',
        # Generic close/dismiss
        '[class*="popup"] button',
        '[class*="toast"] [class*="close"]',
        # Overlay dismiss
        '[class*="overlay"] button',
        '[class*="mask"] button',
    ]

    # Also try to find buttons by text content
    try:
        for text in ["我知道了", "知道了", "继续聊天", "确定", "关闭", "我已知晓", "确认"]:
            btn = page.locator(f'button:has-text("{text}"), a:has-text("{text}"), [role="button"]:has-text("{text}")')
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                time.sleep(1)
                dismissed = True
                break
    except Exception:
        pass

    if not dismissed:
        for sel in popup_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(1)
                    dismissed = True
                    break
            except Exception:
                continue

    # Also try pressing Escape as a fallback
    if not dismissed:
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

    return dismissed


def navigate_to_im(page):
    """Navigate to Goofish IM page. Returns status dict."""
    try:
        page.goto(GOOFISH_IM_URL, wait_until="networkidle", timeout=45000)
    except Exception as e:
        try:
            page.goto(GOOFISH_IM_URL, wait_until="networkidle", timeout=45000)
        except Exception as e2:
            return {"success": False, "error": f"navigation_failed: {e2}"}

    time.sleep(8)  # Wait for SPA full render

    try:
        url = page.url
        title = page.title()
    except Exception:
        return {"success": False, "error": "page_context_lost_after_navigation"}

    if "login" in url or "qrcode" in url:
        return {"success": False, "error": "login_required", "url": url}

    return {"success": True, "url": url, "title": title}


def check_login(page):
    """Check if currently logged in by looking for login indicators."""
    try:
        url = page.url
    except Exception:
        return {"logged_in": False, "reason": "page_context_lost"}

    if "login" in url or "qrcode" in url:
        return {"logged_in": False, "reason": "on_login_page"}

    try:
        # Check for login modal overlay (Goofish uses ant-modal for login)
        login_modal = page.query_selector('.ant-modal')
        if login_modal and login_modal.is_visible():
            return {"logged_in": False, "reason": "login_modal_visible"}
    except Exception:
        pass  # Element may be stale after navigation

    try:
        # Check for login-related iframes
        for frame in page.frames:
            if "mini_login" in frame.url or "passport" in frame.url:
                return {"logged_in": False, "reason": "login_iframe_detected"}
    except Exception:
        pass

    try:
        # Check page text for login prompts
        body_text = page.evaluate("() => document.body.innerText")
        if "请输入手机号" in body_text or "扫码登录" in body_text or "短信登录" in body_text:
            return {"logged_in": False, "reason": "login_prompt_found"}
    except Exception:
        pass

    return {"logged_in": True, "url": url}


def wait_for_login(page, timeout=120):
    """Wait for user to complete login (scan QR code etc).

    Polls every 3 seconds until login is detected or timeout.
    Returns login status dict.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            status = check_login(page)
            if status["logged_in"]:
                return {"logged_in": True, "message": "Login successful"}
        except Exception:
            # Navigation after login destroys execution context - this means login succeeded
            time.sleep(3)
            try:
                # Re-check after page settles
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                return {"logged_in": True, "message": "Login successful (page navigated)"}
            except Exception:
                pass
        time.sleep(3)
    return {"logged_in": False, "reason": "timeout", "message": f"Login not detected after {timeout}s"}


def list_chats(page):
    """List chat conversations with unread indicators.

    Returns list of chats with index, name, last message, and unread status.
    Goofish IM uses CSS classes like conversation-item--XXXXX (with hash suffix).
    """
    chats = []

    # Goofish uses class names with hash suffixes: conversation-item--JReyg97P
    items = page.query_selector_all('[class*="conversation-item"]')

    if not items:
        # Fallback: get page text snapshot for Claude to parse
        text = _get_text_snapshot(page)
        return {
            "success": True,
            "chats": [],
            "count": 0,
            "raw_snapshot": text,
            "note": "Could not parse chat list. Check raw_snapshot.",
        }

    for i, item in enumerate(items):
        try:
            text = item.inner_text().strip()
        except Exception:
            continue

        # Detect unread indicators (badge, dot, unread class)
        has_unread = False
        try:
            badge = item.query_selector('[class*="badge"], [class*="unread"], [class*="dot"], [class*="count"]')
            if badge and badge.is_visible():
                has_unread = True
            # Also check if item has "unread" in its own class
            cls = item.get_attribute("class") or ""
            if "unread" in cls or "active" in cls:
                has_unread = True
        except Exception:
            pass

        # Extract name, last message, and time from text lines
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        name = lines[0] if lines else f"Chat {i}"
        last_msg = lines[1] if len(lines) > 1 else ""
        msg_time = lines[-1] if len(lines) > 2 else ""

        chats.append({
            "index": i,
            "name": name,
            "last_message": last_msg,
            "time": msg_time,
            "has_unread": has_unread,
        })

    return {"success": True, "chats": chats, "count": len(chats)}


def read_chat(page, index=0):
    """Click on a chat by index and read the messages.

    Returns the conversation messages.
    """
    items = page.query_selector_all('[class*="conversation-item"]')

    if not items or index >= len(items):
        return {"success": False, "error": f"Chat index {index} not found. Total: {len(items)}"}

    debug_info = {}

    try:
        items[index].click()
        time.sleep(3)  # Wait for chat to load
    except Exception as e:
        return {"success": False, "error": f"click_failed: {e}"}

    # Dismiss security popups if present
    popup_dismissed = _dismiss_security_popup(page)

    # Check if chat actually opened by looking for input area
    input_el = page.query_selector('[contenteditable="true"], textarea')
    chat_opened = input_el is not None

    if not chat_opened:
        # Maybe the security warning is inline, not a popup.
        # Try force-clicking on the name/avatar area of the conversation item
        items = page.query_selector_all('[class*="conversation-item"]')
        if items and index < len(items):
            try:
                # Try double-click
                items[index].dblclick()
                time.sleep(2)
                _dismiss_security_popup(page)
                input_el = page.query_selector('[contenteditable="true"], textarea')
                chat_opened = input_el is not None
            except Exception:
                pass

    if not chat_opened:
        # Try JavaScript click as fallback
        items = page.query_selector_all('[class*="conversation-item"]')
        if items and index < len(items):
            try:
                items[index].evaluate("el => el.click()")
                time.sleep(2)
                _dismiss_security_popup(page)
                input_el = page.query_selector('[contenteditable="true"], textarea')
                chat_opened = input_el is not None
            except Exception:
                pass

    # Collect debug info
    debug_info["chat_opened"] = chat_opened
    debug_info["popup_dismissed"] = popup_dismissed
    body_text = _get_text_snapshot(page)
    debug_info["has_input"] = input_el is not None
    if not chat_opened:
        debug_info["page_snapshot"] = body_text[:500]

    # Read messages from the chat panel
    messages = _extract_messages(page)
    return {"success": True, "messages": messages, "debug": debug_info}


def send_message(page, text):
    """Type and send a message in the currently open chat.

    Returns success status.
    """
    # Find input area
    input_selectors = [
        '[class*="chat-input"] textarea',
        '[class*="editor"] textarea',
        '[class*="message-input"] textarea',
        'textarea[class*="input"]',
        '[contenteditable="true"]',
        'textarea',
    ]

    input_el = None
    for sel in input_selectors:
        input_el = page.query_selector(sel)
        if input_el:
            break

    if not input_el:
        # Maybe a security popup is blocking - try to dismiss it
        _dismiss_security_popup(page)
        time.sleep(1)
        for sel in input_selectors:
            input_el = page.query_selector(sel)
            if input_el:
                break

    if not input_el:
        return {"success": False, "error": "input_not_found"}

    try:
        input_el.click()
        time.sleep(0.5)
        input_el.fill("")  # Clear first
        input_el.type(text, delay=80)
        time.sleep(0.5)

        # Try pressing Enter to send
        input_el.press("Enter")
        time.sleep(2)

        return {"success": True, "message_sent": text}
    except Exception as e:
        return {"success": False, "error": f"send_failed: {e}"}


def snapshot(page):
    """Get a text snapshot of the current page for Claude to analyze."""
    text = _get_text_snapshot(page)
    return {
        "success": True,
        "url": page.url,
        "title": page.title(),
        "snapshot": text,
    }


def screenshot(page, path=None):
    """Take a screenshot. Returns the file path."""
    if path is None:
        from pathlib import Path as P
        path = str(P.home() / ".xianyu-reply" / "screenshot.png")
    try:
        page.screenshot(path=path, full_page=False)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_text_snapshot(page):
    """Extract visible text from page."""
    try:
        # Get inner text of body
        text = page.evaluate("() => document.body.innerText")
        # Truncate if too long
        if len(text) > 5000:
            text = text[:5000] + "\n... (truncated)"
        return text
    except Exception:
        return page.title()


def _extract_messages(page):
    """Extract chat messages from the currently open conversation."""
    messages = []

    # Try various message selectors
    msg_selectors = [
        '[class*="message-item"]',
        '[class*="msg-bubble"]',
        '[class*="chat-msg"]',
        '[class*="message"] [class*="content"]',
    ]

    items = []
    for sel in msg_selectors:
        items = page.query_selector_all(sel)
        if items:
            break

    if items:
        for item in items[-20:]:  # Last 20 messages
            text = item.inner_text().strip()
            if text:
                messages.append(text)
    else:
        # Fallback: get full text snapshot of chat area
        snapshot = _get_text_snapshot(page)
        messages = [snapshot]

    return messages
