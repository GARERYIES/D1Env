import pytest


@pytest.mark.parametrize("path", ["/api/catalog","/api/jobs/unknown","/api/jobs/unknown/events","/api/session"])
def test_unauthenticated_reads_denied(web_client,path):
    assert web_client.get(path).status_code == 401


def test_bootstrap_is_single_use_and_cookie_protected(web_client):
    kwargs={"json":{"token":"private-test-bootstrap"},"headers":{"Origin":"http://127.0.0.1:8765"}}
    response=web_client.post("/api/session/bootstrap",**kwargs)
    assert response.status_code == 200
    cookie=response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert web_client.post("/api/session/bootstrap",**kwargs).status_code == 401


def test_origin_host_and_csrf_enforced(authenticated):
    client,headers=authenticated
    request={"profile_id":"demo"}
    assert client.post("/api/plans",json=request).status_code == 403
    assert client.post("/api/plans",json=request,headers={**headers,"Origin":"https://evil.test"}).status_code == 403
    assert client.get("/api/catalog",headers={"Host":"evil.test"}).status_code == 403
    assert client.get("/api/catalog",headers={"Origin":"https://evil.test"}).status_code == 403
    assert client.get("/api/jobs/unknown/events?stream=true",headers={"Origin":"https://evil.test"}).status_code == 403


def test_cross_site_fetch_metadata_rejected(authenticated):
    client,_headers=authenticated
    assert client.get("/api/catalog",headers={"Sec-Fetch-Site":"cross-site"}).status_code == 403


def test_missing_origin_cannot_bootstrap(web_client):
    assert web_client.post("/api/session/bootstrap",json={"token":"private-test-bootstrap"}).status_code == 403


def test_non_ascii_bootstrap_is_rejected_without_consuming_valid_token(web_client):
    headers = {"Origin":"http://127.0.0.1:8765"}
    malformed = web_client.post("/api/session/bootstrap",json={"token":"中"*16},headers=headers)
    assert malformed.status_code in {401,422}
    valid = web_client.post("/api/session/bootstrap",json={"token":"private-test-bootstrap"},headers=headers)
    assert valid.status_code == 200


def test_non_ascii_csrf_is_rejected_with_403(authenticated):
    client,headers = authenticated
    bad_headers = [(key.encode(),value.encode()) for key,value in headers.items() if key != "X-CSRF-Token"]
    bad_headers.append((b"X-CSRF-Token", b"\xc3\xa9"*16))
    assert client.post("/api/plans",json={},headers=bad_headers).status_code == 403
