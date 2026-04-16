"""
dag.py — DAG builder, topological sort, and layer extraction for mill plan cards.

Pure functions — no I/O, no file reading. All functions take a Card Index dict
as input (as returned by plan_io.read_card_index).

Card Index dict schema (dict[int, dict]):
    Key: card number (int)
    Value dict fields:
        slug       (str)         — card slug
        creates    (list[str])   — files this card creates
        modifies   (list[str])   — files this card modifies
        reads      (list[str])   — files this card reads (no implicit edge)
        depends-on (list[str])   — explicit dependencies (card numbers as strings)
"""
from __future__ import annotations

from collections import deque

from millpy.core.log_util import log


class CycleError(ValueError):
    """Raised when a cycle is detected in the card dependency graph.

    Attributes
    ----------
    cycle:
        List of card numbers that form the cycle (or are involved in it).
    """

    def __init__(self, cycle: list[int]) -> None:
        self.cycle = cycle
        super().__init__(f"Cycle detected in card dependency graph: {cycle}")


def build_dag(card_index: dict[int, dict]) -> dict[int, set[int]]:
    """Build an adjacency list from a Card Index dict.

    Each entry in the returned dict maps a card number to the set of card
    numbers it directly depends on (prerequisites that must complete first).

    Edges are added from two sources:
    1. Explicit: ``depends-on`` field in each card entry.
    2. Implicit: two cards that both appear in ``creates ∪ modifies`` for the
       same file path must serialize — the higher-numbered card depends on the
       lower-numbered one.

    Files listed only in ``reads`` do NOT create implicit edges.

    Parameters
    ----------
    card_index:
        Keyed by card number (int). Each value has ``depends-on`` (list of
        card-number strings), ``creates``, ``modifies``, ``reads``
        (lists of file path strings).

    Returns
    -------
    dict[int, set[int]]
        Adjacency list: dag[n] = set of card numbers that card n depends on.
    """
    dag: dict[int, set[int]] = {num: set() for num in card_index}

    # --- Explicit edges from depends-on ---
    for card_number, entry in card_index.items():
        for dep_str in entry.get("depends-on", []):
            dep_number = int(dep_str)
            if dep_number in dag:
                dag[card_number].add(dep_number)

    # --- Implicit edges from file write conflicts ---
    # Build a map from file path → list of card numbers that create or modify it.
    file_to_writing_cards: dict[str, list[int]] = {}
    for card_number, entry in card_index.items():
        written_files = set(entry.get("creates", [])) | set(entry.get("modifies", []))
        for file_path in written_files:
            if file_path:
                file_to_writing_cards.setdefault(file_path, []).append(card_number)

    # For each file touched by multiple cards, serialize them: higher-numbered
    # card depends on every lower-numbered card that also touches the file.
    for file_path, writing_cards in file_to_writing_cards.items():
        writing_cards_sorted = sorted(writing_cards)
        for lower_index, lower_card in enumerate(writing_cards_sorted):
            for upper_card in writing_cards_sorted[lower_index + 1:]:
                dag[upper_card].add(lower_card)

    return dag


def topological_sort(dag: dict[int, set[int]]) -> list[int]:
    """Return all card numbers in topological order using Kahn's algorithm.

    Cards with no dependencies appear first. The sort is deterministic:
    when multiple cards are eligible in the same step, they are processed
    in ascending card-number order.

    Parameters
    ----------
    dag:
        Adjacency list as returned by ``build_dag``.

    Returns
    -------
    list[int]
        All card numbers in dependency order (prerequisites before dependents).

    Raises
    ------
    CycleError
        If the graph contains a cycle.
    """
    if not dag:
        return []

    # in_degree[n] = number of cards that card n depends on (prerequisites remaining)
    in_degree: dict[int, int] = {card: len(deps) for card, deps in dag.items()}

    # reverse_edges[dep] = list of cards that directly depend on dep
    reverse_edges: dict[int, list[int]] = {card: [] for card in dag}
    for card, deps in dag.items():
        for dep in deps:
            reverse_edges[dep].append(card)

    # Initialise queue with cards that have no prerequisites, in card-number order
    ready_queue: deque[int] = deque(
        card for card in sorted(dag) if in_degree[card] == 0
    )
    sorted_result: list[int] = []

    while ready_queue:
        card = ready_queue.popleft()
        sorted_result.append(card)
        for dependent in sorted(reverse_edges[card]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready_queue.append(dependent)

    if len(sorted_result) != len(dag):
        remaining_cards = [card for card in dag if card not in set(sorted_result)]
        log("dag", f"cycle detected among cards: {remaining_cards}")
        cycle = _find_cycle_in_subgraph(dag, set(remaining_cards))
        raise CycleError(cycle)

    return sorted_result


def extract_layers(dag: dict[int, set[int]]) -> list[list[int]]:
    """Group card numbers into parallel execution layers.

    Layer 0 contains cards with no dependencies. Layer N contains cards whose
    dependencies are all satisfied by cards in layers 0 through N-1. Cards
    within each layer are sorted in ascending card-number order.

    Parameters
    ----------
    dag:
        Adjacency list as returned by ``build_dag``.

    Returns
    -------
    list[list[int]]
        Ordered list of layers. Each layer is a sorted list of card numbers.
        Returns an empty list for an empty dag.

    Raises
    ------
    CycleError
        If the graph contains a cycle (i.e. after processing all reachable
        cards, some cards still have unsatisfied dependencies).
    """
    if not dag:
        return []

    in_degree: dict[int, int] = {card: len(deps) for card, deps in dag.items()}
    reverse_edges: dict[int, list[int]] = {card: [] for card in dag}
    for card, deps in dag.items():
        for dep in deps:
            reverse_edges[dep].append(card)

    layers: list[list[int]] = []
    current_layer = sorted(card for card, degree in in_degree.items() if degree == 0)

    while current_layer:
        layers.append(current_layer)
        next_layer_cards: list[int] = []
        for card in current_layer:
            for dependent in reverse_edges[card]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_layer_cards.append(dependent)
        current_layer = sorted(next_layer_cards)

    total_processed = sum(len(layer) for layer in layers)
    if total_processed != len(dag):
        remaining_cards = [card for card in dag if in_degree[card] > 0]
        log("dag", f"cycle detected among cards: {remaining_cards}")
        cycle = _find_cycle_in_subgraph(dag, set(remaining_cards))
        raise CycleError(cycle)

    return layers


def _find_cycle_in_subgraph(dag: dict[int, set[int]], nodes: set[int]) -> list[int]:
    """Find and return a cycle path within the subgraph induced by the given nodes.

    Uses depth-first search to locate a back edge, then extracts the cycle
    path from the current DFS stack.

    Parameters
    ----------
    dag:
        Full adjacency list.
    nodes:
        Set of card numbers to search within (only edges between these cards
        are considered).

    Returns
    -------
    list[int]
        A list of card numbers forming a cycle (the repeated node appears only
        once at the start of the list).
    """
    visited: set[int] = set()
    dfs_stack: list[int] = []
    dfs_stack_set: set[int] = set()

    def _dfs(card: int) -> list[int] | None:
        visited.add(card)
        dfs_stack.append(card)
        dfs_stack_set.add(card)

        for dep in sorted(dag.get(card, set())):
            if dep not in nodes:
                continue
            if dep in dfs_stack_set:
                # Back edge found — extract the cycle
                cycle_start_index = dfs_stack.index(dep)
                return dfs_stack[cycle_start_index:]
            if dep not in visited:
                result = _dfs(dep)
                if result is not None:
                    return result

        dfs_stack.pop()
        dfs_stack_set.discard(card)
        return None

    for card in sorted(nodes):
        if card not in visited:
            cycle = _dfs(card)
            if cycle is not None:
                return cycle

    # Fallback: return first two remaining nodes (should not reach here if
    # the caller correctly identified a cycle)
    remaining = sorted(nodes)
    return remaining[:2]
