from dataclasses import dataclass


@dataclass
class Condition:
    pass


@dataclass
class EqualCondition(Condition):
    expected_value: bytes | str

    @staticmethod
    def compare(actual: bytes | str, expected: bytes | str) -> bool:
        if type(actual) is not type(expected):
            raise TypeError("Actual and expected values must have the same type.")

        return actual == expected
