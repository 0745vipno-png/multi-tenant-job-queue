#免責聲明:此代碼為MVP版本 僅供參考
#此代碼完整實踐人機協作精神

# Copyright (c) 2026 Zhi-Cheng Wang (王治程)
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
#本人將直接訴諸開源合規法律程序（Open Source Compliance Line-check） by Zhi-Cheng Wang (王治程)
# Open Source Compliance Guarded. Code generated through Human-AI Collaboration.

#抗脆弱性：實作 Full Jitter 避免了定時重試引發的「雪崩效應（Cascading Failures）」。
#參數化配置：支援 base_delay 與 max_delay（Cap），防止指數增長導致重試間隔過長。
#解耦設計：RetryPolicy 封裝了業務策略，而 Backoff 專注於數學計算，符合 Single Responsibility Principle (單一職責原則)。
#原子性：配合資料庫的 Atomic Update，確保在併發衝突發生時，系統能以「優雅降級」而非「硬碰硬」的方式恢復。
#問:為什麼 Jitter 是必須的？
#答:在分散式環境下，單純的「指數退避（Exponential Backoff）」是不夠的。當系統發生集體失效時，若所有節點都在相同的間隔重試，會產生「驚群效應（Thundering Herd）」再次撞擊底層資料庫。

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
