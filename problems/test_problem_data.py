import json
import subprocess
import sys

from django.test import SimpleTestCase

from problems.management.commands.seed_problems import DEFAULT_DATA_FILE


def solve_sum(input_data):
    a, b = map(int, input_data.split())
    return str(a + b)


def solve_even_or_odd(input_data):
    return "CHAN" if int(input_data) % 2 == 0 else "LE"


def solve_product(input_data):
    a, b = map(int, input_data.split())
    return str(a * b)


def solve_maximum(input_data):
    return str(max(map(int, input_data.split())))


def solve_vowels(input_data):
    return str(sum(character.lower() in "aeiou" for character in input_data))


def solve_palindrome(input_data):
    text = input_data.strip().lower()
    return "YES" if text == text[::-1] else "NO"


def solve_fibonacci(input_data):
    n = int(input_data)
    current, following = 0, 1
    for _ in range(n):
        current, following = following, current + following
    return str(current)


def solve_primes(input_data):
    n = int(input_data)
    primes = []
    for candidate in range(2, n + 1):
        is_prime = all(
            candidate % divisor != 0
            for divisor in range(2, int(candidate**0.5) + 1)
        )
        if is_prime:
            primes.append(str(candidate))
    return " ".join(primes)


def solve_second_largest(input_data):
    lines = input_data.splitlines()
    n = int(lines[0])
    numbers = list(map(int, lines[1].split()))
    if len(numbers) != n:
        raise AssertionError("Second-largest test input does not contain n values.")
    return str(sorted(set(numbers), reverse=True)[1])


def solve_triangle(input_data):
    n = int(input_data)
    return "\n".join("*" * width for width in range(1, n + 1))


REFERENCE_SOLVERS = {
    "sum-two-numbers": solve_sum,
    "even-or-odd": solve_even_or_odd,
    "multiply-two-numbers": solve_product,
    "maximum-of-three": solve_maximum,
    "count-vowels": solve_vowels,
    "palindrome-check": solve_palindrome,
    "fibonacci-number": solve_fibonacci,
    "primes-up-to-n": solve_primes,
    "second-largest-distinct": solve_second_largest,
    "star-triangle": solve_triangle,
}


class ProblemDataAuditTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.problems = json.loads(
            DEFAULT_DATA_FILE.read_text(encoding="utf-8")
        )["problems"]

    def test_bank_shape_and_test_case_counts(self):
        difficulty_counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
        problem_orders = []
        for problem in self.problems:
            difficulty_counts[problem["difficulty"]] += 1
            problem_orders.append(problem["order"])
            test_orders = [test_case["order"] for test_case in problem["test_cases"]]
            self.assertEqual(len(test_orders), len(set(test_orders)), problem["slug"])
            self.assertEqual(
                sum(test_case["is_sample"] for test_case in problem["test_cases"]),
                1,
                problem["slug"],
            )
            self.assertEqual(
                sum(not test_case["is_sample"] for test_case in problem["test_cases"]),
                6,
                problem["slug"],
            )

        self.assertEqual(len(self.problems), 10)
        self.assertEqual(difficulty_counts, {"EASY": 3, "MEDIUM": 4, "HARD": 3})
        self.assertEqual(len(problem_orders), len(set(problem_orders)))
        self.assertEqual(set(REFERENCE_SOLVERS), {item["slug"] for item in self.problems})

    def test_every_expected_output_matches_reference_solver(self):
        for problem in self.problems:
            solver = REFERENCE_SOLVERS[problem["slug"]]
            for test_case in problem["test_cases"]:
                with self.subTest(
                    problem=problem["slug"],
                    test_case=test_case["order"],
                ):
                    self.assertEqual(
                        solver(test_case["input_data"]),
                        test_case["expected_output"],
                    )

    def test_every_reference_solution_passes_all_seed_tests(self):
        for problem in self.problems:
            for test_case in problem["test_cases"]:
                with self.subTest(
                    problem=problem["slug"],
                    test_case=test_case["order"],
                ):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            "-c",
                            problem["reference_solution"],
                        ],
                        input=test_case["input_data"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(
                        completed.stdout.rstrip("\r\n"),
                        test_case["expected_output"],
                    )

    def test_palindrome_hidden_tests_cover_case_insensitivity(self):
        problem = next(
            item for item in self.problems if item["slug"] == "palindrome-check"
        )
        mixed_case_palindromes = [
            test_case
            for test_case in problem["test_cases"]
            if not test_case["is_sample"]
            and test_case["input_data"] != test_case["input_data"].lower()
            and test_case["expected_output"] == "YES"
        ]
        self.assertTrue(mixed_case_palindromes)

    def test_triangle_sample_has_four_rows(self):
        problem = next(
            item for item in self.problems if item["slug"] == "star-triangle"
        )
        sample = next(
            test_case for test_case in problem["test_cases"] if test_case["is_sample"]
        )
        self.assertEqual(sample["input_data"], "4")
        self.assertEqual(sample["expected_output"], "*\n**\n***\n****")
