#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IAZ Jud - Servidor Local e Proxy para DataJud / Supabase
Serve o front-end web e atua como API backend para contornar restrições de CORS
do DataJud oficial, sincronizando diretamente com o Supabase sem depender do Google Apps Script.
"""

import sys
import os
import json
import socketserver
from http.server import SimpleHTTPRequestHandler
from sync_datajud import (
    consultar_datajud,
    sincronizar_processo,
    sincronizar_todos,
    supabase_request,
    SUPABASE_URL
)

PORT = int(os.environ.get("PORT", 8000))

class IazJudHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Permite requisições de qualquer origem (CORS liberado para PWA/Localhost)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PATCH, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, apikey, Prefer")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def responder_json(self, status_code, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/status":
            try:
                processos = supabase_request("ju_processos?select=count", extra_headers={"Prefer": "count=exact"})
                self.responder_json(200, {
                    "status": "online",
                    "supabase": "conectado",
                    "datajud_proxy": "ativo",
                    "porta": PORT
                })
            except Exception as e:
                self.responder_json(200, {
                    "status": "online",
                    "supabase_aviso": str(e),
                    "datajud_proxy": "ativo"
                })
            return

        # Serve arquivos estáticos do diretório raiz (index.html, etc.)
        return super().do_GET()

    def do_POST(self):
        # 1. Rota de consulta ao DataJud (usada pelo front-end para obter movimentos ou sincronizar)
        if self.path in ["/api/consultar", "/api/consultar_datajud"]:
            try:
                length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(length)
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}

                processo = payload.get("processo") or payload.get("numero")
                tribunal = payload.get("tribunal") or ""

                if not processo:
                    self.responder_json(400, {"success": False, "error": "Número do processo obrigatório."})
                    return

                res = consultar_datajud(processo, tribunal)
                if res.get("success"):
                    self.responder_json(200, {"success": True, "data": res})
                else:
                    self.responder_json(200, {"success": False, "mensagem": res.get("mensagem")})
            except Exception as e:
                self.responder_json(500, {"success": False, "error": str(e)})
            return

        # 2. Rota de sincronização completa de processo individual direto no Supabase
        elif self.path in ["/api/sincronizar_processo", "/api/sincronizar"]:
            try:
                length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(length)
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}

                processo = payload.get("processo")
                tribunal = payload.get("tribunal") or ""

                if not processo:
                    self.responder_json(400, {"success": False, "error": "Número do processo obrigatório."})
                    return

                ok = sincronizar_processo({"processo": processo, "tribunal": tribunal}, verbose=True)
                self.responder_json(200, {
                    "success": ok,
                    "message": "Processo sincronizado e salvo no Supabase com sucesso!" if ok else "Não localizado no tribunal informado."
                })
            except Exception as e:
                self.responder_json(500, {"success": False, "error": str(e)})
            return

        # 3. Rota de sincronização em lote de todos os processos
        elif self.path == "/api/sincronizar_todos":
            try:
                # Executa a sincronização completa
                sincronizar_todos(verbose=True)
                self.responder_json(200, {
                    "success": True,
                    "message": "Sincronização em lote finalizada com sucesso."
                })
            except Exception as e:
                self.responder_json(500, {"success": False, "error": str(e)})
            return

        else:
            self.send_response(404)
            self.end_headers()

def iniciar_servidor():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), IazJudHandler) as httpd:
        print("=" * 60)
        print(f" IAZ Jud - Servidor Web & API Ativo")
        print(f" Painel Web: http://localhost:{PORT}")
        print(f" API Proxy:  http://localhost:{PORT}/api/consultar")
        print(f" Supabase:   {SUPABASE_URL}")
        print("=" * 60)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")

if __name__ == "__main__":
    iniciar_servidor()
