"""The relay CLI: proofs, check, summary, one page each."""

from __future__ import annotations

import argparse

from relay.proofs import registry


def _summary() -> int:
    findings = registry.all_findings()
    broken = [f for f in findings if not f.holds]
    print(f"{len(findings)} proofs ({len(broken)} broken)")
    return 1 if broken else 0


def _check() -> int:
    broken = registry.broken()
    if broken:
        print("broken proofs: " + ", ".join(broken))
        return 1
    print("all proofs hold")
    return 0


def _proofs() -> int:
    print(registry.report())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relay")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("proofs", help="print every proof's line")
    sub.add_parser("check", help="exit nonzero if any proof is broken")
    sub.add_parser("summary", help="one-line proof count")
    args = parser.parse_args(argv)
    if args.command == "proofs":
        return _proofs()
    if args.command == "check":
        return _check()
    return _summary()


if __name__ == "__main__":
    raise SystemExit(main())
