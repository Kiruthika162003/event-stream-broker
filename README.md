# relay

A Kafka-like event streaming broker, built in Python from the log upward.

`relay` is a partitioned, append-only, replicated event log with the
machinery a real broker needs around it: consumer groups that rebalance,
replication with an in-sync set and a high watermark, retention and log
compaction, idempotent and transactional produce with exactly-once
delivery, a stream-processing layer with windows and joins, and the
distributed-systems primitives underneath all of it. It is a study of how
a broker actually keeps its promises, written so that every guarantee is
either demonstrated by a test or refused honestly when it cannot hold.

The package is called `relay`. Everything runs on the standard library;
there are no runtime dependencies.

## The shape of it

A broker is a stack of guarantees, and `relay` is organized the same way.

- **The log.** Records, segments, an append-only partition log, offsets,
  the sparse offset and time indexes, and the high watermark that divides
  committed records from the uncommitted tail.
- **Replication.** Leaders and followers, the in-sync replica set, the
  pull-based fetch loop where a follower's fetch offset is its own
  acknowledgment, leader election, leader-epoch truncation, unclean
  election as an explicit durability-versus-availability switch, and
  `min.insync.replicas` as the floor an `acks=all` write must clear.
- **Consumer groups.** Join, sync, heartbeat, the generation that bumps on
  every rebalance, sticky and cooperative assignment, static assignment,
  offset commit and reset, and the coordinator that reloads group state
  before it will serve.
- **Transactions and exactly-once.** Producer idempotence by producer id
  and sequence number, the transaction coordinator and its fencing epoch,
  commit and abort markers, the last stable offset that a read-committed
  consumer may not read past, and the aborted-transaction index it filters
  by.
- **Retention.** Time and size retention, the log start offset that rises
  as records age out, compaction to the latest value per key, and the
  tombstone grace that keeps a delete visible long enough for a lagging
  consumer to see it.
- **Stream processing.** Tumbling, hopping, and session windows; stream,
  table, global-table, and outer joins; state stores, changelogs,
  watermarks, suppression, and retraction.
- **Resilience.** Circuit breakers, retry budgets, hedged requests,
  deadline propagation, bulkheads, flow control and backpressure, quotas
  with a throttle-delay that paces a client back to its ceiling, and
  capped exponential backoff with jitter.
- **Distributed systems.** Lamport, vector, and hybrid-logical clocks;
  g-counter, LWW, and OR-set CRDTs; quorum reads and writes; Raft pieces
  including the commit index, log matching, pre-vote, read-index, snapshot
  install, and single-voter membership change; gossip, Merkle
  anti-entropy, chain replication, hinted handoff, and causal delivery.
- **Data structures and algorithms.** Bloom and counting-bloom filters, a
  timer wheel, ring buffer, LRU, skip list, Fenwick and segment trees,
  disjoint set, trie, priority queue, running median, quickselect,
  count-min sketch, and HyperLogLog, each tied to a concrete broker use.
- **Operations math.** Capacity planning, error budgets, write
  amplification, partition limits, consumer scaling, hot-partition and
  slow-broker detection, and reassignment throttling with a deadline
  solver that refuses the impossible.

Every module carries a narrative docstring explaining the idea, the
tradeoff, and the failure it guards against, and a paired test file that
holds it to that account.

## Proofs

The signature of this repository is its **proofs**. A proof is a standing
demonstration that a specific guarantee holds under a scenario designed to
break it. Each one runs real broker code and reports a single finding in
plain language, and the whole set is checked in the test suite, so a proof
that stopped holding would fail the build.

```bash
python -m relay.cli summary
python -m relay.cli check
python -m relay.cli proofs
```

`summary` prints the count, `check` exits non-zero if any proof is broken,
and `proofs` prints each finding. There are 13, covering the watermark's
blast radius, exactly-once versus at-least-once, rebalancing without a
stop-the-world pause, the retention floor, sticky assignment, epoch
truncation, order under retry, CRC integrity, throttle bounds, frame
reassembly, the parallel-mean count, bloom-filter safety, and why
membership changes go one voter at a time.

A representative finding:

```
nolostcommit: holds -- the epoch handshake truncates exactly the
unreplicated tail (40 records) and leaves the committed prefix untouched;
committed and truncated are disjoint by arithmetic, not by luck
```

## Examples

The `examples/` directory holds runnable walkthroughs, each a single file
you can run directly:

```bash
python -m examples.firststream
python -m examples.exactlyonceday
python -m examples.failoverday
python -m examples.rebalanceday
python -m examples.retentionday
python -m examples.streamsday
python -m examples.consensusday
python -m examples.securityday
python -m examples.wireformatday
python -m examples.operationsday
python -m examples.upgradeday
```

`firststream` is the place to start: it produces to a partitioned topic,
advances the watermark, commits, and consumes, showing the committed line
in between.

## Refusals

Every refusal in the broker descends from one small family of errors in
`relay/errors.py`: `Invalid` for a request that contradicts itself or the
configuration, `Missing` for something that does not exist, `Sealed` for a
target closed to writes, `Fenced` for a stale writer that lost its claim,
and `Lagging` for a reader that fell off the retained window. When the
broker cannot keep a promise, it says so and refuses, rather than
returning a plausible-looking wrong answer. That discipline is the point:
much of the code is about the cases where the honest move is to reject.

## Running the tests

```bash
python -m pytest tests/ -q
```

The suite has 2462 tests across 352 modules, and it is green. Linting is
`ruff` over the whole tree:

```bash
python -m ruff check relay/ tests/
```

## A note on how this was built

The work was done module by module in a tight loop: write the module and
its tests, lint, run the whole suite, and commit only on green. When a
test refuted a guess, the wrong guess was kept in the record beside the
measured truth rather than quietly erased, because the correction is the
most honest part of the history. Two design bugs were found exactly that
way, by a test that disagreed with the code: an OR-set whose per-replica
tags collided across replicas, and a segment-roll decision that keyed a
dict by a value that could tie. Both are fixed, and both fixes are
recorded in the commits that made them.
