# iOS: Windows → 원격 Mac → USB iPhone

iPhone은 Mac에 USB로 꽂혀 있고, 에이전트는 Windows에서 SSH로 Mac을 부린다. Windows에서 폰 Wi-Fi IP로 직접 붙는 건 사내망 분리로 안 되는 경우가 많아 **모든 경로를 Mac 경유로** 잡는다.

## 0. 준비물 (Mac 쪽, 1회)

- macOS 설정 → 일반 → 공유 → **원격 로그인(SSH) 켬**.
- Windows에서 키 생성 후 Mac `~/.ssh/authorized_keys`에 공개키 추가. Windows `~/.ssh/config`:
  ```
  Host mac
      HostName <mac-ip-or-hostname>
      User <mac-user>
      IdentityFile ~/.ssh/id_ed25519_mac
  ```
  Mac IP가 DHCP면 공유기에서 예약해 둔다(바뀌면 모든 스크립트가 깨짐).
- Xcode(+ Command Line Tools), `pip3 install --user pymobiledevice3`.
- WebDriverAgent: `git clone https://github.com/appium/WebDriverAgent ~/WebDriverAgent`, Xcode에서 서명 팀 지정 후 한 번 빌드:
  ```
  xcodebuild build-for-testing -project ~/WebDriverAgent/WebDriverAgent.xcodeproj \
    -scheme WebDriverAgentRunner -destination 'generic/platform=iOS' \
    -derivedDataPath ~/wda-build -allowProvisioningUpdates
  ```
  SSH 세션에서 서명하면 키체인이 잠겨 `errSecInternalComponent`가 난다 → 빌드 전에
  `security unlock-keychain -p "$(cat ~/.config/<keychain-pw-file>)" ~/Library/Keychains/login.keychain-db`
  (비밀번호 파일은 600 권한, 저장소에 넣지 말 것). 새 기기는 자동 프로비저닝으로 프로필에 들어가야 한다.
- 폰: 설정 → 개인정보 보호 및 보안 → **개발자 모드 켬**, Mac 신뢰. 시험 동안 자동 잠금 '안 함'. 가능하면 암호 끔.

## 1. 기기 식별

```bash
ssh mac 'xcrun devicectl list devices'                       # 이름, CoreDevice ID, 모델, 상태
ssh mac 'xcrun devicectl device info details --device <coredevice-id>' | grep -iE "udid|osVersion|passcode|developerMode"
ssh mac 'pymobiledevice3 lockdown get --udid <hw-udid> com.apple.disk_usage' | grep AmountDataAvailable   # 여유 공간(바이트)
ssh mac 'pymobiledevice3 lockdown info --udid <hw-udid>' | grep -E "SIMStatus|CarrierBundleInfoArray"     # 빈 배열이면 통신사 없음 → 셀룰러/전화 시험 불가
```

ID가 두 종류다. **devicectl은 CoreDevice ID**(UUID), **xcodebuild destination과 pymobiledevice3는 하드웨어 UDID**(`00008xxx-...`, `details`의 `udid`).

## 2. 원격 빌드

- 빌드 스크립트는 Mac에 두고 Windows는 `ssh mac '<launcher>'`로 트리거만 한다. 런처는 **ssh가 붙어 있는 동안** VCS sync와 키체인 해제를 하고, 그다음 빌드를 `nohup ... &`으로 분리해 로그 파일에 쓴다. Windows는 `ssh mac 'tail -f <log>'`로 따라가거나 상태 파일만 확인.
- 스크립트를 Windows에서 업로드한다면 CRLF를 LF로 바꿔서 보낸다(zsh가 CRLF 스크립트를 거부).
- 빌드 로그에서 **sync가 실제로 갱신했는지** 확인(낡은 쓰기 가능 파일 함정). 바뀐 소스 파일이 컴파일 목록에 나오는지도 본다.
- 설치는 스크립트에 맡기지 말고 명시적으로(기기 여러 대면 자동 선택이 모호):
  ```bash
  ssh mac 'xcrun devicectl device install app --device <coredevice-id> <path>/<App>.app'
  ```
  `ios-deploy`는 USB 신뢰가 없으면 실패하므로 devicectl을 쓴다.

## 3. WebDriverAgent로 터치·스크린샷

WDA 상시 실행(폰 암호가 있으면 이때 폰에 'Enable UI Automation' 입력창이 뜬다, 64초):
```bash
ssh mac 'cd ~/WebDriverAgent && (nohup xcodebuild test-without-building \
  -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner \
  -destination id=<hw-udid> -derivedDataPath ~/wda-build > ~/wda-<device>.log 2>&1 &)'
ssh mac 'grep ServerURLHere ~/wda-<device>.log'   # 떴는지 확인
```
`Timed out while enabling automation mode` = 암호 입력이 안 됨. 같은 명령 반복하지 말고 사람에게 요청한다.

USB로 포워딩(오프라인 시험에도 유지됨)하고 Windows까지 SSH 터널:
```bash
ssh mac 'nohup pymobiledevice3 usbmux forward --serial <hw-udid> 8200 8100 > ~/fwd.log 2>&1 &'
ssh -f -N -o ExitOnForwardFailure=yes -L 18200:127.0.0.1:8200 mac
curl -s http://127.0.0.1:18200/status      # WDA 응답 확인
```
기기마다 Mac 포트(8100, 8200, …)와 Windows 포트를 다르게.

세션·조작은 [scripts/ios.py](../scripts/ios.py) 참고. 핵심 API:

| 동작 | 요청 |
|---|---|
| 세션 생성(앱 실행) | `POST /session` `{"capabilities":{"alwaysMatch":{"bundleId":B,"shouldWaitForQuiescence":false,"arguments":[...]}}}` |
| idle 대기 끄기 | `POST /session/:id/appium/settings` `{"settings":{"waitForIdleTimeout":0,"animationCoolOffTimeout":0}}` |
| 탭 | `POST /session/:id/wda/tap` `{"x":..,"y":..}` (포인트 단위) |
| 드래그/스크롤 | `POST /session/:id/wda/dragfromtoforduration` |
| 키 입력 | `POST /session/:id/wda/keys` `{"value":[...]}` |
| 스크린샷 | `GET /screenshot` (base64 PNG, 픽셀 단위 → 포인트로 축소해 쓰면 좌표가 맞음) |
| 홈 / 복귀 | `POST /wda/homescreen`, `POST /session/:id/wda/apps/activate` |

- 좌표 = 포인트. 스크린샷을 `포인트 폭`(예: 420)으로 줄여 저장하면 이미지 좌표를 그대로 탭에 쓴다. 가로 재생 화면은 이미지가 가로로 돌아 나오므로 비율을 다시 계산.
- 시스템 팝업(로컬 네트워크·알림 권한)은 첫 실행에 뜬다. 스크린샷으로 보고 탭.
- 제어센터: 오른쪽 위 모서리에서 아래로 드래그 → 비행기 모드/Wi-Fi 타일 탭 → 빈 곳 탭으로 닫기.
- 앱 재실행: `xcrun devicectl device process launch --device <id> --terminate-existing <bundle-id>` 후 ~12초 뒤 새 세션.
- 키보드가 버튼을 가리면 리턴 키 위치를 탭해 내린 뒤 누른다.

## 4. 앱 로그·파일 (AFC / house_arrest)

Development 빌드(get-task-allow)는 앱 컨테이너에 접근할 수 있다.
```bash
# 비대화형으로 여러 명령
ssh mac 'printf "ls -l /Documents/Downloads\nexit\n" | pymobiledevice3 apps afc --udid <hw-udid> <bundle-id>'
# UE 로그 파일 회수
ssh mac 'printf "pull /Documents/<Project>/Saved/Logs/<Project>.log /tmp/app.log\nexit\n" | pymobiledevice3 apps afc --udid <hw-udid> <bundle-id>' && scp mac:/tmp/app.log .
# 파일 삭제(손상/누락 시나리오)
ssh mac 'printf "rm /Documents/Downloads/<file>\nexit\n" | pymobiledevice3 apps afc --udid <hw-udid> <bundle-id>'
```
AFC 셸 명령: `ls -l`, `stat`, `pull`, `push`, `rm`, `mv`, `walk`. `ls -l`의 크기로 받은 파일 크기를 서버 바이트와 대조한다.

UE 로그는 버퍼링돼 몇 초~수십 초 늦을 수 있다. 줄 수가 오래 안 늘면 앱 정지와 구분하려고 CPU를 본다:
```bash
ssh mac 'pymobiledevice3 developer dvt sysmon process single --udid <hw-udid> -f name=<ProcName> -k cpuUsage -k physFootprint --human'
```
`physFootprint`는 메모리 한도(jetsam) 문제 진단에도 쓴다.

## 5. 시스템 로그 (NSLog, nsurlsessiond 등)

ObjC `NSLog`와 OS 데몬 로그는 UE 로그에 없다:
```bash
ssh mac 'nohup pymobiledevice3 syslog live --udid <hw-udid> > /tmp/sys.log 2>&1 & echo $! > /tmp/sys.pid'
# ... 시나리오 실행 ...
ssh mac 'kill $(cat /tmp/sys.pid); grep -E "<YourTag>|nsurlsessiond" /tmp/sys.log | head'
```
macOS엔 `timeout`이 없으니 백그라운드 + kill로 시간을 자른다. 백그라운드 다운로드(NSURLSession background) 문제는 `nsurlsessiond` 줄에서 `Task <...> resuming / will begin` 이후 네트워크 활동이 있는지로 판정한다.

## 6. 화면 밖 상태 확인 팁

- 디스크 여유 공간을 1분 간격으로 찍으면 화면 % 없이도 다운로드가 실제로 진행 중인지 안다.
- 재생 순서는 로그의 미디어 Open 경로를 시간순으로 뽑아 서버 데이터로 계산한 기대 순서와 비교한다.
- 서버 기대값은 테스트 계정 토큰으로 API를 직접 조회해 계산한다(토큰·OTP 우회 코드는 저장소에 적지 않는다).
