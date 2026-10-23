# Android 실기기

## 1. 접근 경로 세 가지

| 경로 | 언제 | 할 수 있는 것 |
|---|---|---|
| **로컬 USB adb** | 책상의 폰 | 전부(설치, 탭, 로그, 파일, 네트워크 토글) |
| **Samsung Remote Test Lab** (developer.samsung.com/remote-test-lab, 무료) | 없는 갤럭시 기종 재현 | 원격 화면 + adb(설치, logcat, input). 사람이 웹에서 기기 예약 |
| **Firebase Test Lab** (`gcloud firebase test android run`) | 무인으로 실물 arm64 부팅·크래시 확인 | robo/instrumentation만, 상태 제어 불가 |

에뮬레이터 주의: x86_64 AVD는 arm64 앱을 번역해 돌리는데, ARMv8 Crypto 명령(SHA1 등)을 번역기가 지원하지 않아 UE 앱이 SIGILL로 죽을 수 있다. 판정용으로 쓰지 말고 스모크 정도만.

### 로컬 USB
```bash
adb devices -l                       # unauthorized면 폰에서 USB 디버깅 허용(RSA)
adb -s <serial> shell getprop ro.product.model
adb -s <serial> shell getprop ro.build.version.release
```
기기 여러 대면 항상 `-s <serial>`. 무선 디버깅: 폰 개발자 옵션 → 무선 디버깅 → `adb pair <ip>:<port>` 후 `adb connect <ip>:<port>`.

### Samsung Remote Test Lab
1. 웹에서 기기 예약 → 원격 화면이 뜸.
2. 클라이언트 메뉴의 Remote Debug Bridge 실행(rdb 도구) → Connect. 로컬 adb에 `localhost:<port>` 기기가 생긴다(포트는 rdb 프로세스의 LISTEN 포트).
3. 웹 원격 화면에서 USB 디버깅 허용을 눌러야 `offline`이 `device`로 바뀐다.
4. **세션 중 `adb kill-server`/`adb disconnect` 금지** — 브리지가 끊겨 Connect를 다시 눌러야 한다.
5. Shipping 빌드처럼 FLAG_SECURE가 켜진 화면은 원격 화면·screencap이 검게 나온다 → Development 빌드.

### Firebase Test Lab
```bash
gcloud firebase test android run --project=<gcp-project> --type robo \
  --app app.apk --device model=<model-id>,version=<api> --timeout 5m
```
`testing.googleapis.com`, `toolresults.googleapis.com` API를 먼저 켠다. 무인 실행엔 서비스 계정 키가 필요(`gcloud auth login`은 대화형).

## 2. 설치·실행

```bash
adb -s <serial> install -r app.apk          # -r = 데이터 유지(같은 서명, versionCode 같거나 높음)
adb -s <serial> shell monkey -p <package> -c android.intent.category.LAUNCHER 1
adb -s <serial> shell am force-stop <package>
```
AAB만 있으면 bundletool로 universal APK를 만든다:
`bundletool build-apks --bundle=app.aab --output=app.apks --mode=universal --ks=... ` → zip에서 `universal.apk` 추출.

## 3. 조작

```bash
adb -s <serial> shell input tap X Y
adb -s <serial> shell input swipe X1 Y1 X2 Y2 300      # 마지막 = ms. 탭/스크롤 경계 시험엔 duration이 중요
adb -s <serial> shell input text 'hello'
adb -s <serial> shell input keyevent KEYCODE_ENTER
MSYS_NO_PATHCONV=1 adb -s <serial> exec-out screencap -p > shot.png
```
- 좌표는 **실제 픽셀**. 스크린샷 크기 = `adb shell wm size`.
- UE 앱은 화면 전체가 SurfaceView 하나라 `uiautomator dump`에 위젯이 안 나온다. 좌표는 스크린샷에서 읽거나, 앱에 "위젯 목록+화면 좌표를 로그로 찍는" 개발용 콘솔 명령을 만들어 둔다.
- **기기 뒤로가기 키**는 앱을 종료시킬 수 있으니 앱 안의 뒤로가기 버튼을 탭한다.

### UE 콘솔 명령을 adb로 보내기 (Development 빌드)
UE Android 템플릿은 non-Shipping에서 콘솔 명령 브로드캐스트 수신기를 등록한다:
```bash
adb -s <serial> shell "am broadcast -a android.intent.action.RUN -e cmd 'stat fps'"
```
`FSelfRegisteringExec`로 앱 전용 명령(페이지 이동, 상태 덤프, 디스크 채우기, 가짜 네트워크 이벤트 등)을 만들어 두면 시험 준비가 빨라진다. 단 **시험 대상 입력은 실제 터치로** — 위젯 함수를 직접 부르면 입력 라우팅 버그를 못 잡는다.

## 4. 로그·파일

```bash
adb -s <serial> logcat -c
adb -s <serial> logcat -v time > logcat.txt          # 백그라운드로 받고 끝나면 kill
adb -s <serial> logcat -s <Tag>                       # Shipping은 앱 태그만 남는 경우가 많다
MSYS_NO_PATHCONV=1 adb -s <serial> pull /sdcard/Android/data/<package>/files/<Project>/Saved/Logs/<Project>.log
adb -s <serial> shell run-as <package> ls -l files   # debuggable 빌드만
adb -s <serial> shell dumpsys package <package> | grep versionCode
```
UE는 SurfaceView 직접 렌더라 `dumpsys gfxinfo` 프레임 통계가 비어 있다. 프레임은 `stat unit` 로그나 `dumpsys SurfaceFlinger --latency`로.

## 5. 네트워크·전원 시나리오

```bash
adb -s <serial> shell svc wifi disable    # / enable
adb -s <serial> shell cmd connectivity airplane-mode enable   # / disable (Android 11+)
adb -s <serial> shell dumpsys telephony.registry | grep -i mServiceState   # SIM/셀룰러 확인
adb -s <serial> shell input keyevent KEYCODE_HOME                          # 백그라운드 전환
```
- SIM 없는 기기(`gsm.sim.state` = ABSENT)는 셀룰러 전환·전화 수신 시험 불가 — 알람 앱 등으로 오디오 포커스만 대체 확인하고 그렇게 적는다.
- adb 데몬이 재시작되면 출력이 유실된다. 판정에 쓰는 명령은 결과가 비면 재시도.
- 폰이 스스로 재부팅하면 adb가 끊긴다. `adb wait-for-device`.

## 6. 저장공간

```bash
adb -s <serial> shell df -h /data
adb -s <serial> shell fallocate -l 20G /sdcard/fill.bin   # 여유 공간 줄이기(끝나면 rm)
```
