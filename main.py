from flask import Flask, render_template, request, jsonify
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, FeedbackRequired, PleaseWaitFewMinutes, ClientError
import threading
import time
import random
import os
import gc

app = Flask(__name__)
app.secret_key = "sujal_hawk_instagrapi_nc_fixed_2026"

state = {"running": False, "changed": 0, "logs": [], "start_time": None}
cfg = {
    "accounts": [],  # [{"sessionid": "...", "thread_id": "...", "client": None}]
    "names": [],
    "nc_delay": 60,
}

DEVICES = [
    {"phone_manufacturer": "Google", "phone_model": "Pixel 9 Pro", "android_version": 35, "android_release": "15", "app_version": "330.0.0.45.112"},
    {"phone_manufacturer": "Samsung", "phone_model": "SM-S938B", "android_version": 35, "android_release": "15", "app_version": "331.0.0.38.120"},
    {"phone_manufacturer": "OnePlus", "phone_model": "CPH2653", "android_version": 35, "android_release": "15", "app_version": "329.0.0.55.99"},
    {"phone_manufacturer": "Xiaomi", "phone_model": "24053PY3BC", "android_version": 35, "android_release": "15", "app_version": "332.0.0.29.110"},
]

def log(msg, important=False):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    if important:
        entry = f"★★★ {entry} ★★★"
    state["logs"].append(entry)
    print(entry)
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]
    gc.collect()

def initialize_clients():
    log("Initializing clients (one-time login)")
    for acc in cfg["accounts"]:
        cl = Client()
        cl.delay_range = [2, 8]

        dev = random.choice(DEVICES)
        cl.set_device(dev)
        ua = f"Instagram {dev['app_version']} Android ({dev['android_version']}/{dev['android_release']}; 480dpi; 1080x2400; {dev['phone_manufacturer']}; {dev['phone_model']}; raven; raven; en_US)"
        cl.set_user_agent(ua)

        log(f"LOGIN ATTEMPT for sessionid ending ...{acc['sessionid'][-6:]} → Device: {dev['phone_model']}")

        try:
            cl.login_by_sessionid(acc["sessionid"])
            cl.get_timeline_feed()  # refresh csrf
            acc["client"] = cl
            log(f"LOGIN SUCCESS for this account", important=True)
        except LoginRequired:
            log(f"SESSION EXPIRED for this account", important=True)
        except ChallengeRequired:
            log(f"CHALLENGE REQUIRED for this account", important=True)
        except Exception as e:
            log(f"LOGIN ERROR → {str(e)[:100]}", important=True)

def name_change(cl, thread_id, new_name):
    try:
        payload = {"title": new_name.strip()}
        response = cl.private_request(
            f"direct_v2/threads/{thread_id}/update_title/",
            data=payload,
            headers=cl.get_headers(),
            method="POST"
        )
        if response.get("status") == "ok":
            log(f"NC SUCCESS → {new_name} (thread {thread_id})", important=True)
            state["changed"] += 1
            return True
        else:
            log(f"NC FAIL RESPONSE → {response.get('message', 'No message')}")
            return False
    except Exception as e:
        log(f"NC ERROR → {str(e)[:100]}")
        return False

def nc_loop():
    initialize_clients()  # Login only once

    valid_clients = [acc for acc in cfg["accounts"] if acc.get("client")]
    if not valid_clients or not cfg["names"]:
        log("No valid clients or names – stopping")
        state["running"] = False
        return

    acc_index = 0
    while state["running"]:
        acc = valid_clients[acc_index]
        cl = acc["client"]

        name_idx = acc_index % len(cfg["names"])
        new_name = cfg["names"][name_idx]

        thread_id = acc["thread_id"]
        name_change(cl, thread_id, new_name)

        acc_index = (acc_index + 1) % len(valid_clients)
        log(f"Switching to next account #{acc_index+1}")

        time.sleep(cfg["nc_delay"])

    log("NC LOOP STOPPED")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global state, cfg
    state["running"] = False
    time.sleep(1)

    state = {"running": True, "changed": 0, "logs": ["STARTED"], "start_time": time.time()}

    accounts_raw = request.form["accounts"].strip().split("\n")
    cfg["accounts"] = []
    for line in accounts_raw:
        line = line.strip()
        if line:
            parts = line.split(":")
            if len(parts) >= 2:
                sessionid = parts[0].strip()
                thread_id = parts[1].strip()
                cfg["accounts"].append({"sessionid": sessionid, "thread_id": thread_id, "client": None})

    cfg["names"] = [n.strip() for n in request.form["names"].split("\n") if n.strip()]
    cfg["nc_delay"] = float(request.form.get("nc_delay", "60"))

    threading.Thread(target=nc_loop, daemon=True).start()
    log(f"STARTED NC LOOP WITH {len(cfg['accounts'])} accounts | Delay: {cfg['nc_delay']}s")

    return jsonify({"ok": True})

@app.route("/stop")
def stop():
    state["running"] = False
    log("STOPPED BY USER")
    return jsonify({"ok": True})

@app.route("/status")
def status():
    uptime = "00:00:00"
    if state.get("start_time"):
        t = int(time.time() - state["start_time"])
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        uptime = f"{h:02d}:{m:02d}:{s:02d}"
    return jsonify({
        "running": state["running"],
        "changed": state["changed"],
        "uptime": uptime,
        "logs": state["logs"][-100:]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
