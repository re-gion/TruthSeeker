"""Domain provenance helpers backed by WhoisXML APIs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WHOISXML_WHOIS_URL = "https://www.whoisxmlapi.com/whoisserver/WhoisService"
WHOISXML_DNS_HISTORY_URL = "https://dns-history.whoisxmlapi.com/api/v1"
WHOISXML_IP_GEOLOCATION_URL = "https://ip-geolocation.whoisxmlapi.com/api/v1"

SECOND_LEVEL_SUFFIXES = {"com.br", "net.br", "org.br", "co.uk", "com.cn", "net.cn", "org.cn"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_registered_domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or value or "").strip(".").lower()
    if not host:
        return ""
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    suffix2 = ".".join(parts[-2:])
    if suffix2 in SECOND_LEVEL_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _as_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_whois(payload: dict[str, Any]) -> dict[str, Any]:
    record = _as_record(payload.get("WhoisRecord") or payload.get("whoisRecord") or payload)
    registry = _as_record(record.get("registryData"))
    registrant = _as_record(record.get("registrant"))
    registry_registrant = _as_record(registry.get("registrant"))
    contact = record.get("contactEmail") or registry.get("contactEmail")
    name_servers = record.get("nameServers") or registry.get("nameServers") or record.get("nameServer") or []
    if isinstance(name_servers, dict):
        name_servers = name_servers.get("hostNames") or name_servers.get("rawText") or []
    return {
        "created_date": record.get("createdDate") or record.get("createdDateNormalized") or registry.get("createdDate") or registry.get("createdDateNormalized"),
        "updated_date": record.get("updatedDate") or record.get("updatedDateNormalized") or registry.get("updatedDate") or registry.get("updatedDateNormalized"),
        "expires_date": record.get("expiresDate") or record.get("expiresDateNormalized") or registry.get("expiresDate") or registry.get("expiresDateNormalized"),
        "registrar": record.get("registrarName") or record.get("registrarIANAID") or registry.get("registrarName") or registry.get("registrarIANAID"),
        "registrant_organization": registrant.get("organization") or registry_registrant.get("organization"),
        "registrant_country": registrant.get("country") or registry_registrant.get("country"),
        "name_servers": name_servers,
        "contact_email": contact if isinstance(contact, str) else None,
        "ips": record.get("ips") or registry.get("ips") or [],
    }


def _normalize_dns_history(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("records") or payload.get("result") or payload.get("dnsRecords") or []
    if isinstance(rows, dict):
        rows = rows.get("records") or []
    result: list[dict[str, Any]] = []
    for item in rows[:20] if isinstance(rows, list) else []:
        if not isinstance(item, dict):
            continue
        ips = item.get("ips")
        if isinstance(ips, list):
            for ip_item in ips:
                ip_value = ip_item.get("ip") if isinstance(ip_item, dict) else ip_item
                if ip_value:
                    result.append({
                        "type": "A",
                        "value": ip_value,
                        "first_seen": item.get("date") or item.get("firstSeen") or item.get("first_seen"),
                        "last_seen": item.get("lastSeen") or item.get("last_seen"),
                    })
            continue
        result.append({
            "type": item.get("rrtype") or item.get("type") or item.get("recordType"),
            "value": item.get("value") or item.get("address") or item.get("data"),
            "first_seen": item.get("firstSeen") or item.get("first_seen") or item.get("date"),
            "last_seen": item.get("lastSeen") or item.get("last_seen"),
        })
    return result


def _normalize_ip_geolocation(payload: dict[str, Any]) -> dict[str, Any]:
    location = _as_record(payload.get("location"))
    asn = _as_record(payload.get("as"))
    return {
        "ip": payload.get("ip"),
        "country": location.get("country"),
        "region": location.get("region"),
        "city": location.get("city"),
        "isp": payload.get("isp"),
        "asn": asn.get("asn"),
        "as_name": asn.get("name"),
        "as_route": asn.get("route"),
    }


def _extract_ips(whois: dict[str, Any], dns_history: list[dict[str, Any]]) -> list[str]:
    ips: list[str] = []
    raw_whois_ips = whois.get("ips") or []
    if isinstance(raw_whois_ips, str):
        raw_whois_ips = [raw_whois_ips]
    for value in raw_whois_ips if isinstance(raw_whois_ips, list) else []:
        if value:
            ips.append(str(value))
    for row in dns_history:
        if str(row.get("type") or "").upper() in {"A", "AAAA"} and row.get("value"):
            ips.append(str(row["value"]))
    return list(dict.fromkeys(ips))[:5]


async def analyze_domain_provenance(value: str) -> dict[str, Any]:
    domain = extract_registered_domain(value)
    started_at = _now()
    if not settings.DOMAIN_PROVENANCE_ENABLED:
        return {
            "tool": "whoisxml_domain_provenance",
            "target": value,
            "domain": domain,
            "status": "disabled",
            "degraded": True,
            "summary": "域名溯源未启用",
            "whois": {},
            "dns_history": [],
            "ip_geolocation": [],
            "started_at": started_at,
            "completed_at": _now(),
        }
    if not domain:
        return {
            "tool": "whoisxml_domain_provenance",
            "target": value,
            "domain": "",
            "status": "degraded",
            "degraded": True,
            "summary": "未能抽取可查询域名",
            "whois": {},
            "dns_history": [],
            "ip_geolocation": [],
            "started_at": started_at,
            "completed_at": _now(),
        }
    if not settings.WHOISXML_API_KEY:
        return {
            "tool": "whoisxml_domain_provenance",
            "target": value,
            "domain": domain,
            "status": "no_key",
            "degraded": True,
            "summary": "未配置 WhoisXML API Key，域名注册与 DNS 历史不可用",
            "whois": {},
            "dns_history": [],
            "ip_geolocation": [],
            "started_at": started_at,
            "completed_at": _now(),
        }

    whois: dict[str, Any] = {}
    dns_history: list[dict[str, Any]] = []
    ip_geolocation: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=settings.WHOISXML_TIMEOUT_SECONDS) as client:
        try:
            whois_resp = await client.get(
                WHOISXML_WHOIS_URL,
                params={"apiKey": settings.WHOISXML_API_KEY, "domainName": domain, "outputFormat": "JSON"},
            )
            whois_resp.raise_for_status()
            whois = _normalize_whois(whois_resp.json())
        except Exception as exc:
            logger.warning("WhoisXML WHOIS degraded for %s: %s", domain, exc)
            errors.append(f"whois:{type(exc).__name__}: {exc}")

        try:
            dns_resp = await client.post(
                WHOISXML_DNS_HISTORY_URL,
                json={
                    "apiKey": settings.WHOISXML_API_KEY,
                    "searchType": "forward",
                    "recordType": "a",
                    "domainName": domain,
                    "outputFormat": "JSON",
                    "limit": 20,
                },
            )
            dns_resp.raise_for_status()
            dns_history = _normalize_dns_history(dns_resp.json())
        except Exception as exc:
            logger.warning("WhoisXML DNS history degraded for %s: %s", domain, exc)
            errors.append(f"dns_history:{type(exc).__name__}: {exc}")

        for ip in _extract_ips(whois, dns_history):
            try:
                geo_resp = await client.get(
                    WHOISXML_IP_GEOLOCATION_URL,
                    params={"apiKey": settings.WHOISXML_API_KEY, "ipAddress": ip, "outputFormat": "JSON"},
                )
                geo_resp.raise_for_status()
                geo = _normalize_ip_geolocation(geo_resp.json())
                if geo.get("ip"):
                    ip_geolocation.append(geo)
            except Exception as exc:
                logger.warning("WhoisXML IP geolocation degraded for %s: %s", ip, exc)
                errors.append(f"ip_geolocation:{ip}:{type(exc).__name__}: {exc}")

    has_data = bool(whois or dns_history or ip_geolocation)
    if has_data:
        status = "partial" if errors else "success"
        created = whois.get("created_date") or "未知注册时间"
        registrar = whois.get("registrar") or "未知注册商"
        return {
            "tool": "whoisxml_domain_provenance",
            "target": value,
            "domain": domain,
            "status": status,
            "degraded": bool(errors),
            "summary": f"WhoisXML 查询{('部分' if errors else '')}完成: {domain}，注册时间={created}，注册商={registrar}，DNS历史 {len(dns_history)} 条，IP归属 {len(ip_geolocation)} 条",
            "whois": whois,
            "dns_history": dns_history,
            "ip_geolocation": ip_geolocation,
            "errors": errors,
            "started_at": started_at,
            "completed_at": _now(),
        }

    logger.warning("WhoisXML domain provenance degraded for %s: %s", domain, "; ".join(errors))
    error_text = "; ".join(errors) or "unknown"
    return {
        "tool": "whoisxml_domain_provenance",
        "target": value,
        "domain": domain,
        "status": "degraded",
        "degraded": True,
        "summary": "WhoisXML 域名溯源不可用",
        "error": error_text,
        "whois": {},
        "dns_history": [],
        "ip_geolocation": [],
        "started_at": started_at,
        "completed_at": _now(),
    }
