#!/usr/bin/env python3
"""
WhatsApp sender (native) for the Leilao PB routine — runs on YOUR Mac with real
network (the Cowork sandbox cannot reach Z-API, so this part runs locally).

It reads:
  whatsapp_outbox.json   <- written by leilao_routine.py (messages ready to send)
  whatsapp_secrets.json  <- YOUR Z-API credentials (never commit this)
and sends each message via the Z-API WhatsApp API, skipping anything already
sent (idempotent via whatsapp_sent.json).

Usage:
  python3 whatsapp_sender.py            # send pending messages
  python3 whatsapp_sender.py --status   # check if the instance is connected (no send)
  python3 whatsapp_sender.py --dry-run  # print what WOULD be sent, send nothing
  python3 whatsapp_sender.py --groups   # list your WhatsApp groups + their IDs (no send)
  python3 whatsapp_sender.py --test +5583999999999   # send one test message

Para enviar a um GRUPO: rode --groups, copie o ID do grupo (ex.: 120363...-group)
e coloque esse ID no campo de destinatários do alarme (no painel), igual a um número.

Setup (once):
  pip3 install requests
  cp whatsapp_secrets.example.json whatsapp_secrets.json   # then fill it in
  # 1. Create account at https://z-api.io
  # 2. Create an instance and scan the QR code with your WhatsApp
  # 3. Copy instance_id and token from the instance dashboard
  # 4. Security tab -> "Account Security Token": copy it into client_token
  #    (REQUIRED if that feature is enabled — without it every call returns
  #     {"error":"null not allowed"} / HTTP 4xx even with the right id/token)
"""
import json, os, sys, re, datetime

try:
    import requests
except ImportError:
    print("Missing dependency: pip3 install requests")
    sys.exit(1)

HERE    = os.path.dirname(os.path.abspath(__file__))
OUTBOX  = os.path.join(HERE, 'whatsapp_outbox.json')
SECRETS = os.path.join(HERE, 'whatsapp_secrets.json')
SENTLOG = os.path.join(HERE, 'whatsapp_sent.json')

ZAPI_BASE   = "https://api.z-api.io/instances/{instance_id}/token/{token}/send-text"
ZAPI_STATUS = "https://api.z-api.io/instances/{instance_id}/token/{token}/status"
ZAPI_GROUPS = "https://api.z-api.io/instances/{instance_id}/token/{token}/groups"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f: return json.load(f)
        except Exception as e:
            print(f"! could not read {os.path.basename(path)}: {e}")
    return default

def norm_phone(number):
    """Return bare digits with country code, no + or spaces. E.g. '5548999001155'"""
    n = str(number).strip()
    # strip whatsapp: prefix if present
    n = re.sub(r'^whatsapp:', '', n, flags=re.IGNORECASE).strip()
    digits = re.sub(r'[^\d]', '', n)
    # Brazil: if starts with 55 and looks right, keep as-is
    # Otherwise assume Brazil and prepend 55
    if not digits.startswith('55') and len(digits) <= 11:
        digits = '55' + digits
    return digits

def is_group_id(raw):
    """True if 'raw' looks like a WhatsApp GROUP id rather than a phone number.
    Z-API group ids look like '120363019502305150-group' (or end with '@g.us'),
    and are much longer than a phone number. Also accepts an explicit 'group:'/'g:' tag."""
    s = str(raw).strip().lower()
    if s.startswith('group:') or s.startswith('g:'):
        return True
    if s.endswith('-group') or '@g.us' in s:
        return True
    digits = re.sub(r'[^\d]', '', s)
    return len(digits) >= 15   # group ids ~18 digits; BR phones are <= 13

def to_destination(raw):
    """Z-API 'phone' value: a GROUP id is sent VERBATIM (never normalized, so the
    '-group' suffix is preserved); a phone number is normalized with country code."""
    s = str(raw).strip()
    low = s.lower()
    if low.startswith('group:'):
        s = s[6:].strip()
    elif low.startswith('g:'):
        s = s[2:].strip()
    return s if is_group_id(s) else norm_phone(s)

def list_groups(instance_id, token, client_token):
    """Return (list_of_groups, error). Read-only; sends nothing."""
    url = ZAPI_GROUPS.format(instance_id=instance_id, token=token)
    out = []
    for page in range(1, 21):
        try:
            resp = requests.get(url, headers=zapi_headers(client_token),
                                params={"page": page, "pageSize": 50}, timeout=20)
        except Exception as e:
            return None, str(e)
        if resp.status_code != 200:
            try: err = resp.json()
            except Exception: err = resp.text
            return None, f"HTTP {resp.status_code}: {err}"
        try:
            data = resp.json()
        except Exception:
            return None, f"resposta inesperada: {resp.text[:200]}"
        if not isinstance(data, list) or not data:
            break
        out.extend(data)
        if len(data) < 50:
            break
    return out, None

def zapi_headers(client_token):
    """Z-API requires the account 'Client-Token' header when Account Security
    Token is enabled (default on new accounts). Without it every request is
    rejected even if instance_id/token are correct."""
    h = {"Content-Type": "application/json"}
    if client_token:
        h["Client-Token"] = client_token
    return h

def check_status(instance_id, token, client_token):
    """Return (connected, info_dict_or_error). Read-only; sends no message."""
    url = ZAPI_STATUS.format(instance_id=instance_id, token=token)
    try:
        resp = requests.get(url, headers=zapi_headers(client_token), timeout=15)
        try:
            data = resp.json()
        except Exception:
            return False, f"HTTP {resp.status_code}: {resp.text}"
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {data}"
        return bool(data.get("connected")), data
    except Exception as e:
        return False, str(e)

def send_zapi(instance_id, token, client_token, phone, message):
    """Send a WhatsApp message via Z-API. Returns (ok, error_message)."""
    url = ZAPI_BASE.format(instance_id=instance_id, token=token)
    payload = {"phone": phone, "message": message}
    try:
        resp = requests.post(url, json=payload,
                             headers=zapi_headers(client_token), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            # Z-API returns {"zaapId": "...", "messageId": "..."} on success
            if data.get("zaapId") or data.get("messageId"):
                return True, data.get("messageId") or data.get("zaapId")
            # Some versions return {"value": true}
            if data.get("value") is True:
                return True, "ok"
            return False, f"unexpected response: {data}"
        else:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            return False, f"HTTP {resp.status_code}: {err}"
    except requests.exceptions.Timeout:
        return False, "request timed out"
    except Exception as e:
        return False, str(e)

def main():
    args = sys.argv[1:]
    dry = '--dry-run' in args

    secrets = load_json(SECRETS, None) or {}
    instance_id  = secrets.get('instance_id')
    token        = secrets.get('token')
    # Account Security Token — sent as the 'Client-Token' header. Accept a few
    # common key spellings so older secrets files keep working.
    client_token = (secrets.get('client_token') or secrets.get('clientToken')
                    or secrets.get('security_token') or secrets.get('account_token'))
    # from_phone is optional metadata; Z-API uses the connected WhatsApp automatically
    from_phone   = secrets.get('from_phone', '(seu WhatsApp conectado ao Z-API)')

    if not dry and not (instance_id and token):
        print("whatsapp_secrets.json must have instance_id and token. "
              "Copy whatsapp_secrets.example.json to whatsapp_secrets.json and fill it in.")
        sys.exit(1)

    # --status mode: check the instance connection without sending anything
    if '--status' in args:
        connected, info = check_status(instance_id, token, client_token)
        print(f"Z-API status: {'CONNECTED ✓' if connected else 'NOT connected ✗'}")
        print(json.dumps(info, ensure_ascii=False, indent=2) if isinstance(info, dict) else info)
        if not client_token:
            print("\n⚠ No client_token in whatsapp_secrets.json. If your Z-API account has "
                  "'Account Security Token' enabled, every request fails until you add it.")
        return

    # --groups mode: list groups + ids so you can paste an id into an alarm's recipients
    if '--groups' in args:
        groups, err = list_groups(instance_id, token, client_token)
        if err:
            print("Erro ao listar grupos:", err); sys.exit(1)
        if not groups:
            print("Nenhum grupo encontrado. (A conta Z-API precisa estar conectada e "
                  "participar de pelo menos um grupo.)")
            return
        print(f"{len(groups)} grupo(s) encontrado(s):\n")
        for g in groups:
            print(f"  • {g.get('name') or '(sem nome)'}")
            print(f"      ID: {g.get('phone')}\n")
        print("Para disparar a um grupo: copie o ID acima e cole no campo de "
              "destinatários (📱) do alarme, no painel — funciona igual a um número.")
        return

    # --test mode: one message, ignore outbox
    if '--test' in args:
        i = args.index('--test')
        raw_to = args[i + 1] if i + 1 < len(args) else None
        if not raw_to:
            print("usage: --test +5583999999999"); sys.exit(1)
        msgs = [{'key': 'test', 'to': raw_to,
                 'body': '✅ Teste do sender de WhatsApp do Leilão PB. Funcionando!'}]
        outbox = {'date': 'test', 'messages': msgs}
    else:
        outbox = load_json(OUTBOX, {'messages': []})

    messages = outbox.get('messages', [])
    if not messages:
        print("Outbox empty — nothing to send."); return

    sent = load_json(SENTLOG, {})
    pending = [m for m in messages if m.get('key') not in sent or m.get('key') == 'test']
    if not pending:
        print(f"All {len(messages)} message(s) already sent. Nothing to do."); return

    print(f"{len(pending)} message(s) to send (from {from_phone}).")

    if dry:
        for m in pending:
            phone = to_destination(m['to'])
            kind = 'GRUPO' if is_group_id(m['to']) else 'número'
            print(f"\n--- to {phone} [{kind}] (alarm: {m.get('alarmName')}) ---\n{m['body']}")
        print(f"\n[dry-run] nothing sent.")
        return

    ok = 0
    for m in pending:
        phone = to_destination(m['to'])
        success, result = send_zapi(instance_id, token, client_token, phone, m['body'])
        if success:
            sent[m['key']] = {'to': phone, 'messageId': result,
                              'at': datetime.datetime.now().isoformat()}
            ok += 1
            print(f"  ✓ sent to {phone}  (messageId {result})")
        else:
            print(f"  ✗ FAILED to {phone}: {result}")

    with open(SENTLOG, 'w', encoding='utf-8') as f:
        json.dump(sent, f, ensure_ascii=False, indent=1)
    print(f"Done: {ok}/{len(pending)} sent.")

if __name__ == '__main__':
    main()
