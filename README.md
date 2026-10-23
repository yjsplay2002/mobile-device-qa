# mobile-device-qa

코딩 에이전트(Claude Code 등)가 **실기기로 모바일 앱 QA를 자동으로 돌리는** 방법을 정리한 스킬.

- iOS: Windows 에이전트 → SSH → 원격 Mac → USB iPhone. 원격 빌드, `devicectl` 설치, WebDriverAgent 터치·스크린샷, USB 포트 포워딩, AFC로 앱 로그·파일 접근, syslog.
- Android: 로컬 adb, Samsung Remote Test Lab, Firebase Test Lab. 탭·스와이프, UE 콘솔 명령 브로드캐스트, logcat, 네트워크 토글.
- 판정과 이슈 보고 규칙.

Unreal Engine 모바일 앱 시험에서 나온 경험이지만 대부분 일반 앱에도 쓸 수 있다.

## 설치

```bash
git clone https://github.com/yjsplay2002/mobile-device-qa ~/.claude/skills/mobile-device-qa
```
진입점은 [SKILL.md](SKILL.md).

## 구성

```
SKILL.md                    흐름과 함정 요약
references/ios-remote-mac.md
references/android.md
references/reporting.md
scripts/ios.py              WDA·AFC·로그 도우미(환경변수로 기기 지정)
scripts/android.sh          adb 도우미
```

## License

MIT
