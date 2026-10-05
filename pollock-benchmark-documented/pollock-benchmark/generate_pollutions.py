"""Generate original Pollock cases without Docker or Unix shell commands."""
from copy import deepcopy
from pathlib import Path
import json
from pollock.CSVFile import CSVFile
import pollock.polluters_stdlib as pl

PROJECT_DIR = Path(__file__).resolve().parent
OUT_CSV_PATH = (PROJECT_DIR / "data/polluted/pollock").as_posix() + "/"
OUT_CLEAN_PATH = (PROJECT_DIR / "data/expected/pollock").as_posix() + "/"
OUT_PARAMETERS_PATH = (PROJECT_DIR / "data/parameters/pollock").as_posix() + "/"


def generate():
    for directory in (OUT_CSV_PATH, OUT_CLEAN_PATH, OUT_PARAMETERS_PATH):
        Path(directory).mkdir(parents=True, exist_ok=True)
    manifest = []

    def execute_polluter(file, polluter, new_filename=None, *args, **kwargs):
        # Every case starts with its own copy of the clean source tree.
        t = deepcopy(file)
        polluter(t, *args, **kwargs)
        if new_filename is not None:
            t.filename = new_filename
            t.xml.getroot().attrib["filename"] = new_filename
        if any(case["filename"] == t.filename for case in manifest):
            raise ValueError(f"Duplicate output name: {t.filename}")
        t.write_csv(OUT_CSV_PATH)
        t.write_clean_csv(OUT_CLEAN_PATH)
        t.write_parameters(OUT_PARAMETERS_PATH)
        manifest.append({"filename": t.filename, "polluter": polluter.__name__,
                         "arguments": kwargs})
        if len(manifest) % 250 == 0:
            print(f"Generated {len(manifest)} cases...")

    f = CSVFile((PROJECT_DIR / "data/clean/source.csv").as_posix(), quote_all=True)
    # Returns the source file : 1 file
    execute_polluter(f, pl.dummyPolluter, "source.csv")

    # File payload polluters : 3 files
    execute_polluter(f, pl.changeDimension, target_dimension=0, new_filename="file_no_payload.csv")
    execute_polluter(f, pl.changeRowRecordDelimiter, row=-1, target_delimiter="", new_filename="file_no_trailing_newline.csv")
    execute_polluter(f, pl.changeRowRecordDelimiter, row=-1, target_delimiter="\r\n\r\n", new_filename="file_double_trailing_newline.csv")

    # Header and preamble polluters : 7 files
    execute_polluter(f, pl.changeNumberRows, target_number_rows=f.row_count, remove_header=True, new_filename="file_no_header.csv")
    execute_polluter(f, pl.expandColumnHeader, extra_rows=1, new_filename="file_header_multirow_2.csv")  # 1 regular, on multiple rows
    execute_polluter(f, pl.expandColumnHeader, extra_rows=2, new_filename="file_header_multirow_3.csv")  # 1 regular, on multiple rows
    execute_polluter(f, pl.addPreamble, n_rows=1, delimiters=True, emptyrow=True, new_filename="file_preamble.csv")  # delimited, with empty
    execute_polluter(f, pl.addTable, new_filename="file_multitable_less.csv", n_rows=83, n_cols=8, empty_boundary=False)
    execute_polluter(f, pl.addTable, new_filename="file_multitable_same.csv", n_rows=83, n_cols=9, empty_boundary=False)
    execute_polluter(f, pl.addTable, new_filename="file_multitable_more.csv", n_rows=83, n_cols=10, empty_boundary=False)

    # Data rows: 2 files
    execute_polluter(f, pl.changeNumberRows, new_filename="file_header_only.csv", target_number_rows=1)
    execute_polluter(f, pl.changeNumberRows, new_filename="file_one_data_row.csv", target_number_rows=2)

    # Add or remove one separator for each row/column : 1428 files
    # Add extra quote mark for each row/column : 756 files
    # Change delimiter for each row : 88 files
    for i in range(f.row_count):
        for j in range(f.col_count):
            execute_polluter(f, pl.addRowFieldDelimiter, new_filename=f"row_more_sep_row{i}_col{j}.csv", row=i, col=j)  # row 1, empty
            if j > 0:
                execute_polluter(f, pl.deleteRowFieldDelimiter, new_filename=f"row_less_sep_row{i}_col{j}.csv", row=i, col=j)  # row 1, empty
            execute_polluter(f, pl.addRowQuoteMark, new_filename=f"row_extra_quote{i}_col{j}.csv", row=i, col=j)  # row 1, empty

        vals = [ord(x) for x in " "]
        del_string = ''.join([f'_0x{v:X}' for v in vals])
        target_filename = f"row_field_delimiter_{i}{del_string}.csv"
        execute_polluter(f, pl.changeRowFieldDelimiter, new_filename=target_filename, row=i, target_delimiter=" ")

    # Change record Delimiter : 2 files
    execute_polluter(f, pl.changeRecordDelimiter, target_delimiter="\n")
    execute_polluter(f, pl.changeRecordDelimiter, target_delimiter="\r")

    # Change delimiter everywhere : 4 files
    execute_polluter(f, pl.changeFieldDelimiter, target_delimiter=";")
    execute_polluter(f, pl.changeFieldDelimiter, target_delimiter="\t")
    execute_polluter(f, pl.changeFieldDelimiter, target_delimiter=", ")
    execute_polluter(f, pl.changeFieldDelimiter, target_delimiter=" ")

    # Change quotation mark everywhere : 1 file
    execute_polluter(f, pl.changeQuotationChar, target_char="\u0027")

    # Change escape character : 2 files
    execute_polluter(f, pl.changeEscapeCharacter, target_escape="\u005C")  # backslash
    execute_polluter(f, pl.changeEscapeCharacter, target_escape="")

    manifest_path = PROJECT_DIR / "data/pollock_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generation complete: {len(manifest)} cases (including source.csv).")
    print("Polluted files:", OUT_CSV_PATH)
    print("Expected files:", OUT_CLEAN_PATH)
    print("Parameters:", OUT_PARAMETERS_PATH)


if __name__ == "__main__":
    generate()
