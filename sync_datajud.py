#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IAZ Jud - Módulo de Sincronização com DataJud e Supabase
Permite sincronizar os processos cadastrados no Supabase diretamente com a API do DataJud (CNJ),
atualizando data da última verificação, última movimentação e inserindo o histórico detalhado.
"""

import sys
import os
import re
import json
import ssl
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# --- Configurações Supabase e DataJud ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://kslmyvlewsmjnrhwklfd.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_WjgE2b2iKdZrRopbQieW3A_Cr9R9pGB")
DATAJUD_API_KEY = os.environ.get("DATAJUD_API_KEY", "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==")

# Mapeamento do número CNJ para Tribunal (quando não informado)
TRIBUNAIS_ESTADUAIS = {
    "01": "tjac", "02": "tjal", "03": "tjap", "04": "tjam", "05": "tjba",
    "06": "tjce", "07": "tjdft", "08": "tjes", "09": "tjgo", "10": "tjma",
    "11": "tjmt", "12": "tjms", "13": "tjmg", "14": "tjpa", "15": "tjpb",
    "16": "tjpr", "17": "tjpe", "18": "tjpi", "19": "tjrj", "20": "tjrn",
    "21": "tjrs", "22": "tjro", "23": "tjrr", "24": "tjsc", "25": "tjse",
    "26": "tjsp", "27": "tfto"
}

def identificar_tribunal_cnj(numero_processo, tribunal_hint=""):
    """
    Identifica o alias do tribunal no DataJud a partir da dica ou do número CNJ.
    Ex: 00003004120255070009 -> trt7 (J=5, TR=07)
        01074497920178060001 -> tjce (J=8, TR=06)
        08186685120234058100 -> trf5 (J=4, TR=05)
    """
    if tribunal_hint:
        t_clean = tribunal_hint.lower().replace("-", "").strip()
        if t_clean in ["tjce", "tjsp", "trt7", "trf5", "tjrj", "tjmg", "trt2", "trf1", "trf2", "trf3", "trf4", "trf6", "stj", "tst"]:
            return t_clean

    digitos = re.sub(r"\D", "", str(numero_processo))
    if len(digitos) >= 20:
        # Padrão CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
        # Índices:
        # NNNNNNN (0..6), DD (7..8), AAAA (9..12), J (13), TR (14..15), OOOO (16..19)
        j = digitos[13]
        tr = digitos[14:16]

        if j == "8":  # Justiça Estadual
            return TRIBUNAIS_ESTADUAIS.get(tr, f"tj{tr}")
        elif j == "5":  # Justiça do Trabalho
            regiao = int(tr)
            return f"trt{regiao}"
        elif j == "4":  # Justiça Federal
            regiao = int(tr)
            return f"trf{regiao}"
        elif j == "3":  # STJ
            return "stj"
        elif j == "1":  # STF
            return "stf"

    if tribunal_hint:
        return tribunal_hint.lower().strip()
    return "tjce"


def supabase_request(endpoint, method="GET", data=None, extra_headers=None):
    """Executa requisições HTTP na API REST do Supabase com fallback transparente."""
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    if extra_headers:
        headers.update(extra_headers)

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    ctx = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else []
    except urllib.error.HTTPError as e:
        # Fallback de transição: se a tabela ju_* retornar 404 (ainda não migrada), tenta tabela legada
        if e.code == 404 and endpoint.startswith("ju_"):
            fallback_endpoint = endpoint[3:]
            try:
                fallback_url = f"{SUPABASE_URL}/rest/v1/{fallback_endpoint}"
                fallback_req = urllib.request.Request(fallback_url, data=body_bytes, headers=headers, method=method)
                with urllib.request.urlopen(fallback_req, context=ctx, timeout=30) as resp:
                    content = resp.read().decode("utf-8")
                    return json.loads(content) if content else []
            except Exception:
                pass

        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"Erro Supabase [{e.code}]: {err_msg}")


def consultar_datajud(numero_processo, tribunal_hint=""):
    """
    Consulta o processo na API pública oficial do DataJud (CNJ).
    Retorna o dicionário com dados do processo e movimentos normalizados.
    """
    num_limpo = re.sub(r"\D", "", str(numero_processo))
    tribunal = identificar_tribunal_cnj(num_limpo, tribunal_hint)
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"

    payload = json.dumps({"query": {"match": {"numeroProcesso": num_limpo}}}).encode("utf-8")
    headers = {
        "Authorization": f"APIKey {DATAJUD_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (IAZ-Jud Process Monitor)"
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    ctx = ssl._create_unverified_context()

    max_tentativas = 3
    espera = 2

    for tentativa in range(1, max_tentativas + 1):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                hits = data.get("hits", {}).get("hits", [])
                if not hits:
                    return {"success": False, "mensagem": f"Nenhum registro encontrado no DataJud ({tribunal.upper()})"}

                # O mesmo processo pode ter vários graus (G1, G2...): consolida todos os movimentos
                source = hits[0].get("_source", {})
                vistos = set()
                movimentos = []
                for h in hits:
                    for m in h.get("_source", {}).get("movimentos", []):
                        chave = (m.get("dataHora"), m.get("nome"))
                        if chave not in vistos:
                            vistos.add(chave)
                            movimentos.append(m)
                movimentos.sort(key=lambda m: m.get("dataHora") or "", reverse=True)

                ultima_data = None
                if movimentos:
                    ultima_data = movimentos[0].get("dataHora")
                if not ultima_data:
                    ultima_data = source.get("dataHoraUltimaAtualizacao")

                return {
                    "success": True,
                    "tribunal": tribunal.upper(),
                    "numeroProcesso": source.get("numeroProcesso", num_limpo),
                    "classe": source.get("classe", {}).get("nome", ""),
                    "grau": source.get("grau", ""),
                    "ultimaData": ultima_data,
                    "movimentos": [
                        {
                            "dataHora": m.get("dataHora"),
                            "nome": m.get("nome", "Movimentação registrada"),
                            "codigo": m.get("codigo")
                        }
                        for m in movimentos
                    ]
                }
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < max_tentativas:
                time.sleep(espera)
                espera *= 2
                continue
            err_msg = e.read().decode("utf-8") if e.fp else str(e)
            return {"success": False, "mensagem": f"Erro HTTP DataJud [{e.code}]: {err_msg}"}
        except Exception as e:
            if tentativa < max_tentativas and "timed out" in str(e).lower():
                time.sleep(espera)
                espera *= 2
                continue
            return {"success": False, "mensagem": f"Falha na conexão com DataJud: {str(e)}"}


def sincronizar_processo(processo_obj, verbose=True):
    """
    Sincroniza um processo específico:
    1. Consulta DataJud
    2. Atualiza ultima_verificacao e ultima_data no Supabase
    3. Grava novos movimentos no Supabase
    """
    num_processo = processo_obj.get("processo")
    tribunal = processo_obj.get("tribunal", "")

    if verbose:
        print(f"\n[+] Verificando: {num_processo} ({tribunal or 'Auto'})...")

    resultado = consultar_datajud(num_processo, tribunal)
    agora_iso = datetime.now(timezone.utc).isoformat()

    if not resultado.get("success"):
        if verbose:
            print(f"    [-] Alerta: {resultado.get('mensagem')}")
        # Mesmo se não achou no DataJud, marcamos que foi verificado para não ficar indefinido
        try:
            supabase_request(
                f"ju_processos?processo=eq.{num_processo}",
                method="PATCH",
                data={"ultima_verificacao": agora_iso}
            )
        except Exception as e:
            if verbose:
                print(f"    [!] Erro ao atualizar status de verificação no Supabase: {e}")
        return False

    movimentos = resultado.get("movimentos", [])
    ultima_mov_data = resultado.get("ultimaData")
    tribunal_resolvido = resultado.get("tribunal", tribunal)

    patch_data = {
        "ultima_verificacao": agora_iso
    }
    if ultima_mov_data:
        patch_data["ultima_data"] = ultima_mov_data
    if tribunal_resolvido and not processo_obj.get("tribunal"):
        patch_data["tribunal"] = tribunal_resolvido

    # Atualiza na tabela ju_processos
    try:
        supabase_request(
            f"ju_processos?processo=eq.{num_processo}",
            method="PATCH",
            data=patch_data
        )
        if verbose:
            print(f"    [OK] Tabela 'ju_processos' atualizada. Última verificação: {agora_iso}")
    except Exception as e:
        print(f"    [!] Erro ao atualizar processo no Supabase: {e}")
        return False

    # Insere as movimentações em batch para performance instantânea
    inseridos = 0
    if movimentos:
        lote = []
        for m in movimentos:
            dt = m.get("dataHora")
            nome = m.get("nome")
            if dt and nome:
                lote.append({
                    "processo": num_processo,
                    "data_movimentacao": dt,
                    "atualizacao": nome
                })

        # Envia em blocos de 50
        tamanho_bloco = 50
        for i in range(0, len(lote), tamanho_bloco):
            bloco = lote[i:i + tamanho_bloco]
            try:
                supabase_request(
                    "ju_movimentacoes",
                    method="POST",
                    data=bloco,
                    extra_headers={"Prefer": "resolution=merge-duplicates"}
                )
                inseridos += len(bloco)
            except Exception as e:
                # Se falhar o lote, tenta individual como fallback
                for item in bloco:
                    try:
                        supabase_request(
                            "ju_movimentacoes",
                            method="POST",
                            data=item,
                            extra_headers={"Prefer": "resolution=merge-duplicates"}
                        )
                        inseridos += 1
                    except Exception:
                        pass

    if verbose:
        print(f"    [OK] Total de movimentações sincronizadas: {inseridos} de {len(movimentos)}")
    return True


def sincronizar_todos(verbose=True, apenas_pendentes=False):
    """Varre todos os processos do Supabase e sincroniza um a um."""
    print("=" * 65)
    print(" IAZ JUD - Sincronização Direta com Supabase e DataJud (CNJ)")
    print("=" * 65)

    try:
        endpoint = "ju_processos?select=*"
        if apenas_pendentes:
            endpoint += "&ultima_verificacao=is.null"
        processos = supabase_request(endpoint)
    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha ao carregar processos do Supabase: {e}")
        return

    total = len(processos)
    print(f"Total de processos para sincronizar: {total}")

    sucessos = 0
    falhas = 0

    for i, p in enumerate(processos, 1):
        num = p.get("processo")
        print(f"\n({i}/{total}) Processo {num}")
        ok = sincronizar_processo(p, verbose=verbose)
        if ok:
            sucessos += 1
        else:
            falhas += 1
        # Pausa leve para respeitar os limites de requisição do DataJud
        time.sleep(0.5)

    print("\n" + "=" * 65)
    print(f" Resumo da Sincronização:")
    print(f" Sucessos: {sucessos} | Não localizados/Erros: {falhas} | Total: {total}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="IAZ Jud - Sincronizador de Processos Judiciais")
    parser.add_argument("--processo", help="Número de um processo específico para sincronizar")
    parser.add_argument("--tribunal", help="Tribunal do processo (opcional, ex: TJCE, TRT7)")
    parser.add_argument("--pendentes", action="store_true", help="Sincronizar apenas os que nunca foram verificados")
    parser.add_argument("--loop", type=int, default=0, help="Executar em loop a cada N segundos")

    args = parser.parse_args()

    if args.processo:
        proc_obj = {"processo": args.processo, "tribunal": args.tribunal or ""}
        sincronizar_processo(proc_obj, verbose=True)
    elif args.loop > 0:
        print(f"Modo daemon ativado. Intervalo: {args.loop}s.")
        while True:
            sincronizar_todos(verbose=True, apenas_pendentes=args.pendentes)
            print(f"\nAguardando {args.loop} segundos para o próximo ciclo...")
            time.sleep(args.loop)
    else:
        sincronizar_todos(verbose=True, apenas_pendentes=args.pendentes)


if __name__ == "__main__":
    main()
