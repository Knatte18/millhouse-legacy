"""
test_dag.py — Unit tests for millpy.core.dag (TDD: RED → GREEN → REFACTOR).

Tests cover build_dag, topological_sort, and extract_layers independently,
plus integration tests through the full Card Index → layers pipeline.
"""
from __future__ import annotations

import pytest

from millpy.core.dag import CycleError, build_dag, extract_layers, topological_sort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(
    *,
    slug: str = "card",
    creates: list[str] | None = None,
    modifies: list[str] | None = None,
    reads: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict:
    return {
        "slug": slug,
        "creates": creates or [],
        "modifies": modifies or [],
        "reads": reads or [],
        "depends-on": depends_on or [],
    }


# ---------------------------------------------------------------------------
# CycleError
# ---------------------------------------------------------------------------

class TestCycleError:
    def test_is_value_error(self) -> None:
        err = CycleError([1, 2])
        assert isinstance(err, ValueError)

    def test_cycle_attribute(self) -> None:
        err = CycleError([3, 5, 7])
        assert err.cycle == [3, 5, 7]

    def test_message_contains_cycle(self) -> None:
        err = CycleError([1, 2])
        assert "1" in str(err)
        assert "2" in str(err)


# ---------------------------------------------------------------------------
# build_dag — explicit edges
# ---------------------------------------------------------------------------

class TestBuildDagExplicitEdges:
    def test_single_card_no_dependencies(self) -> None:
        card_index = {1: _make_card(slug="only")}
        dag = build_dag(card_index)
        assert dag == {1: set()}

    def test_linear_chain_explicit(self) -> None:
        card_index = {
            1: _make_card(slug="a"),
            2: _make_card(slug="b", depends_on=["1"]),
            3: _make_card(slug="c", depends_on=["2"]),
        }
        dag = build_dag(card_index)
        assert dag[1] == set()
        assert dag[2] == {1}
        assert dag[3] == {2}

    def test_diamond_explicit(self) -> None:
        card_index = {
            1: _make_card(slug="a"),
            2: _make_card(slug="b"),
            3: _make_card(slug="c", depends_on=["1", "2"]),
        }
        dag = build_dag(card_index)
        assert dag[1] == set()
        assert dag[2] == set()
        assert dag[3] == {1, 2}

    def test_all_independent(self) -> None:
        card_index = {n: _make_card(slug=f"card{n}") for n in range(1, 6)}
        dag = build_dag(card_index)
        for n in range(1, 6):
            assert dag[n] == set()

    def test_depends_on_string_parsed_to_int(self) -> None:
        card_index = {
            1: _make_card(slug="a"),
            2: _make_card(slug="b", depends_on=["1"]),
        }
        dag = build_dag(card_index)
        assert 1 in dag[2]


# ---------------------------------------------------------------------------
# build_dag — implicit edges from file conflicts
# ---------------------------------------------------------------------------

class TestBuildDagImplicitEdges:
    def test_shared_creates_file_adds_implicit_edge(self) -> None:
        """Card 3 modifies a file that card 1 creates → implicit 3 depends on 1."""
        card_index = {
            1: _make_card(slug="a", creates=["core/foo.py"]),
            3: _make_card(slug="c", modifies=["core/foo.py"]),
        }
        dag = build_dag(card_index)
        assert 1 in dag[3], "card 3 must depend on card 1 due to shared file"
        assert dag[1] == set()

    def test_both_creates_same_file_serializes(self) -> None:
        """Two cards both creating the same file — higher depends on lower."""
        card_index = {
            2: _make_card(slug="b", creates=["shared.py"]),
            5: _make_card(slug="e", creates=["shared.py"]),
        }
        dag = build_dag(card_index)
        assert 2 in dag[5]
        assert dag[2] == set()

    def test_both_modifies_same_file_serializes(self) -> None:
        card_index = {
            1: _make_card(slug="a", modifies=["util.py"]),
            4: _make_card(slug="d", modifies=["util.py"]),
        }
        dag = build_dag(card_index)
        assert 1 in dag[4]

    def test_reads_only_does_not_create_implicit_edge(self) -> None:
        """Files in `reads` only must NOT create implicit edges."""
        card_index = {
            1: _make_card(slug="a", creates=["api.py"]),
            2: _make_card(slug="b", reads=["api.py"]),
        }
        dag = build_dag(card_index)
        assert dag[2] == set(), "reads-only should not create implicit edge"

    def test_no_shared_files_no_implicit_edges(self) -> None:
        card_index = {
            1: _make_card(slug="a", creates=["a.py"]),
            2: _make_card(slug="b", creates=["b.py"]),
        }
        dag = build_dag(card_index)
        assert dag[1] == set()
        assert dag[2] == set()

    def test_implicit_and_explicit_edges_combined(self) -> None:
        """Explicit depends-on plus implicit file conflict — union."""
        card_index = {
            1: _make_card(slug="a"),
            2: _make_card(slug="b", creates=["shared.py"]),
            3: _make_card(slug="c", modifies=["shared.py"], depends_on=["1"]),
        }
        dag = build_dag(card_index)
        assert dag[3] == {1, 2}


# ---------------------------------------------------------------------------
# topological_sort
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    def test_single_card(self) -> None:
        dag = {1: set()}
        assert topological_sort(dag) == [1]

    def test_linear_chain(self) -> None:
        dag = {1: set(), 2: {1}, 3: {2}}
        result = topological_sort(dag)
        assert result.index(1) < result.index(2)
        assert result.index(2) < result.index(3)

    def test_diamond(self) -> None:
        dag = {1: set(), 2: set(), 3: {1, 2}}
        result = topological_sort(dag)
        assert result.index(1) < result.index(3)
        assert result.index(2) < result.index(3)
        assert set(result) == {1, 2, 3}

    def test_all_independent(self) -> None:
        dag = {n: set() for n in range(1, 6)}
        result = topological_sort(dag)
        assert set(result) == {1, 2, 3, 4, 5}
        assert len(result) == 5

    def test_cycle_raises_cycle_error(self) -> None:
        dag = {1: {2}, 2: {1}}
        with pytest.raises(CycleError) as exc_info:
            topological_sort(dag)
        assert 1 in exc_info.value.cycle
        assert 2 in exc_info.value.cycle

    def test_cycle_three_nodes(self) -> None:
        dag = {1: {3}, 2: {1}, 3: {2}}
        with pytest.raises(CycleError) as exc_info:
            topological_sort(dag)
        cycle = exc_info.value.cycle
        assert set(cycle) == {1, 2, 3}

    def test_empty_dag(self) -> None:
        assert topological_sort({}) == []


# ---------------------------------------------------------------------------
# extract_layers
# ---------------------------------------------------------------------------

class TestExtractLayers:
    def test_single_card_no_dependencies(self) -> None:
        dag = {1: set()}
        assert extract_layers(dag) == [[1]]

    def test_linear_chain(self) -> None:
        dag = {1: set(), 2: {1}, 3: {2}}
        assert extract_layers(dag) == [[1], [2], [3]]

    def test_diamond(self) -> None:
        """Cards 1 and 2 are independent → layer 0. Card 3 depends on both → layer 1."""
        dag = {1: set(), 2: set(), 3: {1, 2}}
        assert extract_layers(dag) == [[1, 2], [3]]

    def test_all_independent_one_layer(self) -> None:
        dag = {n: set() for n in range(1, 6)}
        layers = extract_layers(dag)
        assert len(layers) == 1
        assert layers[0] == [1, 2, 3, 4, 5]

    def test_within_layer_sorted_by_card_number(self) -> None:
        dag = {5: set(), 1: set(), 3: set(), 2: set()}
        layers = extract_layers(dag)
        assert layers == [[1, 2, 3, 5]]

    def test_cycle_raises_cycle_error(self) -> None:
        dag = {1: {2}, 2: {1}}
        with pytest.raises(CycleError) as exc_info:
            extract_layers(dag)
        assert 1 in exc_info.value.cycle
        assert 2 in exc_info.value.cycle

    def test_empty_dag(self) -> None:
        assert extract_layers({}) == []

    def test_complex_dag_layer_ordering(self) -> None:
        """Cards 1,2 independent; 3,4 depend on 1; 5 depends on 3 and 4; 6 depends on 2."""
        dag = {
            1: set(),
            2: set(),
            3: {1},
            4: {1},
            5: {3, 4},
            6: {2},
        }
        layers = extract_layers(dag)
        assert layers[0] == [1, 2]
        assert layers[1] == [3, 4, 6]
        assert layers[2] == [5]


# ---------------------------------------------------------------------------
# Integration: Card Index → build_dag → extract_layers
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_linear_chain_from_card_index(self) -> None:
        card_index = {
            1: _make_card(slug="a"),
            2: _make_card(slug="b", depends_on=["1"]),
            3: _make_card(slug="c", depends_on=["2"]),
        }
        dag = build_dag(card_index)
        layers = extract_layers(dag)
        assert layers == [[1], [2], [3]]

    def test_diamond_from_card_index(self) -> None:
        card_index = {
            1: _make_card(slug="a"),
            2: _make_card(slug="b"),
            3: _make_card(slug="c", depends_on=["1", "2"]),
        }
        dag = build_dag(card_index)
        layers = extract_layers(dag)
        assert layers == [[1, 2], [3]]

    def test_implicit_edge_from_shared_file(self) -> None:
        """card 1 creates foo.py, card 3 modifies foo.py — no explicit depends-on."""
        card_index = {
            1: _make_card(slug="a", creates=["core/foo.py"]),
            2: _make_card(slug="b"),
            3: _make_card(slug="c", modifies=["core/foo.py"]),
        }
        dag = build_dag(card_index)
        layers = extract_layers(dag)
        # card 3 must come after card 1; card 2 is independent
        assert 1 in layers[0]
        assert 2 in layers[0]
        card_3_layer = next(i for i, layer in enumerate(layers) if 3 in layer)
        card_1_layer = next(i for i, layer in enumerate(layers) if 1 in layer)
        assert card_3_layer > card_1_layer

    def test_cycle_raises_cycle_error(self) -> None:
        card_index = {
            1: _make_card(slug="a", depends_on=["2"]),
            2: _make_card(slug="b", depends_on=["1"]),
        }
        dag = build_dag(card_index)
        with pytest.raises(CycleError) as exc_info:
            extract_layers(dag)
        assert set(exc_info.value.cycle) == {1, 2}

    def test_single_card(self) -> None:
        card_index = {1: _make_card(slug="only")}
        dag = build_dag(card_index)
        layers = extract_layers(dag)
        assert layers == [[1]]

    def test_all_independent_cards(self) -> None:
        card_index = {n: _make_card(slug=f"card{n}") for n in range(1, 6)}
        dag = build_dag(card_index)
        layers = extract_layers(dag)
        assert len(layers) == 1
        assert layers[0] == [1, 2, 3, 4, 5]

    def test_complex_dag_ten_cards(self) -> None:
        """10-card DAG with mixed explicit and implicit edges."""
        card_index = {
            1: _make_card(slug="c1"),
            2: _make_card(slug="c2"),
            3: _make_card(slug="c3", depends_on=["1"]),
            4: _make_card(slug="c4", depends_on=["1", "2"]),
            5: _make_card(slug="c5", depends_on=["3"]),
            6: _make_card(slug="c6", creates=["shared.py"]),
            7: _make_card(slug="c7", modifies=["shared.py"]),  # implicit dep on 6
            8: _make_card(slug="c8", depends_on=["4", "5"]),
            9: _make_card(slug="c9", depends_on=["6"]),
            10: _make_card(slug="c10", depends_on=["7", "8", "9"]),
        }
        dag = build_dag(card_index)

        # Verify implicit edge: card 7 depends on card 6
        assert 6 in dag[7]

        layers = extract_layers(dag)

        # Every layer must precede the layer of cards that depend on it
        layer_of: dict[int, int] = {}
        for layer_idx, layer in enumerate(layers):
            for card in layer:
                layer_of[card] = layer_idx

        for card_num, deps in dag.items():
            for dep in deps:
                assert layer_of[dep] < layer_of[card_num], (
                    f"card {card_num} (layer {layer_of[card_num]}) must be "
                    f"after dep {dep} (layer {layer_of[dep]})"
                )

        # Card 10 must be in the last layer
        assert layer_of[10] == len(layers) - 1
