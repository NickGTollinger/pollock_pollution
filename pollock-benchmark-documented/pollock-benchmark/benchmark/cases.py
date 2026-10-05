"""Select ten named categories without copying or modifying their files."""

def category(case):
    name, function, args = case['filename'], case['polluter'], case['arguments']
    exact = {
        'source.csv': 'baseline',
        'file_no_header.csv': 'missing_header',
        'file_header_multirow_2.csv': 'two_row_header',
        'file_preamble.csv': 'preamble',
    }
    if name in exact:
        return exact[name]
    # Separator mutations here target data rows; quote mutations also include
    # header positions. Keep every selected positional variant.
    if function == 'addRowFieldDelimiter' and args.get('row', 0) > 0:
        return 'extra_record_separator'
    if function == 'deleteRowFieldDelimiter' and args.get('row', 0) > 0:
        return 'missing_record_separator'
    if function == 'addRowQuoteMark':
        return 'extra_unescaped_quote'
    if function == 'changeFieldDelimiter':
        return {';': 'semicolon_delimiter', '\t': 'tab_delimiter'}.get(args.get('target_delimiter'))
    if function == 'changeQuotationChar' and args.get('target_char') == "'":
        return 'single_quote_character'
    if function == 'changeEscapeCharacter' and args.get('target_escape') == '\\':
        return 'backslash_escape'
    return None
