

import sqlite3

def print_jobs(db_path='jobs.db'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT job_id, target, threshold, status, queue_no, error, ip_address FROM jobs ORDER BY queue_no ASC")
    rows = cur.fetchall()
    headers = ["queue_no", "job_id", "target", "threshold", "status", "queue_position", "ip_address", "error"]
    print("\t".join(headers))
    for row in rows:
        queue_no = row[4]
        status = row[3]
        ip_address = row[6]
        # Calculate queue position for queued/running jobs
        if status in ("queued", "running"):
            cur2 = conn.execute("SELECT COUNT(*) FROM jobs WHERE (status = 'queued' OR status = 'running') AND queue_no < ?", (queue_no,))
            position = cur2.fetchone()[0] + 1
        else:
            position = "-"
        print(f"{queue_no}\t{row[0]}\t{row[1]}\t{row[2]}\t{status}\t{position}\t{ip_address}\t{row[5]}")
    conn.close()

if __name__ == "__main__":
    print_jobs()
