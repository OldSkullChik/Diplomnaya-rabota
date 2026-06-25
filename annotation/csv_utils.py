import csv


def clean_cell(value):
    if value is None:
        return ""
    return " ".join(str(value).replace("\ufeff", "").split())


def first_value(row, fields):
    for field in fields:
        value = clean_cell(row.get(field))
        if value:
            return value
    return ""


def sniff_dialect(sample):
    header = sample.splitlines()[0] if sample else ""
    delimiter_counts = {
        ",": header.count(","),
        ";": header.count(";"),
        "\t": header.count("\t"),
    }
    delimiter, count = max(delimiter_counts.items(), key=lambda item: item[1])
    if count:
        class HeaderDialect(csv.excel):
            pass

        HeaderDialect.delimiter = delimiter
        return HeaderDialect

    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel
