"""One command to answer "How are our Play Store ratings?"

    python run.py              # fetch new reviews, re-analyse, rebuild the report
    python run.py --no-scrape  # rebuild the report from data already on disk
"""

import argparse

from pulse import analyze, report, scrape
from pulse.config import OUTPUT_DIR


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-scrape", action="store_true", help="skip fetching, reuse data/reviews.db")
    args = ap.parse_args()

    if not args.no_scrape:
        scrape.run()
    result, df = analyze.run()
    path = report.write(result)

    # Tagged reviews for anyone who wants to slice further in a spreadsheet.
    out = df.assign(themes=df["themes"].map(";".join))
    out.drop(columns=["minor"]).to_csv(OUTPUT_DIR / "reviews_tagged.csv", index=False, encoding="utf-8-sig")

    print(f"\nReport:  {path}")
    print(f"Digest:  {OUTPUT_DIR / 'digest.md'}\n")
    print((OUTPUT_DIR / "digest.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
