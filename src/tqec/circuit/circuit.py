from __future__ import annotations

from copy import deepcopy

import cirq

from tqec.circuit.schedule import ScheduledCircuit, merge_scheduled_circuits
from tqec.exceptions import TQECException
from tqec.plaquette.plaquette import Plaquette
from tqec.position import Displacement
from tqec.templates.base import Template


def generate_circuit(
    template: Template,
    plaquettes: list[Plaquette] | dict[int, Plaquette],
) -> cirq.Circuit:
    """Generate a quantum circuit from a template and its plaquettes

    This is one of the core methods of the `tqec` package. It generates a quantum circuit
    from the description of the template that should be implemented as well as the plaquettes
    that should be used to instantiate the provided template.

    This function requires that a few pre-conditions on the inputs are met:
    1. the number of plaquettes provided should match the number of plaquettes required by
    the provided template.
    2. all the provided plaquettes should be implemented on cirq.GridQubit instances **only**.

    If any of the above pre-conditions is not met, the inputs are considered invalid, in which
    case this function **might** raise an error.

    Args:
        template: spatial description of the quantum error correction experiment
            we want to implement.
        plaquettes: description of the computation that should happen at
            different time-slices of the quantum error correction experiment (or
            at least part of it).

    Returns:
        a cirq.Circuit instance implementing the (part of) quantum error
        correction experiment represented by the provided inputs.

    Raises:
        TQECException: if the provided plaquettes do not match the expected
            number of plaquettes for the given template.
    """
    # Check that the user gave enough plaquettes.
    if len(plaquettes) != template.expected_plaquettes_number:
        raise TQECException(
            f"{len(plaquettes)} plaquettes have been provided, but "
            f"{template.expected_plaquettes_number} were expected."
        )

    # If plaquettes are given as a list, make that a dict to simplify the following operations
    if isinstance(plaquettes, list):
        plaquettes = {i + 1: plaquette for i, plaquette in enumerate(plaquettes)}

    # instantiate the template with the appropriate plaquette indices.
    # Index 0 is "no plaquette" by convention and should not be included here.
    _indices = list(range(1, len(plaquettes) + 1))
    template_plaquettes = template.instantiate(_indices)
    increments = template.get_increments()
    # Plaquettes indices are starting at 1 in template_plaquettes. To avoid
    # offsets in the following code, we add an empty circuit at position 0.
    plaquette_circuits = {0: ScheduledCircuit(cirq.Circuit())} | {
        i: p.circuit for i, p in plaquettes.items()
    }

    # Generate the ScheduledCircuit instances for each plaquette instanciation
    all_scheduled_circuits: list[ScheduledCircuit] = []
    plaquette_index: int
    for row_index, line in enumerate(template_plaquettes):
        for column_index, plaquette_index in enumerate(line):
            if plaquette_index != 0:
                scheduled_circuit = deepcopy(plaquette_circuits[plaquette_index])
                offset = Displacement(
                    column_index * increments.x, row_index * increments.y
                )
                plaquette = plaquettes[plaquette_index]
                qubit_map = _create_mapping(plaquette, scheduled_circuit, offset)
                scheduled_circuit.map_to_qubits(qubit_map, inplace=True)
                all_scheduled_circuits.append(scheduled_circuit)

    # Merge everything!
    return merge_scheduled_circuits(all_scheduled_circuits)


def _create_mapping(
    plaquette: Plaquette, scheduled_circuit: ScheduledCircuit, offset: Displacement
) -> dict[cirq.GridQubit, cirq.GridQubit]:
    origin = plaquette.origin

    qubit_map = {
        # GridQubit are indexed as (row, col), so (y, x)
        # Qubits are given relative to an origin, so we need to add the offset
        qubit: qubit + (offset.y, offset.x) + (origin.y, origin.x)  # type: ignore
        for qubit in scheduled_circuit.mappable_qubits
    }
    return qubit_map
