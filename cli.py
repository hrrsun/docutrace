import argparse
from ingest import parse
from engine import Index, ask

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="+")
    p.add_argument("-q", "--question", required=True)
    p.add_argument("--model", default="")
    p.add_argument("--embed", default="")
    args = p.parse_args()
    units = []
    for f in args.files:
        rows, notes = parse(f)
        units += rows
        for note in notes:
            print(note)
    a, refs, log = ask(Index(units, args.embed), args.question, [], args.model)
    print(a)
    for i, u in enumerate(refs, 1):
        print(f"[S{i}] {u.file} · {u.loc}")
    print(log)
