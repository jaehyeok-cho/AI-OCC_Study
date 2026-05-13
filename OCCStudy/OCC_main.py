from __future__ import annotations

try:
    from perforated_tray.app import main
except Exception as exc:
    print("pythonOCC/PyQt 초기화 실패:", exc)
    print("setting.bat으로 AI-OCC_Study 환경을 만든 뒤 다시 실행해 주세요.")
    raise


if __name__ == "__main__":
    main()
