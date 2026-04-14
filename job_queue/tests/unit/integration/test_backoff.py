import pytest
from internal.infra.concurrency.backoff import Backoff

def test_backoff_exponential_growth():
    """測試延遲時間是否隨嘗試次數指數增長（不考慮 Jitter）"""
    # 關閉 jitter 進行確定性測試
    backoff = Backoff(base_delay=1.0, factor=2.0, jitter=False)
    
    assert backoff.compute_delay(1) == 1.0   # 1 * (2^0)
    assert backoff.compute_delay(2) == 2.0   # 1 * (2^1)
    assert backoff.compute_delay(3) == 4.0   # 1 * (2^2)
    assert backoff.compute_delay(4) == 8.0   # 1 * (2^3)

def test_backoff_max_delay_cap():
    """測試延遲時間是否會被封頂"""
    max_d = 10.0
    backoff = Backoff(base_delay=1.0, factor=2.0, max_delay=max_d, jitter=False)
    
    # 2^4 = 16.0，應該被封頂在 10.0
    assert backoff.compute_delay(5) == 10.0
    assert backoff.compute_delay(10) == 10.0

def test_full_jitter_behavior():
    """測試 Full Jitter 是否在預期區間內隨機分佈"""
    base = 10.0
    backoff = Backoff(base_delay=base, jitter=True)
    
    # 進行多次採樣，確保結果落在 [0, base] 之間
    samples = [backoff.compute_delay(1) for _ in range(100)]
    
    for s in samples:
        assert 0 <= s <= base
    
    # 統計上不應該所有值都一樣 (隨機性校驗)
    assert len(set(samples)) > 90 

def test_zero_attempts():
    """測試第 0 次嘗試不應有延遲"""
    backoff = Backoff()
    assert backoff.compute_delay(0) == 0.0

@pytest.mark.parametrize("attempt, expected_max", [
    (1, 2.0),
    (2, 4.0),
    (3, 8.0),
])
def test_jitter_ranges(attempt, expected_max):
    """使用參數化測試驗證不同次數下的 Jitter 上限"""
    backoff = Backoff(base_delay=2.0, factor=2.0, jitter=True)
    
    # 跑多次確保隨機值不會越界
    for _ in range(50):
        delay = backoff.compute_delay(attempt)
        assert 0 <= delay <= expected_max
