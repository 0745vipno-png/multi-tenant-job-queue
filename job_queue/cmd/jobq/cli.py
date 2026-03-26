from __future__ import annotations
import argparse
import json
from datetime import datetime, UTC

from internal.context.tenant_context import TenantContext
from internal.application.submit_job import SubmitJobUseCase
from internal.application.lease_job import LeaseJobUseCase
from internal.application.ack_job import AckJobUseCase
from internal.application.recover_leases import RecoverLeasesUseCase
from internal.repository.sqlite.db import SQLiteDatabase

DB_PATH = "job_queue.db"

def get_db():
    db = SQLiteDatabase(DB_PATH)
    db.initialize_schema() # 確保執行時表是存在的
    return db

# -------------------------
# submit: 提交任務
# -------------------------
def handle_submit(args):
    db = get_db()
    ctx = TenantContext(tenant_id=args.tenant, queue_id=args.queue)
    
    # 執行提交
    submitter = SubmitJobUseCase(db)
    job_id = submitter.execute(
        ctx=ctx,
        payload_json=args.payload, # 傳入 JSON 字串
    )
    print(f"✅ Job submitted! ID: {job_id}")

# -------------------------
# worker: 模擬 Worker 跑一輪
# -------------------------
def handle_worker(args):
    db = get_db()
    tenant_id = args.tenant
    queue_id = args.queue
    worker_id = args.worker

    # 1. 維護：先救回那些死掉的任務
    recovery_uc = RecoverLeasesUseCase(db)
    recovered = recovery_uc.execute(tenant_id, queue_id)
    if recovered > 0:
        print(f"🚑 Recovered {recovered} zombie jobs.")

    # 2. 領取與執行
    try:
        lease_uc = LeaseJobUseCase(db)
        lease = lease_uc.execute(tenant_id, queue_id, worker_id)
        print(f"📥 Leased job {lease.job_id}")

        # 模擬執行並結案 (Ack)
        ack_uc = AckJobUseCase(db)
        ack_uc.execute(
            tenant_id=tenant_id,
            queue_id=queue_id,
            job_id=lease.job_id,
            lease_token=lease.lease_token,
            worker_id=worker_id,
        )
        print(f"✅ Successfully processed {lease.job_id}")

    except Exception as e:
        # 如果沒工作會噴 JobNotLeaseableError
        print(f"😴 No work found or error: {str(e)}")

# -------------------------
# inspect: 查看排隊現況
# -------------------------
def handle_inspect(args):
    db = get_db()
    # 使用我們在 db.py 裡定義好的連線
    rows = db._conn.execute(
        """
        SELECT job_id, state, attempt_count, available_at
        FROM jobs
        WHERE tenant_id = ? AND queue_id = ?
        ORDER BY created_at DESC LIMIT 10
        """,
        (args.tenant, args.queue),
    ).fetchall()

    print(f"\n📊 Queue Status [{args.tenant}/{args.queue}]:")
    for r in rows:
        print(f"- {r['job_id'][:8]}... | {r['state']:<10} | retry={r['attempt_count']} | next={r['available_at']}")

def main():
    parser = argparse.ArgumentParser(prog="jobq")
    sub = parser.add_subparsers(dest="command")

    # submit 指令
    p_submit = sub.add_parser("submit")
    p_submit.add_argument("--tenant", default="t1")
    p_submit.add_argument("--queue", default="default")
    p_submit.add_argument("--payload", required=True)
    p_submit.set_defaults(func=handle_submit)

    # worker 指令
    p_worker = sub.add_parser("worker")
    p_worker.add_argument("--tenant", default="t1")
    p_worker.add_argument("--queue", default="default")
    p_worker.add_argument("--worker", required=True)
    p_worker.set_defaults(func=handle_worker)

    # inspect 指令
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--tenant", default="t1")
    p_inspect.add_argument("--queue", default="default")
    p_inspect.set_defaults(func=handle_inspect)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
