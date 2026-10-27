from app.adapters.douyin.signer import canonical_json, sign_request


def test_canonical_json_sorts_and_compacts() -> None:
    assert canonical_json({"size": 50, "page": 0}) == '{"page":0,"size":50}'


def test_sign_request_matches_known_vector() -> None:
    signature = sign_request(
        app_key="test_key",
        app_secret="test_secret",
        method="order.searchList",
        param_json='{"page":0,"size":50}',
        timestamp="2026-10-27 10:00:00",
    )
    assert signature == "af379fa1da6904e2061934441a330fa1713f0a51928665c2237985b9438b6c35"
