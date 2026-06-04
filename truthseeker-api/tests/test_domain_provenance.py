import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeWhoisXmlClient:
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        params = params or {}
        self.calls.append(("GET", url, dict(params)))

        if url.endswith("/WhoisService"):
            return FakeResponse(
                {
                    "WhoisRecord": {
                        "createdDate": "2026-06-01T00:00:00Z",
                        "registrarName": "Example Registrar",
                    }
                }
            )

        if url.endswith("/DNSService"):
            domain_name = params.get("domainName")
            record_type = params.get("type")
            if domain_name == "halifax.co.uk.account.security.update.moroba.com.br" and record_type == "A,AAAA":
                return FakeResponse(
                    {
                        "DNSData": {
                            "dnsRecords": [
                                {
                                    "dnsType": "A",
                                    "name": domain_name,
                                    "address": "198.51.100.7",
                                    "ttl": 300,
                                }
                            ]
                        }
                    }
                )
            return FakeResponse({"DNSData": {"dnsRecords": []}})

        if url.endswith("/api/v1"):
            return FakeResponse(
                {
                    "ip": params.get("ipAddress"),
                    "location": {"country": "BR", "region": "SP", "city": "Sao Paulo"},
                    "isp": "Example ISP",
                    "as": {"asn": 64512, "name": "Example ASN", "route": "198.51.100.0/24"},
                }
            )

        raise AssertionError(f"unexpected GET {url} {params}")

    async def post(self, url, json=None):
        self.calls.append(("POST", url, dict(json or {})))
        raise AssertionError("DNS Chronicle/DNS History must not be called by default")


@pytest.mark.asyncio
async def test_domain_provenance_uses_dns_lookup_for_full_hostname_before_registered_domain(monkeypatch):
    from app.agents.tools import domain_provenance

    FakeWhoisXmlClient.calls = []
    monkeypatch.setattr(domain_provenance.httpx, "AsyncClient", FakeWhoisXmlClient)
    monkeypatch.setattr(domain_provenance, "settings", SimpleNamespace(
        DOMAIN_PROVENANCE_ENABLED=True,
        WHOISXML_API_KEY="test-key",
        WHOISXML_TIMEOUT_SECONDS=5,
    ))

    result = await domain_provenance.analyze_domain_provenance(
        "http://halifax.co.uk.account.security.update.moroba.com.br"
    )

    assert result["status"] == "success"
    assert result["domain"] == "moroba.com.br"
    assert result["hostname"] == "halifax.co.uk.account.security.update.moroba.com.br"
    assert result["dns_lookup"][0]["value"] == "198.51.100.7"
    assert result["dns_lookup"][0]["source"] == "hostname"
    assert result["ip_geolocation"][0]["ip"] == "198.51.100.7"

    dns_calls = [call for call in FakeWhoisXmlClient.calls if call[1].endswith("/DNSService")]
    assert dns_calls == [
        (
            "GET",
            domain_provenance.WHOISXML_DNS_LOOKUP_URL,
            {
                "apiKey": "test-key",
                "domainName": "halifax.co.uk.account.security.update.moroba.com.br",
                "type": "A,AAAA",
                "outputFormat": "JSON",
            },
        )
    ]


class FakeFallbackDnsClient(FakeWhoisXmlClient):
    async def get(self, url, params=None):
        params = params or {}
        self.calls.append(("GET", url, dict(params)))

        if url.endswith("/WhoisService"):
            return FakeResponse({"WhoisRecord": {"registrarName": "Example Registrar"}})

        if url.endswith("/DNSService"):
            domain_name = params.get("domainName")
            record_type = params.get("type")
            if domain_name == "login.example.com" and record_type == "CNAME":
                return FakeResponse(
                    {
                        "DNSData": {
                            "dnsRecords": [
                                {
                                    "dnsType": "CNAME",
                                    "name": domain_name,
                                    "target": "edge.example.net",
                                }
                            ]
                        }
                    }
                )
            if domain_name == "edge.example.net" and record_type == "A,AAAA":
                return FakeResponse({"DNSData": {"dnsRecords": []}})
            if domain_name == "example.com" and record_type == "A,AAAA":
                return FakeResponse(
                    {
                        "DNSData": {
                            "dnsRecords": [
                                {
                                    "dnsType": "A",
                                    "name": domain_name,
                                    "address": "203.0.113.9",
                                }
                            ]
                        }
                    }
                )
            return FakeResponse({"DNSData": {"dnsRecords": []}})

        if url.endswith("/api/v1"):
            return FakeResponse({"ip": params.get("ipAddress"), "isp": "Fallback ISP", "as": {"asn": 64513}})

        raise AssertionError(f"unexpected GET {url} {params}")


@pytest.mark.asyncio
async def test_domain_provenance_follows_cname_then_falls_back_to_registered_domain(monkeypatch):
    from app.agents.tools import domain_provenance

    FakeFallbackDnsClient.calls = []
    monkeypatch.setattr(domain_provenance.httpx, "AsyncClient", FakeFallbackDnsClient)
    monkeypatch.setattr(domain_provenance, "settings", SimpleNamespace(
        DOMAIN_PROVENANCE_ENABLED=True,
        WHOISXML_API_KEY="test-key",
        WHOISXML_TIMEOUT_SECONDS=5,
    ))

    result = await domain_provenance.analyze_domain_provenance("https://login.example.com/reset")

    assert result["status"] == "success"
    assert [record["type"] for record in result["dns_lookup"]] == ["CNAME", "A"]
    assert result["dns_lookup"][0]["value"] == "edge.example.net"
    assert result["dns_lookup"][1]["value"] == "203.0.113.9"
    assert result["dns_lookup"][1]["source"] == "registered_domain"
    assert result["ip_geolocation"][0]["ip"] == "203.0.113.9"

    dns_targets = [
        (call[2]["domainName"], call[2]["type"])
        for call in FakeFallbackDnsClient.calls
        if call[1].endswith("/DNSService")
    ]
    assert dns_targets == [
        ("login.example.com", "A,AAAA"),
        ("login.example.com", "CNAME"),
        ("edge.example.net", "A,AAAA"),
        ("example.com", "A,AAAA"),
    ]
