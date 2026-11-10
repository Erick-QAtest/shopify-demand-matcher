"""One test per match status, plus the size-parsing rules they depend on."""

from sportland_matcher.matcher import DemandSupplyMatcher
from sportland_matcher.normalization import parse_legacy_sku_size
from sportland_matcher.shopify_source import QUERY, LocationInventory, ShopifyVariant
from sportland_matcher.smart_source import DemandEvent


def _event(*, sku="", size=""):
    return DemandEvent(
        event_uuid="e1",
        event_hash="h1",
        fecha_evento="2026-09-28T10:00:00Z",
        client_uuid="c1",
        phone="",
        event_type="PREGUNTA_TALLA_PRECIO",
        detail="",
        smart_sku=sku,
        explicit_size=size,
        requested_size=size,
        size_source="EXPLICIT" if size else "",
        channel="whatsapp",
        source_status="LOGGED",
        pg_evento_id="",
        raw_row_number=2,
    )


def _variant(*, sku, size, qty, product="P1", variant="V1"):
    return ShopifyVariant(
        variant_id=variant,
        variant_legacy_id=variant,
        product_id=product,
        product_legacy_id=product,
        product_handle="product",
        product_title="Product",
        product_status="ACTIVE",
        variant_title=size,
        sku=sku,
        size=size,
        inventory_total=qty,
        price="100",
        compare_at_price="",
        inventory_item_id="I1",
        locations=[LocationInventory(location_id="L1", location_name="Store", available=qty)],
    )


# --- size parsing -----------------------------------------------------------

def test_legacy_sku_carries_size():
    assert parse_legacy_sku_size("2033-27") == ("2033", "27")
    assert parse_legacy_sku_size("1878L-23.5") == ("1878L", "23.5")
    assert parse_legacy_sku_size("1878l-23,5") == ("1878L", "23.5")


def test_sequence_suffix_is_not_a_size():
    # 951-1: the 1 is a sequence number, not shoe size 1.
    assert parse_legacy_sku_size("951-1") == ("951-1", "")
    assert parse_legacy_sku_size("AB-60") == ("AB-60", "")


def test_sequence_suffix_never_becomes_a_match_by_size():
    matcher = DemandSupplyMatcher([_variant(sku="951-27", size="27", qty=3)])
    result = matcher.match(_event(sku="951-1"))
    assert result.match_status == "NEEDS_SIZE_RESOLUTION"
    assert result.variant_id == ""


# --- one test per status ------------------------------------------------------

def test_sibling_variant_resolved_by_requested_size():
    # Same shape as the live V1.1 check: SKU points to size 26, customer asked for 27.
    matcher = DemandSupplyMatcher([
        _variant(sku="2072-26", size="26", qty=1, variant="V26"),
        _variant(sku="2072-27", size="27", qty=0, variant="V27"),
    ])
    result = matcher.match(_event(sku="2072-26", size="27"))
    assert result.match_status == "MATCH_OUT_OF_STOCK"
    assert result.match_confidence == "HIGH"
    assert result.shopify_sku == "2072-27"


def test_size_conflict_when_requested_size_does_not_exist():
    matcher = DemandSupplyMatcher([_variant(sku="2072-26", size="26", qty=1)])
    result = matcher.match(_event(sku="2072-26", size="28"))
    assert result.match_status == "SIZE_CONFLICT"
    assert result.match_confidence == "LOW"


def test_ambiguous_when_sku_is_duplicated_in_shopify():
    matcher = DemandSupplyMatcher([
        _variant(sku="DUP-27", size="27", qty=1, product="P1", variant="V1"),
        _variant(sku="DUP-27", size="27", qty=2, product="P2", variant="V2"),
    ])
    result = matcher.match(_event(sku="DUP-27"))
    assert result.match_status == "AMBIGUOUS_MATCH"
    assert result.variant_id == ""


def test_needs_product_resolution_when_only_size_is_known():
    result = DemandSupplyMatcher([]).match(_event(size="27"))
    assert result.match_status == "NEEDS_PRODUCT_RESOLUTION"


def test_needs_size_resolution_when_sku_has_no_usable_size():
    result = DemandSupplyMatcher([]).match(_event(sku="ZZZ"))
    assert result.match_status == "NEEDS_SIZE_RESOLUTION"


def test_no_shopify_match_when_sku_and_size_are_unknown():
    result = DemandSupplyMatcher([_variant(sku="ABC-27", size="27", qty=1)]).match(_event(sku="ZZZ-27"))
    assert result.match_status == "NO_SHOPIFY_MATCH"


# --- zero writes --------------------------------------------------------------

def test_shopify_query_is_read_only():
    assert QUERY.lstrip().startswith("query ")
    assert "mutation" not in QUERY.lower()
