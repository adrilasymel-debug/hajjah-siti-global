import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from .test_workflows import verified,payment

@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'),reason='Requires an isolated PostgreSQL test database')
def test_concurrent_payments_cannot_overpay(ctx):
    b=verified(ctx)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(payment,ctx,b,'80.00','concurrency-key-'+str(i)) for i in range(2)]
        statuses=sorted(f.result().status_code for f in futures)
    assert statuses==[201,409]
