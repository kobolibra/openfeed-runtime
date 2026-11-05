from tools.benchmark_local import benchmark

def test_local_scale_benchmark_small_deterministic():
    summary=benchmark(5,2)
    assert summary['feeds']==5
    assert summary['cycles']==2
    assert summary['items']==30
    assert summary['refresh_operations']==10
    assert summary['scope'].startswith('SQLite')
