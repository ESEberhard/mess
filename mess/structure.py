# Copyright (c) 2024 Graphcore Ltd. All rights reserved.
from typing import List

import equinox as eqx
import numpy as np
import jax.numpy as jnp
from jax import value_and_grad
from periodictable import elements

from mess.types import FloatNx3, IntN
from mess.units import to_bohr


class Structure(eqx.Module):
    atomic_number: IntN
    position: FloatNx3

    def __post_init__(self):
        # single atom case
        self.atomic_number = np.atleast_1d(self.atomic_number)
        self.position = np.atleast_2d(self.position)

    @property
    def num_atoms(self) -> int:
        return len(self.atomic_number)

    @property
    def atomic_symbol(self) -> List[str]:
        return [elements[z].symbol for z in self.atomic_number]

    @property
    def num_electrons(self) -> int:
        return np.sum(self.atomic_number)

    def _repr_html_(self):
        import py3Dmol
        from mess.plot import plot_molecule

        v = py3Dmol.view()
        plot_molecule(v, self)
        return v._repr_html_()


def molecule(name: str) -> Structure:
    """Builds a few sample molecules

    Args:
        name (str): either "h2" or "water". More to be added.

    Raises:
        NotImplementedError: _description_

    Returns:
        Structure: the built molecule as a Structure object
    """

    name = name.lower()

    if name == "h2":
        return Structure(
            atomic_number=np.array([1, 1]),
            position=np.array([[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]]),
        )

    if name == "water":
        r"""Single water molecule
        Structure of single water molecule calculated with DFT using B3LYP
        functional and 6-31+G** basis set <https://cccbdb.nist.gov/>"""
        return Structure(
            atomic_number=np.array([8, 1, 1]),
            position=to_bohr(
                np.array([
                    [0.0000, 0.0000, 0.1165],
                    [0.0000, 0.7694, -0.4661],
                    [0.0000, -0.7694, -0.4661],
                ])
            ),
        )

    raise NotImplementedError(f"No structure registered for: {name}")


def nuclear_energy(structure: Structure) -> float:
    """Nuclear electrostatic interaction energy

    Evaluated by taking sum over all unique pairs of atom centers:

    .. math:: \\sum_{j > i} \\frac{Z_i Z_j}{|\\mathbf{r}_i - \\mathbf{r}_j|}

    where :math:`z_i` is the charge of the ith atom (the atomic number).

    Args:
        structure (Structure): input structure

    Returns:
        float: the total nuclear repulsion energy
    """
    idx, jdx = jnp.triu_indices(structure.num_atoms, 1)
    u = structure.atomic_number[idx] * structure.atomic_number[jdx]
    rij = structure.position[idx, :] - structure.position[jdx, :]
    return jnp.sum(u / jnp.linalg.norm(rij, axis=1))


def nuclear_energy_and_force(structure: Structure):
    @value_and_grad
    def energy_and_grad(pos, rest):
        return nuclear_energy(eqx.combine(pos, rest))

    pos, rest = eqx.partition(structure, lambda x: id(x) == id(structure.position))
    E, grad = energy_and_grad(pos, rest)
    return E, -grad.position
