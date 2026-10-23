---
name: mobile-device-qa
description: 실기기(Android 폰, 원격 Mac에 USB로 연결된 iPhone)로 Unreal Engine 모바일 앱 QA를 자동으로 돌리는 방법. Windows 에이전트가 SSH로 원격 Mac에 붙어 iOS 빌드·설치·WebDriverAgent 터치·스크린샷·앱 로그/파일 접근을 하고, Android는 adb·원격 테스트랩으로 같은 일을 한다. "실기기로 QA 돌려", "iPhone에서 테스트", "안드로이드 기기 테스트", "QA 이슈 기기 확인 후 코멘트" 요청에 사용.
---

# 실기기 모바일 QA (iOS 원격 Mac + Android)

Windows에서 일하는 에이전트가 **사람 손 없이** 실기기에서 앱을 조작하고, 증거(스크린샷·로그·파일 크기)를 모아 이슈에 결과를 남기는 절차다. UE5 앱 기준으로 썼지만 대부분 일반 모바일 앱에도 그대로 쓴다.

- iOS: [references/ios-remote-mac.md](references/ios-remote-mac.md) — SSH, 원격 빌드, devicectl, WebDriverAgent, 포트 포워딩, AFC(앱 컨테이너), syslog
- Android: [references/android.md](references/android.md) — adb, 좌표 얻기, 콘솔 명령 브로드캐스트, 원격 테스트랩(Samsung RTL, Firebase Test Lab)
- 판정·보고: [references/reporting.md](references/reporting.md) — 무엇을 증거로 남기고 어떻게 코멘트하는지
- 도우미: [scripts/ios.py](scripts/ios.py)(WDA·AFC·로그), [scripts/android.sh](scripts/android.sh)(adb)

## 전체 흐름

1. **기기 확인** — iOS: `ssh <mac> xcrun devicectl list devices`, Android: `adb devices -l`. 모델·OS·여유 공간·SIM 유무(셀룰러/전화 시험 가능 여부)를 먼저 적어 둔다.
2. **빌드** — 시험용은 Development 빌드(로그·콘솔 명령·디버그 메뉴가 살아 있음). iOS는 원격 Mac에서, Android는 CI 아티팩트 APK.
3. **설치** — iOS `xcrun devicectl device install app`, Android `adb install -r`(같은 서명·같거나 높은 versionCode면 데이터 유지).
4. **조작 채널 열기** — iOS는 WebDriverAgent(WDA) 세션, Android는 `adb shell input`.
5. **시나리오 실행** — 한 단계마다 스크린샷 → 눈으로 확인 → 다음 단계. 좌표는 스크린샷에서 읽는다(UE는 화면 전체가 하나의 Surface라 접근성 트리가 비어 있다).
6. **증거 수집** — 앱 로그(파일), 시스템 로그(syslog/logcat), 앱 컨테이너 파일 목록·크기, 디스크 여유 공간 변화.
7. **판정 후 보고** — 이슈별 PASS / FAIL / 부분 확인 / 시험 불가(사유)를 구분해 코멘트.

## 꼭 지킬 것 (시간을 가장 많이 잡아먹은 함정)

- **원격 Mac의 고아 프로세스는 로컬 네트워크 권한을 잃는다.** ssh 세션이 끝난 뒤 남은 프로세스(nohup/tmux)는 LAN에 못 나간다(`No route to host`). 반면 `nc`는 애플 바이너리라 예외로 통과해서 "네트워크 되는데 왜 안 되지"가 된다. → LAN이 필요한 작업(VCS sync 등)은 **ssh 세션이 살아 있는 동안** 하고, 오래 걸리는 빌드만 분리 실행한다. usbmux(USB) 포워딩은 로컬이라 분리돼도 된다.
- **폰 암호 = WDA 시작 때마다 'Enable UI Automation' 입력 요구(64초 제한, 연장 불가).** 시험 동안 암호를 끄거나, 사람에게 그 순간 입력을 부탁한다. 자동 잠금은 '안 함'.
- **WDA 세션을 새로 만들면 앱이 재시작되고 실행 인자가 사라진다.** 실행 인자(서버 환경 cvar 등)는 세션 capabilities의 `arguments`로 넘긴다. 앱 실행 직후 세션 생성이 겹치면 UE 초기화 중 크래시가 날 수 있으니 `devicectl process launch` 후 ~12초 뒤 세션을 만든다.
- **영상 재생 중엔 앱이 idle이 안 돼 WDA가 멈춘다.** 세션 생성 시 `shouldWaitForQuiescence:false`, 세션 설정 `waitForIdleTimeout:0`, `animationCoolOffTimeout:0`.
- **원격 작업영역의 쓰기 가능한 낡은 파일은 VCS sync가 건너뛴다**(Perforce `Can't clobber writable file`). 빌드 로그에서 sync 결과를 꼭 보고, 내용이 have 리비전과 같으면(`p4 diff -se`가 비면) `sync -f`.
- **두 대 이상 연결 시 포트 충돌.** 기기마다 다른 로컬 포트로 WDA를 포워딩한다(예: 8100, 8200).
- **iOS 비행기 모드는 Wi-Fi를 끄지 않는다**(마지막 설정 기억). 오프라인 시험은 제어센터에서 Wi-Fi도 끈다. WDA는 USB 포워딩이면 오프라인에서도 살아 있다.
- **Android 기기 뒤로가기 키는 앱을 종료시킬 수 있다** → 앱 내부 뒤로가기 버튼을 탭.
- **Android adb 데몬이 재시작되면 출력이 유실된다** → 중요한 명령은 재시도. 원격 테스트랩 브리지가 떠 있을 땐 `adb kill-server` 금지.
- **Git Bash에서 adb 경로 인자**는 `MSYS_NO_PATHCONV=1`을 붙여야 `/sdcard/...`가 Windows 경로로 바뀌지 않는다.
- **Shipping 빌드는 화면 캡처가 막힐 수 있다**(FLAG_SECURE, iOS 녹화 차단). 화면 증거가 필요하면 Development 빌드.

## 판정 원칙

- 기대값이 이슈에 표로 없으면 **서버 API 원본 데이터에서 기대값을 계산**한다(재생 순서, 용량 합 등). 화면 숫자와 원본 바이트를 함께 적는다.
- "앱이 그렇게 보인다"와 "실제로 그렇다"를 분리한다. 예: 화면의 선택 멤버 표시와 실제 재생된 파일(로그의 Open 경로)이 다를 수 있다.
- 시험 불가 항목은 이유를 구체적으로(SIM 없음, 서버에 해당 데이터 없음, 기기 1대뿐 등) 쓰고 상태는 바꾸지 않는다.
- 시험 중 직접 만든 상태(파일 삭제 등)가 다음 시험에 영향을 주면 그 사실을 같이 적는다.
