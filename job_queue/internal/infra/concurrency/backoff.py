# internal/infra/concurrency/backoff.py

import random
import time
from typing import Optional

class Backoff:
    """
    實作帶有 Jitter (抖動) 的指數退避演算法。
    用於處理分散式環境下的 Race Condition 與 重試機制，防止驚群效應 (Thundering Herd)。
    """

    def __init__(
        self, 
        base_delay: float = 1.0, 
        max_delay: float = 60.0, 
        factor: float = 2.0,
        jitter: bool = True
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter

    def compute_delay(self, attempt: int) -> float:
        """
        計算第 n 次嘗試的等待時間。
        公式: min(max_delay, base_delay * (factor ^ attempt))
        """
        if attempt <= 0:
            return 0.0

        # 指數計算
        delay = self.base_delay * (self.factor ** (attempt - 1))
        
        # 封頂
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Full Jitter 策略：在 [0, delay] 之間隨機取值
            # 這能最有效地將併發衝突的 Worker 散開
            return random.uniform(0, delay)
        
        return delay

    def sleep(self, attempt: int):
        """執行緒休眠"""
        delay = self.compute_delay(attempt)
        time.sleep(delay)

# ----------------------------------------------------------------
# Domain Policy 結合範例 (PolicyService 會用到)
# ----------------------------------------------------------------

class RetryPolicy:
    """定義任務重試的具體策略"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.backoff = Backoff(base_delay=2.0, max_delay=300.0)

    def should_retry(self, current_attempt: int) -> bool:
        return current_attempt < self.max_retries

    def get_next_available_time(self, current_attempt: int, now: float) -> float:
        """計算下一次任務可以被重新執行的 Unix Timestamp"""
        delay = self.backoff.compute_delay(current_attempt)
        return now + delay
