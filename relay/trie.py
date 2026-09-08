"""Trie: match a name against many prefixes at once, sharing the shared parts.

Matching a topic name against a set of prefix rules, an ACL that
grants access to every topic starting with orders-, a router that
sends every metrics- topic one way, is a prefix-membership question:
does the name start with any registered prefix. Checking each prefix
separately costs the whole set per name; a trie answers it in one
walk down the length of the name. A trie is a tree of characters
where each registered prefix is a path from the root, and prefixes
sharing a head share the path for that head, so orders-eu and
orders-us share the orders- path and branch only where they differ,
which is where the trie saves space over storing each string whole.
A node is marked as the end of a registered prefix, so walking a
query name down the trie and noting each end-marked node passed
gives every registered prefix the name starts with, and the longest
of them in one pass. This is what makes prefix ACLs cheap at scale:
a thousand prefix rules are one trie, and a topic name is matched
against all of them by walking its own length, not the rule count.
The trie inserts a prefix as a path marking its last node, and
matches a name by walking it and returning the longest registered
prefix that the name starts with, or none. It refuses an empty
prefix, which would match everything and defeat the point of
specific rules, and reports how many distinct prefixes are
registered against the node count, because a trie with far fewer
nodes than the total prefix length is one whose prefixes share long
heads, the sharing that is the structure's whole advantage."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class _TrieNode:
    children: dict[str, _TrieNode] = field(default_factory=dict)
    is_end: bool = False


@dataclass
class PrefixTrie:
    _root: _TrieNode = field(default_factory=_TrieNode)
    _count: int = 0

    def insert(self, prefix: str) -> None:
        if not prefix:
            raise Invalid("an empty prefix matches everything, defeating specific rules")
        node = self._root
        for ch in prefix:
            node = node.children.setdefault(ch, _TrieNode())
        if not node.is_end:
            node.is_end = True
            self._count += 1

    def longest_prefix_of(self, name: str) -> str | None:
        node = self._root
        best = None
        path = []
        for ch in name:
            if ch not in node.children:
                break
            node = node.children[ch]
            path.append(ch)
            if node.is_end:
                best = "".join(path)
        return best

    def matches(self, name: str) -> bool:
        return self.longest_prefix_of(name) is not None

    def _node_count(self) -> int:
        total = 0
        stack = [self._root]
        while stack:
            n = stack.pop()
            total += 1
            stack.extend(n.children.values())
        return total - 1  # exclude the root

    def report(self) -> str:
        return (
            f"{self._count} prefix(es) in {self._node_count()} node(s); far "
            "fewer nodes than the total prefix length is prefixes sharing long "
            "heads, the trie's whole advantage"
        )
