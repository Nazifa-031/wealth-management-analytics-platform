"""
Step 4: Generate an HTML investment report, standalone CLI.

Same natural-language understanding as ask.py's chat loop - both call
report_utils.parse_report_request(), so typing "create a report for
Rohan Mehta" here works exactly like typing it into ask.py.

Interactive mode (recommended - just describe what you want):
    $ python 04_generate_report.py
    Report request: create a report for Rohan Mehta
    Report request: advisor report for Priya Shah
    Report request: scheme report for Bluechip Growth Fund
    Report request: amc report for HDFC Mutual Fund
    Report request: executive report
    Report request: quit

One-shot mode (for scripts/cron - pass the whole request as argv):
    python 04_generate_report.py create a report for Rohan Mehta
    python 04_generate_report.py 101
    python 04_generate_report.py executive
"""

import sys
import report_utils


def generate(text):
    try:
        path = report_utils.generate_report_from_text(text)
        print(f"Report saved to: {path}")
        print("Open it in a browser to view.")
        return True
    except ValueError as e:
        print(str(e))
        return False


def interactive():
    print("Describe the report you want, e.g. 'create a report for Rohan Mehta'")
    print("or 'advisor report for Priya Shah', 'executive report'. Type 'quit' to exit.")
    while True:
        text = input("\nReport request: ").strip()
        if text.lower() in ("quit", "exit"):
            break
        if not text:
            continue
        generate(text)


def main():
    if len(sys.argv) > 1:
        # One-shot mode: treat all remaining args as one free-form request,
        # e.g. `python 04_generate_report.py create a report for Rohan Mehta`
        # or the old-style `python 04_generate_report.py "Rohan Mehta"`.
        text = " ".join(sys.argv[1:])
        ok = generate(text)
        sys.exit(0 if ok else 1)

    interactive()


if __name__ == "__main__":
    main()