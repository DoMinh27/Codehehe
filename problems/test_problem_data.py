import json
import subprocess
import sys
from collections import Counter

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


def solve_leap_year(input_data):
    year = int(input_data)
    return "YES" if year % 400 == 0 or year % 4 == 0 and year % 100 else "NO"


def solve_reverse_string(input_data):
    return input_data[::-1]


def solve_hamming_distance(input_data):
    first, second = input_data.splitlines()
    return str(sum(left != right for left, right in zip(first, second)))


def solve_isogram(input_data):
    letters = [character.casefold() for character in input_data if character.isalpha()]
    return "YES" if len(letters) == len(set(letters)) else "NO"


def solve_acronym(input_data):
    return "".join(
        word[0].upper() for word in input_data.replace("-", " ").split()
    )


def solve_digit_sum(input_data):
    return str(sum(int(digit) for digit in str(abs(int(input_data)))))


def solve_classify_numbers(input_data):
    lines = input_data.splitlines()
    count = int(lines[0])
    numbers = [int(value) for value in lines[1].split()]
    if len(numbers) != count:
        raise AssertionError("Classification input does not contain n values.")
    positive = sum(value > 0 for value in numbers)
    negative = sum(value < 0 for value in numbers)
    return f"{positive} {negative} {count - positive - negative}"


def solve_armstrong(input_data):
    digits = input_data.strip()
    return (
        "YES"
        if sum(int(digit) ** len(digits) for digit in digits) == int(digits)
        else "NO"
    )


def solve_anagram(input_data):
    first, second = input_data.splitlines()
    normalize = lambda text: Counter(  # noqa: E731
        character.casefold() for character in text if not character.isspace()
    )
    return "YES" if normalize(first) == normalize(second) else "NO"


def solve_luhn(input_data):
    digits = [int(character) for character in input_data if character.isdigit()]
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit = digit * 2 - 9 if digit >= 5 else digit * 2
        checksum += digit
    return "YES" if checksum % 10 == 0 else "NO"


def solve_nucleotide_count(input_data):
    counts = Counter(input_data.strip())
    return " ".join(str(counts[nucleotide]) for nucleotide in "ACGT")


def solve_collatz(input_data):
    value = int(input_data)
    steps = 0
    while value > 1:
        value = value // 2 if value % 2 == 0 else value * 3 + 1
        steps += 1
    return str(steps)


def solve_difference_of_squares(input_data):
    values = range(1, int(input_data) + 1)
    return str(sum(values) ** 2 - sum(value * value for value in values))


def solve_rotate_array(input_data):
    header, values = input_data.splitlines()
    count, rotations = map(int, header.split())
    numbers = values.split()
    if len(numbers) != count:
        raise AssertionError("Rotation input does not contain n values.")
    rotations %= count
    result = numbers[-rotations:] + numbers[:-rotations] if rotations else numbers
    return " ".join(result)


def solve_most_frequent(input_data):
    header, values = input_data.splitlines()
    count = int(header)
    numbers = [int(value) for value in values.split()]
    if len(numbers) != count:
        raise AssertionError("Frequency input does not contain n values.")
    frequencies = Counter(numbers)
    highest = max(frequencies.values())
    return str(min(value for value, frequency in frequencies.items() if frequency == highest))


def solve_largest_series_product(input_data):
    digits_text, width_text = input_data.splitlines()
    width = int(width_text)
    if width == 0:
        return "1"
    products = []
    for start in range(len(digits_text) - width + 1):
        product = 1
        for digit in digits_text[start : start + width]:
            product *= int(digit)
        products.append(product)
    return str(max(products))


def solve_minesweeper(input_data):
    lines = input_data.splitlines()
    rows, columns = map(int, lines[0].split())
    grid = lines[1:]
    result = []
    for row in range(rows):
        output = []
        for column in range(columns):
            if grid[row][column] == "*":
                output.append("*")
                continue
            neighbors = (
                grid[nearby_row][nearby_column]
                for nearby_row in range(max(0, row - 1), min(rows, row + 2))
                for nearby_column in range(
                    max(0, column - 1), min(columns, column + 2)
                )
            )
            output.append(str(sum(value == "*" for value in neighbors)))
        result.append("".join(output))
    return "\n".join(result)


def solve_saddle_points(input_data):
    lines = input_data.splitlines()
    rows, columns = map(int, lines[0].split())
    matrix = [list(map(int, line.split())) for line in lines[1:]]
    row_maximums = [max(row) for row in matrix]
    column_minimums = [
        min(matrix[row][column] for row in range(rows))
        for column in range(columns)
    ]
    points = [
        f"{row + 1} {column + 1}"
        for row in range(rows)
        for column in range(columns)
        if matrix[row][column] == row_maximums[row]
        and matrix[row][column] == column_minimums[column]
    ]
    return "\n".join(points) if points else "NONE"


def solve_balanced_brackets(input_data):
    stack = []
    closing = {")": "(", "]": "[", "}": "{"}
    for character in input_data.strip():
        if character in closing.values():
            stack.append(character)
        elif not stack or stack.pop() != closing[character]:
            return "NO"
    return "YES" if not stack else "NO"


def solve_longest_increasing_run(input_data):
    header, values = input_data.splitlines()
    count = int(header)
    numbers = [int(value) for value in values.split()]
    if len(numbers) != count:
        raise AssertionError("Increasing-run input does not contain n values.")
    lengths = [1]
    for index in range(1, count):
        lengths.append(lengths[-1] + 1 if numbers[index] > numbers[index - 1] else 1)
    return str(max(lengths))


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
    "leap-year": solve_leap_year,
    "reverse-string": solve_reverse_string,
    "hamming-distance": solve_hamming_distance,
    "isogram-check": solve_isogram,
    "make-acronym": solve_acronym,
    "digit-sum": solve_digit_sum,
    "classify-numbers": solve_classify_numbers,
    "armstrong-number": solve_armstrong,
    "anagram-check": solve_anagram,
    "luhn-check": solve_luhn,
    "nucleotide-count": solve_nucleotide_count,
    "collatz-steps": solve_collatz,
    "difference-of-squares": solve_difference_of_squares,
    "rotate-array": solve_rotate_array,
    "most-frequent-value": solve_most_frequent,
    "largest-series-product": solve_largest_series_product,
    "minesweeper-map": solve_minesweeper,
    "saddle-points": solve_saddle_points,
    "balanced-brackets": solve_balanced_brackets,
    "longest-increasing-run": solve_longest_increasing_run,
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
                8,
                problem["slug"],
            )

        self.assertEqual(len(self.problems), 30)
        self.assertEqual(difficulty_counts, {"EASY": 10, "MEDIUM": 12, "HARD": 8})
        self.assertEqual(len(problem_orders), len(set(problem_orders)))
        self.assertEqual(set(REFERENCE_SOLVERS), {item["slug"] for item in self.problems})

        source_counts = Counter(problem["source_type"] for problem in self.problems)
        self.assertEqual(source_counts, {"ORIGINAL": 16, "ADAPTED": 14})
        new_problem_sources = Counter(
            problem["source_type"] for problem in self.problems if problem["order"] > 10
        )
        self.assertEqual(new_problem_sources, {"ORIGINAL": 6, "ADAPTED": 14})

    def test_every_problem_has_valid_source_metadata(self):
        allowed_topics = {
            "BASICS",
            "ARITHMETIC",
            "STRINGS",
            "LISTS",
            "HASHING",
            "SEARCH",
            "SIMULATION",
            "MATRIX",
            "STACK",
            "DYNAMIC_PROGRAMMING",
        }
        for problem in self.problems:
            with self.subTest(problem=problem["slug"]):
                self.assertIn(problem["primary_topic"], allowed_topics)
                self.assertTrue(problem["source_name"])
                self.assertTrue(problem["source_license"])
                if problem["source_type"] == "ADAPTED":
                    self.assertEqual(problem["source_license"], "MIT")
                    self.assertTrue(problem["source_url"].startswith("https://"))

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
