import argparse
from pipelines.generate_descriptions_pipeline import generate_descriptions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="claude-sonnet")
    parser.add_argument("--code-prefix")
    args = parser.parse_args()

    generate_descriptions(model_id=args.model_id, code_prefix=args.code_prefix)


if __name__ == "__main__":
    main()
