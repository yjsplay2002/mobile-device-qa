"""WebDriverAgent + AFC helper for an iPhone attached to a remote Mac.

Run on the agent's machine (Windows/Linux). Talks to WDA through an SSH tunnel and
reaches the app container / logs through `ssh <mac> pymobiledevice3 ...`.

Config (environment variables):
  IOS_WDA      WDA base URL through the tunnel, e.g. http://127.0.0.1:18200
  IOS_MAC      ssh host alias of the Mac, e.g. mac
  IOS_DEVICE   CoreDevice ID (devicectl)
  IOS_UDID     hardware UDID (pymobiledevice3)
  IOS_BUNDLE   app bundle id
  IOS_PM       pymobiledevice3 path on the Mac (default: pymobiledevice3)
  IOS_APPARGS  extra launch arguments for the app, separated by '|'

usage: python ios.py relaunch | new | tap X Y | drag X1 Y1 X2 Y2 [sec] | keys TEXT
                     | shot out.png [pt_width] | home | activate | log out.log | afc "cmd" ...
Coordinates are points. `shot` resizes to the point width so image coords == tap coords.
"""
import base64, json, os, subprocess, sys, time, urllib.request

B = os.environ.get('IOS_WDA', 'http://127.0.0.1:18100')
MAC = os.environ.get('IOS_MAC', 'mac')
DEVICE = os.environ.get('IOS_DEVICE', '')
UDID = os.environ.get('IOS_UDID', '')
BUNDLE = os.environ.get('IOS_BUNDLE', '')
PM = os.environ.get('IOS_PM', 'pymobiledevice3')
APPARGS = [a for a in os.environ.get('IOS_APPARGS', '').split('|') if a]
SESS_FILE = os.environ.get('IOS_SESS_FILE', 'ios_sess.txt')


def req(method, path, data=None, timeout=60):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(B + path, method=method, data=body, headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def new():
    caps = {'bundleId': BUNDLE, 'shouldWaitForQuiescence': False, 'arguments': APPARGS}
    s = req('POST', '/session', {'capabilities': {'alwaysMatch': caps}}, 120)['value']['sessionId']
    open(SESS_FILE, 'w').write(s)
    # Video playback never goes idle; without this every call waits and times out.
    try:
        req('POST', f'/session/{s}/appium/settings', {'settings': {'waitForIdleTimeout': 0, 'animationCoolOffTimeout': 0}})
    except Exception:
        pass
    return s


def sess():
    try:
        return open(SESS_FILE).read().strip()
    except OSError:
        return new()


def tap(x, y): return req('POST', f'/session/{sess()}/wda/tap', {'x': x, 'y': y})
def drag(x1, y1, x2, y2, d=0.3): return req('POST', f'/session/{sess()}/wda/dragfromtoforduration', {'fromX': x1, 'fromY': y1, 'toX': x2, 'toY': y2, 'duration': d})
def keys(text): return req('POST', f'/session/{sess()}/wda/keys', {'value': list(text)})
def home(): return req('POST', '/wda/homescreen', {})
def activate(): return req('POST', f'/session/{sess()}/wda/apps/activate', {'bundleId': BUNDLE})


def shot(path, pt_width=None):
    open(path, 'wb').write(base64.b64decode(req('GET', '/screenshot')['value']))
    if pt_width:
        from PIL import Image
        im = Image.open(path)  # landscape shots come back rotated: pass the point width of that orientation
        im.resize((pt_width, round(im.height * pt_width / im.width))).save(path)


def ssh(cmd):
    return subprocess.run(['ssh', MAC, cmd], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout


def relaunch(wait=12):
    # Launch with devicectl first; creating a WDA session at the same moment can crash UE init.
    ssh(f'xcrun devicectl device process launch --device {DEVICE} --terminate-existing {BUNDLE}')
    time.sleep(wait)
    return new()


def afc(*cmds):
    script = '\\n'.join(list(cmds) + ['exit'])
    return ssh(f'printf "{script}\\n" | {PM} apps afc --udid {UDID} {BUNDLE} 2>/dev/null')


def pull_log(remote_path, local='app.log'):
    ssh(f'rm -f /tmp/_app.log; printf "pull {remote_path} /tmp/_app.log\\nexit\\n" | {PM} apps afc --udid {UDID} {BUNDLE} >/dev/null 2>&1')
    subprocess.run(['scp', '-q', f'{MAC}:/tmp/_app.log', local])
    return local


def free_bytes():
    out = ssh(f'{PM} lockdown get --udid {UDID} com.apple.disk_usage 2>/dev/null')
    for line in out.splitlines():
        if '"AmountDataAvailable"' in line:
            return int(line.split(':')[1].strip(' ,'))
    return None


if __name__ == '__main__':
    c, a = sys.argv[1], sys.argv[2:]
    if c == 'new': print(new())
    elif c == 'relaunch': print(relaunch())
    elif c == 'tap': tap(float(a[0]), float(a[1]))
    elif c == 'drag': drag(*map(float, a[:4]), float(a[4]) if len(a) > 4 else 0.3)
    elif c == 'keys': keys(a[0])
    elif c == 'shot': shot(a[0], int(a[1]) if len(a) > 1 else None)
    elif c == 'home': home()
    elif c == 'activate': activate()
    elif c == 'log': print(pull_log(a[0], a[1] if len(a) > 1 else 'app.log'))
    elif c == 'afc': print(afc(*a))
    elif c == 'free': print(free_bytes())
    else: sys.exit(__doc__)
