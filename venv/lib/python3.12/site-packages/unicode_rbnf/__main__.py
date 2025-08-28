import argparse

from unicode_rbnf import FormatPurpose, RbnfEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--language",
        choices=RbnfEngine.get_supported_languages(),
        required=True,
        help="Language code",
    )
    parser.add_argument(
        "--purpose",
        choices=[v.value for v in FormatPurpose],
        default=FormatPurpose.CARDINAL,
        help="Format purpose",
    )
    parser.add_argument("number", nargs="+", help="Number(s) to turn into words")
    args = parser.parse_args()

    engine = RbnfEngine.for_language(args.language)
    for number_str in args.number:
        result = engine.format_number(number_str, purpose=FormatPurpose(args.purpose))
        for ruleset, words in result.text_by_ruleset.items():
            print(number_str, ruleset, words, sep="|")


if __name__ == "__main__":
    main()
