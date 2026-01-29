from flask import Flask, render_template, request, jsonify
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, FeedbackRequired, PleaseWaitFewMinutes
import threading
import time
import random
import os
import gc

app = Flask(__name__)
app.secret_key = "sujal_hawk_multi_id_spam_2026"

state = {
    "running": False,
    "sent": 0,
    "logs": [],
    "start_time": None,
    "current_acc_index": 0,
    "account_stats": []
}

cfg = {
    "accounts": [],  # [{"sessionid": "...", "thread_id": "...", "client": None}]
    "messages": [],
    "spam_delay": 30,
    "break_sec": 120,
    "switch_after_msgs": 100
}

DEVICES = [
    {"phone_manufacturer": "Google", "phone_model": "Pixel 9 Pro", "android_version": 35, "android_release": "15", "app_version": "330.0.0.45.112"},
    {"phone_manufacturer": "Samsung", "phone_model": "SM-S938B", "android_version": 35, "android_release": "15", "app_version": "331.0.0.38.120"},
    {"phone_manufacturer": "OnePlus", "phone_model": "CPH2653", "android_version": 35, "android_release": "15", "app_version": "329.0.0.55.99"},
    {"phone_manufacturer": "Xiaomi", "phone_model": "24053PY3BC", "android_version": 35, "android_release": "15", "app_version": "332.0.0.29.110"},
]

def log(msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    state["logs"].append(entry)
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]
    print(entry)
    gc.collect()  # Memory cleaner har log pe

def initialize_clients():
    log("Initializing clients – ONE TIME LOGIN ONLY")
    for acc in cfg["accounts"]:
        cl = Client()
        cl.delay_range = [3, 12]

        dev = random.choice(DEVICES)
        cl.set_device(dev)
        ua = f"Instagram {dev['app_version']} Android ({dev['android_version']}/{dev['android_release']}; 480dpi; 1080x2400; {dev['phone_manufacturer']}; {dev['phone_model']}; raven; raven; en_US)"
        cl.set_user_agent(ua)

        log(f"LOGIN ATTEMPT ACC #{cfg['accounts'].index(acc)+1} → Device: {dev['phone_model']}")

        try:
            cl.login_by_sessionid(acc["sessionid"])
            cl.get_timeline_feed()  # csrf refresh
            acc["client"] = cl
            log(f"LOGIN SUCCESS ACC #{cfg['accounts'].index(acc)+1}", important=True)
        except Exception as e:
            log(f"LOGIN FAILED ACC #{cfg['accounts'].index(acc)+1} → {str(e)[:100]}", important=True)

def generate_variation(msg):
    emojis = ['🔥', '💀', '😈', '🚀', '😂', '🤣', '😍', '❤️', '👍', '🙌']
    if random.random() > 0.5:
        msg += " " + random.choice(emojis) + random.choice(emojis)
    return msg

def spam_message(cl, thread_id, msg):
    try:
        cl.direct_send(msg, thread_ids=[thread_id])
        return True
    except Exception as e:
        log(f"SEND FAILED → {str(e)[:80]}")
        return False

def nc_loop():
    initialize_clients()

    valid_accounts = [acc for acc in cfg["accounts"] if acc.get("client")]
    if not valid_accounts:
        log("No valid accounts – stopping")
        state["running"] = False
        return

    state["account_stats"] = [{"sent": 0, "errors": 0} for _ in valid_accounts]

    acc_index = 0
    sent_this_account = 0
    total_sent = 0

    while state["running"]:
        acc = valid_accounts[acc_index]
        cl = acc["client"]

        msg = random.choice(cfg["messages"])
        msg = generate_variation(msg)

        thread_id = acc["thread_id"]
        if spam_message(cl, thread_id, msg):
            state["sent"] += 1
            state["account_stats"][acc_index]["sent"] += 1
            sent_this_account += 1
            total_sent += 1
            log(f"SENT #{state['sent']} → {msg[:40]} (Acc #{acc_index+1})")

        if total_sent >= cfg["switch_after_msgs"]:
            acc_index = (acc_index + 1) % len(valid_accounts)
            total_sent = 0
            log(f"SWITCHED TO ACCOUNT #{acc_index+1}")

        if sent_this_account >= 50:
            log(f"BREAK {cfg['break_sec']} sec")
            time.sleep(cfg["break_sec"])
            sent_this_account = 0

        delay = cfg["spam_delay"] + random.uniform(-2, 3)
        time.sleep(max(5, delay))

        # Error handling
        if random.random() < 0.05:  # simulate occasional fail
            log("Random rate limit simulation – waiting extra 30s")
            time.sleep(30)

    log("SPAM LOOP STOPPED")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global state, cfg
    state["running"] = False
    time.sleep(1)

    state = {
        "running": True,
        "sent": 0,
        "logs": ["[START] Initializing..."],
        "start_time": time.time(),
        "current_acc_index": 0,
        "account_stats": []
    }

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

    cfg["messages"] = [m.strip() for m in request.form["messages"].split("\n") if m.strip()]
    cfg["spam_delay"] = float(request.form.get("spam_delay", "30"))
    cfg["break_sec"] = int(request.form.get("break_sec", "120"))
    cfg["switch_after_msgs"] = int(request.form.get("switch_after_msgs", "100"))

    threading.Thread(target=nc_loop, daemon=True).start()
    log(f"[STARTED] {len(cfg['accounts'])} accounts | Delay: {cfg['spam_delay']} sec")

    return jsonify({"ok": True})

@app.route("/stop")
def stop():
    state["running"] = False
    log("[STOPPED] By user")
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
        "sent": state["sent"],
        "uptime": uptime,
        "logs": state["logs"][-150:]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
