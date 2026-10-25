import ipaddress
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

import pytest

POLICIES = Path(__file__).resolve().parent.parent / "policies"
TEMPLATES = sorted(p.stem.removesuffix(".xml") for p in POLICIES.glob("*.xml.tftpl"))
CLOUDFLARE_V4 = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]
Render = Callable[..., str]


EXPRESSION_ATTRIBUTE = re.compile(r'="(@[({].*?)"(?=\s*/?>|\s+[\w:-]+=)', re.DOTALL)


def parse(xml: str) -> ET.Element:
    escaped = EXPRESSION_ATTRIBUTE.sub(
        lambda m: '="' + m.group(1).replace('"', "&quot;") + '"', xml
    )
    return ET.fromstring(escaped)


def attr(element: ET.Element, path: str, name: str) -> str | None:
    found = element.find(path)
    assert found is not None, f"missing {path}"
    return found.get(name)


def test_every_template_has_a_test() -> None:
    assert TEMPLATES == ["claims-api", "model-api", "product", "service"]


@pytest.mark.parametrize("name", TEMPLATES)
def test_renders_to_well_formed_xml(render: Render, name: str) -> None:
    root = parse(render(name))
    assert root.tag == "policies"
    assert [child.tag for child in root] == ["inbound", "backend", "outbound", "on-error"][
        : len(root)
    ]


@pytest.mark.parametrize("name", TEMPLATES)
@pytest.mark.parametrize("cache", [True, False])
def test_no_unrendered_template_syntax_is_left(render: Render, name: str, cache: bool) -> None:
    xml = render(name, semantic_cache_enabled=cache)
    assert "${" not in xml
    assert "%{" not in xml


@pytest.mark.parametrize("name", TEMPLATES)
def test_templates_hold_no_secrets_or_hostnames(name: str) -> None:
    text = (POLICIES / f"{name}.xml.tftpl").read_text()
    hosts = r"[\w-]+\.(openai\.azure\.com|services\.ai\.azure\.com|cognitiveservices\.azure\.com)"
    assert not re.search(hosts, text)
    assert not re.search(r"(?i)api[-_]?key|subscription-key|bearer ", text)


def test_cloudflare_fragment_matches_the_published_ipv4_list() -> None:
    fragment = (POLICIES / "cloudflare-ips.xml").read_text()
    ranges = re.findall(r'<address-range from="([\d.]+)" to="([\d.]+)" />', fragment)
    expected = [
        (str(ipaddress.ip_network(c)[0]), str(ipaddress.ip_network(c)[-1])) for c in CLOUDFLARE_V4
    ]
    assert ranges == expected
    assert len(ranges) == 15
    assert ":" not in "".join(a + b for a, b in ranges)


def test_service_policy_has_exactly_one_ip_filter_with_all_cloudflare_ranges(
    render: Render,
) -> None:
    root = parse(render("service"))
    filters = list(root.iter("ip-filter"))
    assert len(filters) == 1
    assert filters[0].get("action") == "allow"
    assert len(filters[0].findall("address-range")) == 15
    assert filters[0].findall("address") == []


def test_extra_addresses_join_the_same_filter(render: Render) -> None:
    root = parse(render("service", extra_allowed_addresses=["20.1.2.3"]))
    filters = list(root.iter("ip-filter"))
    assert len(filters) == 1
    assert [a.text for a in filters[0].findall("address")] == ["20.1.2.3"]
    assert len(filters[0].findall("address-range")) == 15


def test_cloudflare_restriction_can_be_switched_off_for_tests(render: Render) -> None:
    root = parse(render("service", restrict_to_cloudflare=False))
    assert list(root.iter("ip-filter")) == []


def test_service_policy_deletes_each_personal_data_header(render: Render) -> None:
    root = parse(render("service", personal_data_headers=["x-user-email", "cf-connecting-ip"]))
    deleted = [h.get("name") for h in root.iter("set-header") if h.get("exists-action") == "delete"]
    assert deleted == ["x-user-email", "cf-connecting-ip"]


def test_service_policy_still_forwards_when_nothing_is_stripped(render: Render) -> None:
    root = parse(render("service", personal_data_headers=[]))
    assert root.find("backend/forward-request") is not None
    assert [h for h in root.iter("set-header")] == []


def test_product_limits_tokens_per_subscription(render: Render) -> None:
    root = parse(render("product", tokens_per_minute=1234, token_quota=99, country="th"))
    limits = list(root.iter("llm-token-limit"))
    assert len(limits) == 1
    limit = limits[0]
    assert limit.get("counter-key") == "@(context.Subscription.Id)"
    assert limit.get("tokens-per-minute") == "1234"
    assert limit.get("token-quota") == "99"
    assert limit.get("token-quota-period") == "Monthly"


def test_product_rejects_a_mismatched_country(render: Render) -> None:
    root = parse(render("product", country="th"))
    when = next(root.iter("when"))
    assert '!= "th"' in (when.get("condition") or "")
    assert attr(when, "return-response/set-status", "code") == "403"


def test_product_policy_inherits_the_parent_policy(render: Render) -> None:
    root = parse(render("product"))
    assert root.find("inbound/base") is not None


def test_model_api_emits_the_four_required_dimensions(render: Render) -> None:
    root = parse(render("model-api"))
    metric = next(root.iter("llm-emit-token-metric"))
    names = [d.get("name") for d in metric.findall("dimension")]
    assert names[:4] == ["country", "app", "model", "route_tier"]
    assert len(names) <= 5


def test_model_api_turns_unknown_countries_into_unknown(render: Render) -> None:
    xml = render("model-api", allowed_countries=["ph", "sg"])
    variable = next(v for v in parse(xml).iter("set-variable") if v.get("name") == "country")
    expression = variable.get("value") or ""
    assert 'new[] { "ph", "sg", }' in expression
    assert ': "unknown"' in expression


def test_model_api_forwards_only_the_validated_country(render: Render) -> None:
    root = parse(render("model-api"))
    header = next(h for h in root.iter("set-header") if h.get("name") == "x-country")
    assert header.get("exists-action") == "override"
    assert 'Variables["country"]' in (header.findtext("value") or "")


def test_model_api_fails_over_on_429_with_a_retry(render: Render) -> None:
    root = parse(render("model-api", retry_count=3))
    retry = root.find("backend/limit-concurrency/retry")
    assert retry is not None
    assert "429" in (retry.get("condition") or "")
    assert retry.get("count") == "3"
    assert retry.find("forward-request") is not None


def test_model_api_caps_concurrent_requests_per_country(render: Render) -> None:
    root = parse(render("model-api", max_concurrent_per_country=5))
    cap = next(root.iter("limit-concurrency"))
    assert cap.get("max-count") == "5"
    assert 'Variables["country"]' in (cap.get("key") or "")
    assert cap.find("retry/forward-request") is not None


def test_model_api_uses_the_backend_pool_and_managed_identity(render: Render) -> None:
    root = parse(render("model-api", model_backend_id="small-pool"))
    assert attr(root, "inbound/set-backend-service", "backend-id") == "small-pool"
    assert root.find("inbound/authentication-managed-identity") is not None


def test_semantic_cache_is_off_by_default(render: Render) -> None:
    xml = render("model-api")
    assert "llm-semantic-cache" not in xml


def test_semantic_cache_applies_to_faq_only_and_is_partitioned_by_country(
    render: Render,
) -> None:
    root = parse(render("model-api", semantic_cache_enabled=True))
    lookup = next(root.iter("llm-semantic-cache-lookup"))
    assert lookup.get("embeddings-backend-auth") == "system-assigned"
    assert lookup.get("ignore-system-messages") == "true"
    assert 'Variables["country"]' in (lookup.findtext("vary-by") or "")
    for tag in ("llm-semantic-cache-lookup", "llm-semantic-cache-store"):
        parent = next(w for w in root.iter("when") if w.find(tag) is not None)
        assert 'Variables["is_faq"]' in (parent.get("condition") or "")
    store_condition = next(
        w for w in root.iter("when") if w.find("llm-semantic-cache-store") is not None
    ).get("condition")
    assert "== 200" in (store_condition or "")


def test_semantic_cache_flag_is_the_only_difference_in_what_runs(render: Render) -> None:
    on = parse(render("model-api", semantic_cache_enabled=True))
    off = parse(render("model-api", semantic_cache_enabled=False))
    assert len(list(on.iter("llm-semantic-cache-lookup"))) == 1
    assert len(list(on.iter("llm-semantic-cache-store"))) == 1
    assert len(list(off.iter("llm-semantic-cache-lookup"))) == 0


def test_claims_api_has_no_cache_and_no_token_policies(render: Render) -> None:
    xml = render("claims-api")
    assert "cache" not in xml
    assert "llm-" not in xml


def test_claims_api_rejects_unknown_countries_and_rate_limits(render: Render) -> None:
    root = parse(render("claims-api", calls_per_minute=77, claims_backend_id="claims"))
    assert next(root.iter("rate-limit-by-key")).get("calls") == "77"
    assert attr(root, "inbound/set-backend-service", "backend-id") == "claims"
    assert next(root.iter("set-status")).get("code") == "400"


def test_cloudflare_fragment_comment_does_not_mention_policy_tags() -> None:
    text = (POLICIES / "cloudflare-ips.xml").read_text()
    comment = text[: text.index("-->")]
    assert "<ip-filter" not in comment
