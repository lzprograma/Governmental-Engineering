"""Adaptadores HTTP para protocolos públicos de inferência de LLM.

Não existe um único formato universal de API. Este módulo implementa protocolos
comuns e deixa o catálogo extensível por `api_format`.
"""
from __future__ import annotations

import json
import socket
import ipaddress
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit


class ProviderError(RuntimeError):
    pass


@dataclass
class Completion:
    text: str
    provider_request_id: str | None = None
    usage: dict[str, Any] | None = None


def _validate_url(url: str, allow_private_network: bool = False) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("URL de API inválida: use https:// (ou http:// somente para serviço local).")
    host = parsed.hostname.lower()
    if parsed.scheme == "http" and host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("HTTP sem TLS só é permitido para serviços locais. Use HTTPS para provedores externos.")
    if host in {"localhost", "127.0.0.1", "::1"}:
        return
    try:
        addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise ProviderError(f"Não foi possível resolver o host da API: {host}") from exc
    for address in addresses:
        if address.is_link_local or address.is_loopback or address.is_unspecified or address.is_multicast:
            raise ValueError("O endpoint aponta para endereço especial/local não permitido.")
        if not address.is_global and not allow_private_network:
            raise ValueError("O endpoint está em rede privada. Marque a autorização de rede privada somente se este endpoint for seu e confiável.")



def _append_path(base_url: str, suffix: str) -> str:
    parsed = urlsplit(base_url)
    clean_path = parsed.path.rstrip("/")
    if clean_path.endswith(suffix):
        return base_url
    return urlunsplit((parsed.scheme, parsed.netloc, clean_path + suffix, parsed.query, parsed.fragment))


def _headers(connection: dict[str, Any]) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = connection.get("api_key")
    mode = connection.get("auth_mode", "bearer")
    if key:
        if mode == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        elif mode == "x-api-key":
            headers[connection.get("api_key_header") or "x-api-key"] = key
        elif mode == "x-goog-api-key":
            headers["x-goog-api-key"] = key
        elif mode == "query-key":
            pass
        elif mode == "none":
            pass
        else:
            raise ValueError("Modo de autenticação não suportado.")
    for k, v in (connection.get("extra_headers") or {}).items():
        if not isinstance(k, str) or not isinstance(v, str) or "\n" in k + v:
            raise ValueError("Cabeçalho adicional inválido.")
        if k.lower() not in {"host", "content-length", "connection", "transfer-encoding"}:
            headers[k] = v
    return headers


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _safe_open(request: urllib.request.Request, timeout: float):
    # Evita que um endpoint cadastrado redirecione silenciosamente a chamada para outro host.
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(request, timeout=timeout)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float,
               query_key: str | None = None, allow_private_network: bool = False) -> tuple[dict[str, Any], dict[str, str]]:
    _validate_url(url, allow_private_network=allow_private_network)
    if query_key:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={urllib.parse.quote(query_key)}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with _safe_open(request, timeout=timeout) as response:
            raw = response.read(12 * 1024 * 1024)
            parsed = json.loads(raw.decode("utf-8"))
            return parsed, dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        body = exc.read(8000).decode("utf-8", errors="replace")
        if query_key:
            body = body.replace(query_key, "[REDACTED]")
        raise ProviderError(f"HTTP {exc.code} do provedor: {body[:1500]}") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.timeout):
            raise ProviderError("Tempo limite excedido ao conectar ao provedor.") from exc
        raise ProviderError(f"Falha de conexão com o provedor: {reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ProviderError("Tempo limite excedido ao conectar ao provedor.") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("O provedor retornou conteúdo que não é JSON válido.") from exc


def _messages(history: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in history if m["role"] in {"user", "assistant"}]



def list_models(connection: dict[str, Any]) -> list[str]:
    """Lista modelos nos endpoints que publicam catálogo padrão.

    Para APIs customizadas sem endpoint de catálogo, o operador informa o model ID manualmente.
    """
    fmt = connection["api_format"]
    base = connection["base_url"].rstrip("/")
    timeout = float(connection.get("timeout_seconds", 45))
    key = connection.get("api_key")
    headers = _headers(connection)
    query_key = None
    if fmt in {"openai_chat", "openai_responses", "openai_compatible"}:
        url = _append_path(base, "/models")
    elif fmt == "anthropic_messages":
        parsed_base = urlsplit(base)
        if parsed_base.path.rstrip("/").endswith("/v1/models"):
            url = base
        elif parsed_base.path.rstrip("/").endswith("/v1"):
            url = _append_path(base, "/models")
        else:
            url = _append_path(base, "/v1/models")
        headers.pop("Authorization", None)
        if key:
            headers[connection.get("api_key_header") or "x-api-key"] = key
        headers["anthropic-version"] = connection.get("anthropic_version", "2023-06-01")
    elif fmt == "gemini_generate_content":
        url = _append_path(base, "/models")
        headers.pop("Authorization", None)
        if connection.get("auth_mode") == "query-key":
            query_key = key
        elif key:
            headers["x-goog-api-key"] = key
    else:
        raise ProviderError(f"Formato sem listagem automática de modelos: {fmt}")
    _validate_url(url, allow_private_network=bool(connection.get("allow_private_network", False)))
    if query_key:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={urllib.parse.quote(query_key)}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with _safe_open(request, timeout=timeout) as response:
            data = json.loads(response.read(8 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read(5000).decode("utf-8", errors="replace")
        if query_key:
            body = body.replace(query_key, "[REDACTED]")
        raise ProviderError(f"HTTP {exc.code} ao listar modelos: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Falha ao listar modelos: {exc.reason}") from exc
    if fmt == "gemini_generate_content":
        models = [str(item.get("name", "")).removeprefix("models/") for item in data.get("models", [])]
    else:
        models = [str(item.get("id", "")) for item in data.get("data", [])]
    return sorted({model for model in models if model})


def complete(connection: dict[str, Any], *, model: str, system_prompt: str,
             history: list[dict[str, str]], temperature: float, max_tokens: int) -> Completion:
    fmt = connection["api_format"]
    base = connection["base_url"].rstrip("/")
    timeout = float(connection.get("timeout_seconds", 45))
    headers = _headers(connection)
    msgs = _messages(history)
    key = connection.get("api_key")

    if fmt in {"openai_chat", "openai_compatible"}:
        url = _append_path(base, "/chat/completions")
        payload = {"model": model, "messages": ([{"role": "system", "content": system_prompt}] if system_prompt else []) + msgs,
                   "temperature": temperature, "max_tokens": max_tokens}
        data, response_headers = _post_json(url, payload, headers, timeout, allow_private_network=bool(connection.get("allow_private_network", False)))
        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
            return Completion(str(content or ""), response_headers.get("x-request-id") or data.get("id"), data.get("usage"))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Resposta fora do formato esperado de OpenAI Chat Completions.") from exc

    if fmt == "openai_responses":
        url = _append_path(base, "/responses")
        input_items = []
        for message in msgs:
            input_items.append({"role": message["role"], "content": message["content"]})
        payload = {"model": model, "input": input_items, "max_output_tokens": max_tokens,
                   "temperature": temperature}
        if system_prompt:
            payload["instructions"] = system_prompt
        data, response_headers = _post_json(url, payload, headers, timeout, allow_private_network=bool(connection.get("allow_private_network", False)))
        output_text = data.get("output_text")
        if not output_text:
            chunks = []
            for item in data.get("output", []):
                for part in item.get("content", []):
                    if part.get("type") in {"output_text", "text"}:
                        chunks.append(part.get("text", ""))
            output_text = "\n".join(chunks)
        if not output_text:
            raise ProviderError("Resposta sem texto no formato OpenAI Responses.")
        return Completion(output_text, response_headers.get("x-request-id") or data.get("id"), data.get("usage"))

    if fmt == "anthropic_messages":
        parsed_base = urlsplit(base)
        if parsed_base.path.rstrip("/").endswith("/v1/messages"):
            url = base
        elif parsed_base.path.rstrip("/").endswith("/v1"):
            url = _append_path(base, "/messages")
        else:
            url = _append_path(base, "/v1/messages")
        anthropic_headers = dict(headers)
        anthropic_headers.pop("Authorization", None)
        if key:
            anthropic_headers[connection.get("api_key_header") or "x-api-key"] = key
        anthropic_headers["anthropic-version"] = connection.get("anthropic_version", "2023-06-01")
        payload = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        if system_prompt:
            payload["system"] = system_prompt
        data, response_headers = _post_json(url, payload, anthropic_headers, timeout, allow_private_network=bool(connection.get("allow_private_network", False)))
        text_parts = [part.get("text", "") for part in data.get("content", []) if part.get("type") == "text"]
        if not text_parts:
            raise ProviderError("Resposta sem bloco de texto no formato Anthropic Messages.")
        return Completion("\n".join(text_parts), response_headers.get("request-id") or data.get("id"), data.get("usage"))

    if fmt == "gemini_generate_content":
        model_path = urllib.parse.quote(model, safe="-_.")
        parsed_base = urlsplit(base)
        if parsed_base.path.endswith(":generateContent"):
            url = base
        elif "/models/" in parsed_base.path:
            url = _append_path(base, ":generateContent")
        else:
            url = _append_path(base, f"/models/{model_path}:generateContent")
        gemini_headers = dict(headers)
        gemini_headers.pop("Authorization", None)
        if key and connection.get("auth_mode", "x-goog-api-key") != "query-key":
            gemini_headers["x-goog-api-key"] = key
        contents = []
        for msg in msgs:
            contents.append({"role": "model" if msg["role"] == "assistant" else "user",
                             "parts": [{"text": msg["content"]}]})
        payload: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": temperature,
                                                                              "maxOutputTokens": max_tokens}}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        data, response_headers = _post_json(url, payload, gemini_headers, timeout,
                                             query_key=key if connection.get("auth_mode") == "query-key" else None,
                                             allow_private_network=bool(connection.get("allow_private_network", False)))
        candidates = data.get("candidates", [])
        parts = [part.get("text", "") for candidate in candidates
                 for part in candidate.get("content", {}).get("parts", []) if part.get("text")]
        if not parts:
            feedback = data.get("promptFeedback", {}).get("blockReason")
            raise ProviderError(f"Gemini não retornou texto. Motivo: {feedback or 'resposta vazia'}.")
        return Completion("\n".join(parts), response_headers.get("x-goog-request-id"), data.get("usageMetadata"))

    raise ProviderError(f"Formato de API não suportado: {fmt}")
