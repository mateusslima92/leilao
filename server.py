#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor local do Leilão PB — faz o botão "▶ Rodar agora" do painel funcionar.

Por que existe: um botão no navegador NÃO consegue, sozinho, executar um script
no seu Mac (baixar o CSV da Caixa, etc.). Este servidor minúsculo roda no seu Mac
e expõe um endpoint que o painel chama por localhost. Assim, um clique no painel
dispara TODO o ciclo (baixar CSV -> analisar + alarmes -> WhatsApp -> baseline).

Como usar: dê duplo-clique em "Abrir Painel.command" (ele inicia este servidor e
abre o painel no navegador). Ou rode no Terminal:  python3 server.py

Só escuta em 127.0.0.1 (sua máquina). Sem dependências além da biblioteca padrão.

Rotas:
  GET  /            -> serve dashboard_leilao.html
  GET  /<arquivo>   -> serve arquivos da pasta do projeto (somente leitura, sem ".." )
  GET  /status      -> conteúdo de last_summary.json (resumo da última execução)
  POST /run         -> executa rodar_diario.sh (ciclo completo). Retorna {ok, log, summary}
  OPTIONS *         -> CORS preflight
"""
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 8765
RUN_SCRIPT = os.path.join(HERE, "rodar_diario.sh")
RUN_LOG = os.path.join(HERE, "rodar_diario.log")
DASHBOARD = "dashboard_leilao.html"
SUMMARY = os.path.join(HERE, "last_summary.json")
RUN_TIMEOUT = 600  # segundos

_run_lock = threading.Lock()
_running = False

MIME = {
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
}


def _safe_path(urlpath):
    """Resolve a URL path to a file inside HERE; None if it escapes the folder."""
    rel = urlpath.lstrip("/")
    if rel in ("", "/"):
        rel = DASHBOARD
    full = os.path.realpath(os.path.join(HERE, rel))
    if full != HERE and not full.startswith(HERE + os.sep):
        return None
    return full


def _run_cycle():
    """Run the full daily cycle script; return combined output (tail)."""
    try:
        p = subprocess.run(
            ["bash", RUN_SCRIPT],
            cwd=HERE, capture_output=True, text=True, timeout=RUN_TIMEOUT,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "Tempo esgotado (>%ds). O ciclo pode ainda estar rodando." % RUN_TIMEOUT
    except Exception as e:  # noqa
        return 1, "Erro ao executar rodar_diario.sh: %r" % e


class Handler(BaseHTTPRequestHandler):
    server_version = "LeilaoPB/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/status":
            try:
                with open(SUMMARY, encoding="utf-8") as f:
                    self._send(200, f.read())
            except FileNotFoundError:
                self._send(200, json.dumps({"error": "sem resumo ainda"}))
            return
        full = _safe_path(path)
        if not full or not os.path.isfile(full):
            self._send(404, json.dumps({"error": "nao encontrado"}))
            return
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, MIME.get(ext, "application/octet-stream"))

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/run":
            self._send(404, json.dumps({"error": "rota desconhecida"}))
            return
        global _running
        with _run_lock:
            if _running:
                self._send(409, json.dumps({"ok": False, "error": "Ja existe uma execucao em andamento."}))
                return
            _running = True
        try:
            rc, out = _run_cycle()
        finally:
            with _run_lock:
                _running = False
        summary = None
        try:
            with open(SUMMARY, encoding="utf-8") as f:
                summary = json.load(f)
        except Exception:  # noqa
            pass
        # rc==0 do script; rc==2 = prepare falhou (sem CSV). download em si e best-effort.
        ok = rc == 0
        # O script grava o detalhe em rodar_diario.log; mostramos esse trecho no painel.
        detail = out
        try:
            with open(RUN_LOG, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            if "INÍCIO" in "\n".join(lines):
                idx = max(i for i, l in enumerate(lines) if "INÍCIO" in l)
                detail = "\n".join(lines[idx:])
        except Exception:  # noqa
            pass
        tail = "\n".join((detail or out).splitlines()[-160:])
        self._send(200 if ok else 200, json.dumps({
            "ok": ok, "returncode": rc, "log": tail, "summary": summary,
            "error": None if ok else "rodar_diario.sh retornou codigo %d (veja o log)" % rc,
        }, ensure_ascii=False))

    def log_message(self, fmt, *args):  # quieter console
        pass


def main():
    os.chdir(HERE)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = "http://%s:%d/" % (HOST, PORT)
    print("=" * 60)
    print(" Painel do Leilao PB rodando em:  %s" % url)
    print(" Deixe esta janela ABERTA enquanto usa o painel.")
    print(" Para parar: feche a janela ou pressione Ctrl+C.")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
