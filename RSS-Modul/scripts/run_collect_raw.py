import argparse
from pipelines.collect_raw_pipeline import collect_raw_from_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--code-prefix")
    args = parser.parse_args()

    collect_raw_from_source(source=args.source, code_prefix=args.code_prefix)


if __name__ == "__main__":
    main()
