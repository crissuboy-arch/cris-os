"""
Semver — parser e matching de versões semânticas para o Capability Registry.

Suporta:
  - Versão exata:     "1.2.3"
  - Compatível (^):   "^1.2.3"  → >=1.2.3 e <2.0.0
  - Aproximado (~):   "~1.2.3"  → >=1.2.3 e <1.3.0
  - Maior/menor:      ">=1.2.3", ">1.2.3", "<=1.2.3", "<1.2.3"
  - Igual:            "=1.2.3"
  - Range:            ">=1.0.0 <2.0.0"
  - Wilderos (x):     "1.2.x", "1.x"
  - Apenas major:     "1"
"""

from __future__ import annotations

import re

_RE_SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"(?:\.(?P<minor>0|[1-9]\d*))?"
    r"(?:\.(?P<patch>0|[1-9]\d*))?"
    r"(?:-(?P<prerelease>[a-zA-Z0-9.-]+))?"
    r"(?:\+(?P<build>[a-zA-Z0-9.-]+))?$"
)


class Version:
    """Versão semântica."""

    def __init__(self, major: int, minor: int = 0, patch: int = 0,
                 prerelease: str | None = None) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease

    @classmethod
    def parse(cls, text: str) -> Version:
        m = _RE_SEMVER.match(text.strip())
        if not m:
            raise ValueError(f"Versão inválida: '{text}'")
        major = int(m.group("major"))
        minor = int(m.group("minor") or "0")
        patch = int(m.group("patch") or "0")
        prerelease = m.group("prerelease") or None
        return cls(major, minor, patch, prerelease)

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        return base

    def __repr__(self) -> str:
        return f"Version('{self}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.prerelease) == (
            other.major, other.minor, other.patch, other.prerelease)

    def __lt__(self, other: Version) -> bool:
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease
        return False

    def __le__(self, other: Version) -> bool:
        return self == other or self < other

    def __gt__(self, other: Version) -> bool:
        return not (self <= other)

    def __ge__(self, other: Version) -> bool:
        return not (self < other)


def _strip_eq(text: str) -> str:
    return text.lstrip("=").strip()


def match(text_version: str, constraint: str) -> bool:
    """Verifica se text_version satisfaz a constraint.

    Args:
        text_version: Versão alvo (ex.: "1.2.3")
        constraint:  Constraint (ex.: "^1.0", ">=1.2 <2.0", "1.x")

    Returns:
        True se a versão satisfaz a constraint.
    """
    version = Version.parse(text_version)
    constraint = constraint.strip()

    # Range: ">=1.0.0 <2.0.0"
    parts = constraint.split()
    if len(parts) == 2:
        return match(text_version, parts[0]) and match(text_version, parts[1])

    # Wildcard: "1.x", "1.2.x", "1"
    if constraint.endswith(".x") or constraint.endswith(".*"):
        prefix = constraint.rstrip(".*x")
        if not prefix:
            return True  # "x" sozinho = qualquer
        return text_version.startswith(prefix.rstrip("."))
    if _RE_SEMVER.match(constraint) and "." not in constraint:
        return version.major == int(constraint)

    # Operadores
    if constraint.startswith(">="):
        return version >= Version.parse(_strip_eq(constraint[2:]))
    if constraint.startswith(">"):
        return version > Version.parse(_strip_eq(constraint[1:]))
    if constraint.startswith("<="):
        return version <= Version.parse(_strip_eq(constraint[2:]))
    if constraint.startswith("<"):
        return version < Version.parse(_strip_eq(constraint[1:]))

    # Compatível: "^1.2.3" → >=1.2.3 e <2.0.0
    if constraint.startswith("^"):
        base = Version.parse(_strip_eq(constraint[1:]))
        if base.major == 0 and base.minor > 0:
            upper = Version(base.major, base.minor + 1, 0)
        else:
            upper = Version(base.major + 1, 0, 0)
        return base <= version < upper

    # Aproximado: "~1.2.3" → >=1.2.3 e <1.3.0
    if constraint.startswith("~"):
        base = Version.parse(_strip_eq(constraint[1:]))
        upper = Version(base.major, base.minor + 1, 0)
        return base <= version < upper

    # Igual explícito ou versão exata
    if constraint.startswith("="):
        return version == Version.parse(_strip_eq(constraint[1:]))
    return version == Version.parse(constraint)  # exata