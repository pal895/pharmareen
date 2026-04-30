from __future__ import annotations

from scripts.seed_test_prices import TEST_PRICE_ROWS, seed_master_stock


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = rows

    def row_values(self, row_number):
        if row_number - 1 >= len(self.rows):
            return []
        return self.rows[row_number - 1]

    def get_all_records(self):
        if not self.rows:
            return []
        headers = self.rows[0]
        records = []
        for row in self.rows[1:]:
            records.append(
                {
                    header: row[index] if index < len(row) else ""
                    for index, header in enumerate(headers)
                }
            )
        return records

    def get_all_values(self):
        return self.rows

    def append_row(self, row, value_input_option=None):
        self.rows.append(list(row))

    def update(self, range_name, values, value_input_option=None):
        if range_name == "A1":
            if self.rows:
                self.rows[0] = list(values[0])
            else:
                self.rows.append(list(values[0]))
            return

        row_number = int(range_name.split(":", maxsplit=1)[0][1:])
        while len(self.rows) < row_number:
            self.rows.append([])
        self.rows[row_number - 1] = list(values[0])


def test_seed_test_prices_does_not_overwrite_without_flag():
    worksheet = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["Panadol", 999, 111, 1, 1],
        ]
    )

    added, skipped, updated = seed_master_stock(worksheet, overwrite=False)

    assert added == len(TEST_PRICE_ROWS) - 1
    assert skipped == 1
    assert updated == 0
    assert worksheet.rows[1] == ["Panadol", 999, 111, 1, 1]


def test_seed_test_prices_overwrites_when_flag_is_used():
    worksheet = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["Panadol", 999, 111, 1, 1],
        ]
    )

    added, skipped, updated = seed_master_stock(worksheet, overwrite=True)

    assert added == len(TEST_PRICE_ROWS) - 1
    assert skipped == 0
    assert updated == 1
    assert worksheet.rows[1] == ["Panadol", 220, 140, 30, 10]
