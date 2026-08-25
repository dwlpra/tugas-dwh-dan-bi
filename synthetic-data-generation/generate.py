import csv
from pathlib import Path

from faker import Faker


SEED = 2026
TOTAL_TRANSACTIONS = 10_000
OUTPUT_DIR = Path("data")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / "tes.csv"

    fake = Faker("id_ID")
    fake.seed_instance(SEED)

    with output_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["email"])

        for person_id in range(1, TOTAL_TRANSACTIONS + 1):
            writer.writerow(
                [person_id, fake.name(), fake.unique.email(), fake.city()]
            )

    print(f"Generated {TOTAL_TRANSACTIONS} rows: {output_file}")


if __name__ == "__main__":
    main()
