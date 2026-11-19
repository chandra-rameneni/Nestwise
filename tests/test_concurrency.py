"""Several requests at once must not break the catalog (found 2026-11-19: the home page's 4 category-photo
requests ran in parallel and some returned HTTP 500, because one SQLite connection was shared across threads)."""
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

import server


def test_parallel_product_requests_all_succeed():
    c = TestClient(server.app)
    urls = [f"/api/products?q={q}&category={cat}&page_size=1"
            for q, cat in [("sofa", "furniture"), ("bedsheet", "home_furnishing"), ("lamp", "home_decor"),
                           ("mug", "kitchen_dining")]] * 10
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda u: c.get(u).status_code, urls))
    assert codes == [200] * len(urls)
