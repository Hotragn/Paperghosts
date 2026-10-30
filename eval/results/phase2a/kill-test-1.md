# Kill test 1

On 2026-10-30 the full read of the archive (`ingest-20261030T044316Z`, all 180 years, four at a time) had its worker killed 27 minutes in, at 05:10:45 UTC. The finished years stayed finished, and the four years in flight ran again from their beginnings as attempt 2. The read went on to finish all 180 years at 06:41:54 UTC (decision 25).

## Before the kill

Four years were in flight, each on attempt 1. Their last heartbeats, as Temporal had them ([screenshot](kill-test-1-pending.png)):

| Year | File | Last heartbeat |
|---|---|---|
| 1881 | 2,661 MB | 1,594 MB (60%) |
| 1882 | 2,699 MB | 810 MB (30%) |
| 1883 | 3,003 MB | 714 MB (24%) |
| 1884 | 3,121 MB | 5 MB, its first heartbeat |

96 years were done. 95 were on attempt 1. 1872 was on attempt 2: its first attempt's stream ended partway through a page at about 05:03 (`tarfile.ReadError: unexpected end of data`), and attempt 2 started at 05:03:08.

## The kill

`kill -KILL -- -38958` sent SIGKILL to the worker's whole process group, 9 processes:
- make and uv
- the worker
- the multiprocessing resource tracker and state manager
- the four year processes

Afterwards, `pgrep -g 38958` and `ps -p` on all 9 pids found nothing.

## After the restart

- A new worker, `41373@paperghosts-worker`, was polling within seconds.
- Temporal timed out each killed attempt two minutes after its last heartbeat reached the server, between 05:11:49 and 05:12:31. It started attempt 2 five seconds later, the retry policy's first interval ([screenshot](kill-test-1-retry.png)).
- Each year started again from the beginning of its file, because a gzip stream can't seek. Each attempt 2's first heartbeat is at page 200.
- The 96 manifests from before the kill were byte-identical afterwards.
- Until the four retries finished, the only manifests written were those of 1881–1884. All four are attempt 2, and each `bytes_read` equals the file's listed size.
- Each year's ActivityTaskStarted event keeps the timeout and the retry: attempt 2, with `activity Heartbeat timeout` (`TIMEOUT_TYPE_HEARTBEAT`) as its last failure. These are events 591, 597, 603 and 609, and [the screenshot](kill-test-1-history.png) shows 1883's.
- The kill cost under two minutes of reading. No year ran for 69 s, and all four were running again 111 s after the kill. The killed attempts had read about 4 GB, which the retries read again.

## The orphan check (decision 23)

Before the full read, a one-year run of 1850 had only its worker's main process killed, 12 s into the year. Its year process was orphaned, and launchd (pid 1) adopted it. It stopped 0.18 s later, at its next heartbeat, and no 1850 file was written or changed. Before decision 23, an orphan like this carried on and wrote its files.
