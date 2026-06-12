from pathlib import Path
import re
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_no_idle_wom.py <tracker-repo>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    kconfig = root / "Kconfig"
    esb = root / "src/connection/esb.c"

    text = kconfig.read_text(encoding="utf-8")
    if "config CONNECTION_TIMEOUT_USE_WOM" not in text:
        marker = "config CONNECTION_TIMEOUT_DELAY"
        start = text.index(marker)
        next_choice = text.index("\nchoice", start)
        block = """
config CONNECTION_TIMEOUT_USE_WOM
    bool "Use IMU wake up on connection timeout"
    default n
    depends on USER_SHUTDOWN && USE_IMU_WAKE_UP
    help
        Enter IMU wake up mode instead of system off when the receiver is not
        detected for the connection timeout duration.
"""
        text = text[:next_choice] + block + text[next_choice:]
        kconfig.write_text(text, encoding="utf-8")

    text = esb.read_text(encoding="utf-8")
    if "CONFIG_CONNECTION_TIMEOUT_USE_WOM" not in text:
        pattern = r"(\t+shutdown_requested = true;\n)(\t+)sys_request_system_off\(false\);"
        replacement = (
            r"\1#if CONFIG_CONNECTION_TIMEOUT_USE_WOM\n"
            r"\2sys_request_WOM(true, false);\n"
            r"#else\n"
            r"\2sys_request_system_off(false);\n"
            r"#endif"
        )
        text, count = re.subn(pattern, replacement, text, count=2)
        if count != 2:
            print(f"Expected to update 2 connection timeout shutdown calls, updated {count}", file=sys.stderr)
            print("Nearby shutdown calls:", file=sys.stderr)
            for match in re.finditer(r"sys_request_system_off\(false\);", text):
                start = max(0, match.start() - 160)
                end = min(len(text), match.end() + 80)
                print("---", file=sys.stderr)
                print(text[start:end], file=sys.stderr)
            return 1
        esb.write_text(text, encoding="utf-8")

    (root / "no_idle_wom.conf").write_text(
        """# Keep trackers active while connected. Enter WOM only when the receiver has
# been unavailable for the connection timeout duration.
CONFIG_USE_IMU_WAKE_UP=y
CONFIG_CONNECTION_TIMEOUT_USE_WOM=y
CONFIG_USE_ACTIVE_TIMEOUT=n
CONFIG_USE_IMU_TIMEOUT=n
CONFIG_SENSOR_USE_LOW_POWER_2=n
CONFIG_CONNECTION_TIMEOUT_DELAY=30000
""",
        encoding="utf-8",
    )

    checks = {
        "no_idle_wom.conf": (root / "no_idle_wom.conf").exists(),
        "Kconfig option": "CONNECTION_TIMEOUT_USE_WOM" in kconfig.read_text(encoding="utf-8"),
        "ESB WOM branch": "CONFIG_CONNECTION_TIMEOUT_USE_WOM" in esb.read_text(encoding="utf-8"),
    }
    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'missing'}")
    if not all(checks.values()):
        return 1

    print("no-idle-WOM changes are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
