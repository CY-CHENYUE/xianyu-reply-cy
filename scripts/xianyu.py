#!/usr/bin/env python3
"""xianyu-reply: Goofish (Xianyu) IM automation CLI.

Usage:
    python3 xianyu.py <command> [options]

Commands:
    login       Check login status
    list-chats  List conversations with unread indicators
    read-chat   Read messages from a conversation
    send        Send a message in the current conversation
    snapshot    Get text snapshot of current page
    screenshot  Take a screenshot
    kill        Close the browser
"""

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _get_page(headless=False):
    """Connect to existing browser or launch a new one, return page."""
    from core.browser import ensure_browser
    return ensure_browser(headless=headless)


def cmd_login(args):
    page = _get_page(headless=args.headless)
    from actions.chat import navigate_to_im, check_login
    nav = navigate_to_im(page)
    if not nav["success"]:
        _print_json(nav)
        return
    _print_json(check_login(page))


def cmd_wait_login(args):
    page = _get_page(headless=args.headless)
    from actions.chat import navigate_to_im, wait_for_login
    nav = navigate_to_im(page)
    if not nav["success"]:
        _print_json(nav)
        return
    _print_json(wait_for_login(page, timeout=args.timeout))


def cmd_list_chats(args):
    page = _get_page(headless=args.headless)
    from actions.chat import navigate_to_im, list_chats
    nav = navigate_to_im(page)
    if not nav["success"]:
        _print_json(nav)
        return
    _print_json(list_chats(page))


def cmd_read_chat(args):
    page = _get_page(headless=args.headless)
    from actions.chat import navigate_to_im, read_chat
    nav = navigate_to_im(page)
    if not nav["success"]:
        _print_json(nav)
        return
    _print_json(read_chat(page, index=args.index))


def cmd_send(args):
    page = _get_page(headless=args.headless)
    from actions.chat import navigate_to_im, read_chat, send_message

    # Navigate to IM first
    nav = navigate_to_im(page)
    if not nav["success"]:
        _print_json(nav)
        return

    # If --index is specified, open that chat first
    if args.send_index is not None:
        rc = read_chat(page, index=args.send_index)
        if not rc["success"]:
            _print_json({"success": False, "error": f"Could not open chat: {rc.get('error')}"})
            return

    _print_json(send_message(page, text=args.text))


def cmd_snapshot(args):
    page = _get_page(headless=args.headless)
    from actions.chat import navigate_to_im, snapshot
    nav = navigate_to_im(page)
    if not nav["success"]:
        _print_json(nav)
        return
    _print_json(snapshot(page))


def cmd_screenshot(args):
    page = _get_page(headless=args.headless)
    from actions.chat import screenshot
    _print_json(screenshot(page, path=args.output))


def cmd_kill(args):
    from core.browser import kill
    kill()
    _print_json({"success": True, "message": "Browser closed"})


def build_parser():
    parser = argparse.ArgumentParser(
        prog="xianyu",
        description="Goofish (Xianyu) IM automation CLI",
    )
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--debug", action="store_true", help="Debug output")
    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("login", help="Navigate to IM and check login status")

    p_wait = subs.add_parser("wait-login", help="Open browser and wait for user to login")
    p_wait.add_argument("--timeout", type=int, default=120, help="Max seconds to wait")

    subs.add_parser("list-chats", help="List conversations with unread indicators")

    p_read = subs.add_parser("read-chat", help="Read messages from a conversation")
    p_read.add_argument("--index", type=int, default=0, help="Chat index (from list-chats)")

    p_send = subs.add_parser("send", help="Send a message in the current chat")
    p_send.add_argument("--text", required=True, help="Message text to send")
    p_send.add_argument("--index", type=int, default=None, dest="send_index", help="Chat index to open before sending")

    subs.add_parser("snapshot", help="Get text snapshot of current page")

    p_ss = subs.add_parser("screenshot", help="Take a screenshot")
    p_ss.add_argument("--output", default=None, help="Output file path")

    subs.add_parser("kill", help="Close the browser")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # kill command doesn't need playwright
    if args.command != "kill":
        from core.browser import ensure_playwright
        ensure_playwright()

    try:
        {
            "login": cmd_login,
            "wait-login": cmd_wait_login,
            "list-chats": cmd_list_chats,
            "read-chat": cmd_read_chat,
            "send": cmd_send,
            "snapshot": cmd_snapshot,
            "screenshot": cmd_screenshot,
            "kill": cmd_kill,
        }[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as exc:
        _print_json({"success": False, "error": str(exc)})
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        from core.browser import disconnect
        disconnect()


if __name__ == "__main__":
    main()
