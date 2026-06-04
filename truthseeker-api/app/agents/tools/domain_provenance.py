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
WHOISXML_DNS_LOOKUP_URL = "https://www.whoisxmlapi.com/whoisserver/DNSService"
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


def extract_hostname(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or value or "").strip(".").lower()
    return host


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


def _normalize_dns_records(payload: dict[str, Any], *, source: str, queried_name: str) -> list[dict[str, Any]]:
    dns_data = _as_record(payload.get("DNSData") or payload.get("dnsData"))
    rows = dns_data.get("dnsRecords") or payload.get("dnsRecords") or payload.get("records") or []
    if isinstance(rows, dict):
        rows = rows.get("records") or []
    result: list[dict[str, Any]] = []
    for item in rows[:20] if isinstance(rows, list) else []:
        if not isinstance(item, dict):
            continue
        record_type = str(item.get("dnsType") or item.get("rrtype") or item.get("type") or item.get("recordType") or "").upper()
        value = (
            item.get("address")
            or item.get("target")
            or item.get("alias")
            or item.get("canonicalName")
            or item.get("value")
            or item.get("data")
        )
        if not record_type or value is None:
            continue
        result.append(
            {
                "type": record_type,
                "name": item.get("name") or queried_name,
                "value": str(value).strip(".").lower() if record_type == "CNAME" else str(value),
                "ttl": item.get("ttl"),
                "source": source,
                "queried_name": queried_name,
            }
        )
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


def _format_component_error(component: str, exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 403:
            return f"{component}:http_403_access_restricted"
        if status_code == 401:
            return f"{component}:http_401_invalid_api_key"
        return f"{component}:http_{status_code}"
    return f"{component}:{type(exc).__name__}: {exc}"


def _summarize_partial_limitations(errors: list[str], dns_lookup: list[dict[str, Any]], ip_geolocation: list[dict[str, Any]]) -> str:
    notes: list[str] = []
    if any(error.startswith("dns_lookup:http_403") for error in errors):
        notes.append("DNS Lookup 接口访问受限，请检查 WhoisXML DNS Lookup 权限或额度")
    elif any(error.startswith("dns_lookup:") for error in errors):
        notes.append("DNS Lookup 未返回完整结果")
    if not _extract_ips_from_dns_lookup(dns_lookup) and not ip_geolocation:
        notes.append("未获得可用于 IP 归属查询的当前 A/AAAA 记录")
    elif any(error.startswith("ip_geolocation:") and "http_403" in error for error in errors):
        notes.append("IP Geolocation 接口访问受限，请检查该产品权限或额度")
    elif any(error.startswith("ip_geolocation:") for error in errors):
        notes.append("部分 IP 归属信息未返回")
    return "；".join(dict.fromkeys(notes))


def _extract_ips_from_dns_lookup(dns_lookup: list[dict[str, Any]]) -> list[str]:
    ips: list[str] = []
    for row in dns_lookup:
        if str(row.get("type") or "").upper() in {"A", "AAAA"} and row.get("value"):
            ips.append(str(row["value"]))
    return list(dict.fromkeys(ips))[:5]


async def _dns_lookup(client: httpx.AsyncClient, name: str, record_type: str, source: str) -> list[dict[str, Any]]:
    resp = await client.get(
        WHOISXML_DNS_LOOKUP_URL,
        params={
            "apiKey": settings.WHOISXML_API_KEY,
            "domainName": name,
            "type": record_type,
            "outputFormat": "JSON",
        },
    )
    resp.raise_for_status()
    return _normalize_dns_records(resp.json(), source=source, queried_name=name)


async def _resolve_current_dns(client: httpx.AsyncClient, *, hostname: str, registered_domain: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    queried_address_names: set[str] = set()

    async def query_addresses(name: str, source: str) -> list[dict[str, Any]]:
        if name in queried_address_names:
            return []
        queried_address_names.add(name)
        return await _dns_lookup(client, name, "A,AAAA", source)

    current_name = hostname or registered_domain
    address_records = await query_addresses(current_name, "hostname")
    records.extend(address_records)
    if _extract_ips_from_dns_lookup(address_records):
        return records

    for _ in range(3):
        cname_records = await _dns_lookup(client, current_name, "CNAME", "hostname" if current_name == hostname else "cname")
        if not cname_records:
            break
        records.extend(cname_records)
        cname_targets = [row["value"] for row in cname_records if row.get("type") == "CNAME" and row.get("value")]
        if not cname_targets:
            break
        current_name = str(cname_targets[0]).strip(".").lower()
        address_records = await query_addresses(current_name, "cname")
        records.extend(address_records)
        if _extract_ips_from_dns_lookup(address_records):
            return records
        break

    if registered_domain and registered_domain not in queried_address_names:
        records.extend(await query_addresses(registered_domain, "registered_domain"))
    return records


async def analyze_domain_provenance(value: str) -> dict[str, Any]:
    domain = extract_registered_domain(value)
    hostname = extract_hostname(value)
    started_at = _now()
    if not settings.DOMAIN_PROVENANCE_ENABLED:
        return {
            "tool": "whoisxml_domain_provenance",
            "target": value,
            "domain": domain,
            "hostname": hostname,
            "status": "disabled",
            "degraded": True,
            "summary": "域名溯源未启用",
            "whois": {},
            "dns_lookup": [],
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
            "hostname": hostname,
            "status": "degraded",
            "degraded": True,
            "summary": "未能抽取可查询域名",
            "whois": {},
            "dns_lookup": [],
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
            "hostname": hostname,
            "status": "no_key",
            "degraded": True,
            "summary": "未配置 WhoisXML API Key，域名注册、当前 DNS 与 IP 地理位置不可用",
            "whois": {},
            "dns_lookup": [],
            "dns_history": [],
            "ip_geolocation": [],
            "started_at": started_at,
            "completed_at": _now(),
        }

    whois: dict[str, Any] = {}
    dns_lookup: list[dict[str, Any]] = []
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
            errors.append(_format_component_error("whois", exc))

        try:
            dns_lookup = await _resolve_current_dns(client, hostname=hostname, registered_domain=domain)
        except Exception as exc:
            logger.warning("WhoisXML DNS lookup degraded for %s: %s", hostname or domain, exc)
            errors.append(_format_component_error("dns_lookup", exc))

        for ip in _extract_ips_from_dns_lookup(dns_lookup):
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
                errors.append(_format_component_error(f"ip_geolocation:{ip}", exc))

    has_data = bool(whois or dns_lookup or ip_geolocation)
    if has_data:
        status = "partial" if errors else "success"
        created = whois.get("created_date") or "未知注册时间"
        registrar = whois.get("registrar") or "未知注册商"
        limitation_summary = _summarize_partial_limitations(errors, dns_lookup, ip_geolocation) if errors else ""
        status_text = "部分完成，WHOIS 主查询成功" if errors and whois else ("部分完成" if errors else "完成")
        summary = f"WhoisXML 查询{status_text}: {domain}，注册时间={created}，注册商={registrar}，当前DNS {len(dns_lookup)} 条，IP归属 {len(ip_geolocation)} 条"
        if limitation_summary:
            summary += f"；{limitation_summary}"
        return {
            "tool": "whoisxml_domain_provenance",
            "target": value,
            "domain": domain,
            "hostname": hostname,
            "status": status,
            "degraded": bool(errors),
            "summary": summary,
            "whois": whois,
            "dns_lookup": dns_lookup,
            "dns_history": [],
            "ip_geolocation": ip_geolocation,
            "errors": errors,
            "partial_success": bool(errors),
            "limitation_summary": limitation_summary,
            "started_at": started_at,
            "completed_at": _now(),
        }

    logger.warning("WhoisXML domain provenance degraded for %s: %s", domain, "; ".join(errors))
    error_text = "; ".join(errors) or "unknown"
    return {
        "tool": "whoisxml_domain_provenance",
        "target": value,
        "domain": domain,
        "hostname": hostname,
        "status": "degraded",
        "degraded": True,
        "summary": "WhoisXML 域名溯源不可用",
        "error": error_text,
        "whois": {},
        "dns_lookup": [],
        "dns_history": [],
        "ip_geolocation": [],
        "started_at": started_at,
        "completed_at": _now(),
    }
